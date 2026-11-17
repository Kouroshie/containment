"""End-to-end AoR + PISC run driven by a project file.

One function, :func:`run`, walks the whole sequence a Class VI submittal
needs and keeps every intermediate result attached to the output so nothing
has to be recomputed differently in a second place:

1. evaluate CO2 and brine properties at in-situ conditions;
2. compute the threshold pressure by every applicable method and select one;
3. run the chosen flow model (analytical superposition, vertical-equilibrium
   numerical, or an imported simulation);
4. delineate the AoR from the maximum-over-time plume and pressure fields;
5. screen artificial penetrations and stage corrective action by arrival time;
6. compute the PISC metrics and the 146.93(c) checklist;
7. optionally run tornado and Monte Carlo uncertainty.

The CLI, the browser app and the report generator all go through here, so the
number in the report is by construction the number the model produced.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, replace

import numpy as np

from . import corrective, delineate, fluids, pisc, threshold
from . import units as U
from .analytical import (
    AquiferModel,
    Boundary,
    BuckleyLeverettPlume,
    NordbottenCeliaPlume,
    PlumeInputs,
    VolumetricPlume,
    Well,
    endpoint_mobility_ratio,
    gravity_number,
    residual_trapping_limit_radius,
)
from .config import Project, zone_output_times
from .numerical import Grid, GridProperties, VESolver, VEWell


@dataclass
class ZoneResult:
    """What one injection zone of a stacked completion produced.

    Each zone is modelled on its own grid with its own fluid state and its own
    threshold pressure, because those follow from its own depth, pressure and
    temperature. Nothing is averaged across zones: the project AoR is the
    union of these, not a delineation of some blended formation.
    """

    name: str
    zone: object                     # config.Zone
    threshold: threshold.ThresholdResult
    aor: delineate.AoRResult
    x: np.ndarray
    y: np.ndarray
    times: np.ndarray
    dp_fields: np.ndarray
    plume_fields: np.ndarray
    plume_level: float
    injected_mass: float = 0.0
    pisc: pisc.PISCResult | None = None
    series: list = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def summary(self) -> dict:
        out = {
            "zone": self.name,
            "top_depth_ft": U.length_out(self.zone.top_depth, "ft"),
            "net_thickness_ft": U.length_out(self.zone.thickness, "ft"),
            "permeability_mD": U.permeability_out(self.zone.permeability, "mD"),
            "initial_pressure_psi": U.pressure_out(self.zone.initial_pressure, "psi"),
            "threshold_dp_psi": U.pressure_out(
                self.threshold.delta_p_critical, "psi"),
            "threshold_method": self.threshold.method,
            "co2_allocated_MMT": U.mass_out(self.injected_mass, "MMT"),
            "aor_area_acres": self.aor.area_acres,
            "controlling_component": self.aor.controlling_component(),
        }
        if self.pisc is not None:
            out["pisc_years"] = self.pisc.summary()["recommended_pisc"].get(
                "recommended_years", float("nan"))
        return out


@dataclass
class ProjectResult:
    """Everything one project run produced."""

    project: Project
    fluid: fluids.FluidState
    thresholds: list[threshold.ThresholdResult]
    selected_threshold: threshold.ThresholdResult
    aor: delineate.AoRResult
    x: np.ndarray
    y: np.ndarray
    times: np.ndarray
    dp_fields: np.ndarray
    plume_fields: np.ndarray
    pisc: pisc.PISCResult | None = None
    corrective: corrective.CorrectiveActionPlan | None = None
    ve: object = None
    analytical_checks: dict = field(default_factory=dict)
    uncertainty: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    # One entry per injection zone when the project is a stacked completion.
    # Empty for a single-zone project, where `aor` is already the whole story.
    zones: list[ZoneResult] = field(default_factory=list)
    # The AoR as it would stand at each re-evaluation date [146.84(e)].
    series: list = field(default_factory=list)
    # One row per well: the highest bottomhole pressure the model reached and
    # whether it stayed under the declared limit.
    well_pressure: list = field(default_factory=list)

    @property
    def cell_area(self) -> float:
        dx = float(np.median(np.diff(self.x)))
        dy = float(np.median(np.diff(self.y)))
        return abs(dx * dy)

    def summary(self) -> dict:
        out = {
            "project": self.project.summary(),
            "fluids": self.fluid.summary(),
            "threshold": self.selected_threshold.summary(),
            "threshold_all_methods": [t.summary() for t in self.thresholds],
            "aor": self.aor.summary(),
            "analytical_checks": self.analytical_checks,
            "warnings": list(self.warnings),
            # inputs the application did not give, filled from reference values
            "defaults_used": list(getattr(self.project, "defaults_used", []) or []),
        }
        if self.pisc is not None:
            out["pisc"] = self.pisc.summary()
        if self.corrective is not None:
            out["corrective_action"] = self.corrective.summary()
        if self.ve is not None:
            out["ve_solver"] = self.ve.summary()
        if self.uncertainty:
            out["uncertainty"] = self.uncertainty
        # A result can be unpickled, or held in a browser session, across an
        # upgrade that added fields to this class. Reading the newer ones
        # through getattr keeps an older object summarisable instead of
        # raising AttributeError on a field it was built without.
        zones = getattr(self, "zones", None)
        series = getattr(self, "series", None)
        if zones:
            out["injection_zones"] = [z.summary() for z in zones]
            out["zone_allocation"] = self.project.zone_allocation()
        if series:
            rows = delineate.series_growth(series)
            for row, snap in zip(rows, series, strict=False):
                when = self.project.calendar(snap.time)
                if when is not None:
                    row["date"] = str(when)
            out["aor_by_reevaluation_year"] = rows
        wp = getattr(self, "well_pressure", None)
        if wp:
            out["well_pressure"] = wp
        return out

    @property
    def governing_zone(self) -> ZoneResult | None:
        """The zone whose own AoR is the largest, or None if not stacked."""
        return max(self.zones, key=lambda z: z.aor.area_m2) if self.zones else None


def project_crs(p: Project):
    """The coordinate transform a project implies, or None if ungeoreferenced."""
    from .io.exporters import LocalCRS

    cfg = getattr(p, "crs", None) or {}
    if cfg.get("epsg"):
        return LocalCRS(epsg=int(cfg["epsg"]),
                        x_offset=float(cfg.get("x_offset", 0.0)),
                        y_offset=float(cfg.get("y_offset", 0.0)))
    if cfg.get("origin_lon") is not None:
        return LocalCRS(origin_lon=float(cfg["origin_lon"]),
                        origin_lat=float(cfg["origin_lat"]),
                        x_offset=float(cfg.get("x_offset", 0.0)),
                        y_offset=float(cfg.get("y_offset", 0.0)))
    return None


# ==========================================================================
def select_threshold(p: Project, results: list[threshold.ThresholdResult]
                     ) -> threshold.ThresholdResult:
    """Pick the threshold the project asked for, or the protective default.

    A zone's own ``threshold_override`` comes first, then the project's.
    """
    zone_ov = getattr(p.injection_zone, "threshold_override", float("nan"))
    ov = zone_ov if np.isfinite(zone_ov) else p.threshold_override
    if np.isfinite(ov):
        return threshold.ThresholdResult(
            method="user override",
            delta_p_critical=ov,
            p_threshold_abs=p.injection_zone.initial_pressure + ov,
            initial_pressure=p.injection_zone.initial_pressure,
            regime="n/a",
            citation=("value supplied for this zone in the project file"
                      if np.isfinite(zone_ov) else "value supplied in the project file"),
            warnings=["threshold pressure was supplied directly and not "
                      "derived; record the basis in the AoR plan"],
        )
    key = p.threshold_method
    if key in ("auto", "", "recommended"):
        return threshold.recommended(results)
    aliases = {
        "method1": "Method 1", "thornhill": "Method 1",
        "method2": "Method 2", "nicot": "Method 2",
        "method2b": "Method 2b", "variable_density": "Method 2b",
        "mud_column": "Method 3", "method3": "Method 3", "tceq": "Method 3",
        "overpressured": "Over-pressurised",
    }
    want = aliases.get(key)
    if want:
        for r in results:
            if r.method.startswith(want):
                return r
    raise ValueError(f"unknown threshold method {p.threshold_method!r}; "
                     f"use one of {sorted(aliases) + ['auto']}")


# ==========================================================================
def _analytical_model(p: Project) -> AquiferModel:
    fs = p.fluid_state()
    iz = p.injection_zone
    half_x = 0.5 * p.grid_nx * p.cell_size
    half_y = 0.5 * p.grid_ny * p.cell_size
    xs = [w.x for w in p.wells] or [0.0]
    ys = [w.y for w in p.wells] or [0.0]
    cx, cy = float(np.mean(xs)), float(np.mean(ys))

    if p.boundary in ("infinite", "open"):
        bc = Boundary(kind="infinite")
    else:
        side = ("constant_pressure" if p.boundary.startswith("constant")
                else "noflow")
        bc = Boundary(kind="rectangle",
                      xmin=cx - half_x, xmax=cx + half_x,
                      ymin=cy - half_y, ymax=cy + half_y,
                      sides=(side,) * 4)
    return AquiferModel(
        permeability=iz.permeability, thickness=iz.thickness,
        porosity=iz.porosity, total_compressibility=p.total_compressibility(),
        mu_brine=fs.mu_brine, mu_co2=fs.mu_co2, rho_co2=fs.rho_co2,
        initial_pressure=iz.initial_pressure, relperm=p.relperm, boundary=bc)


def _to_analytical_wells(p: Project) -> list[Well]:
    return [Well(name=w.name, x=w.x, y=w.y, schedule=list(w.schedule),
                 kind=w.kind, radius=w.radius) for w in p.wells]


def _to_ve_wells(p: Project) -> list[VEWell]:
    return [VEWell(name=w.name, x=w.x, y=w.y, schedule=list(w.schedule),
                   kind=w.kind, radius=w.radius, max_bhp=w.max_bhp)
            for w in p.wells]


def _grid(p: Project, plume_radius: float = 0.0,
          pressure_radius: float = 0.0, half_width: float = float("nan"),
          fine_half_width: float = float("nan")) -> Grid:
    """Build the VE grid, telescoping outward when the project asks for it.

    A uniform grid cannot serve both masters: the plume needs cells small
    enough to resolve a buoyant tongue, and the pressure front needs a domain
    that reaches well past it.  When ``half_width`` is given (or can be
    inferred from the estimated pressure radius), the grid keeps ``cell_size``
    cells over the well field and grows geometrically outward, which is the
    mesh refinement EPA describes in Section 2.3.1.
    """
    xs = [w.x for w in p.wells] or [0.0]
    ys = [w.y for w in p.wells] or [0.0]
    cx, cy = float(np.mean(xs)), float(np.mean(ys))
    spread = max([abs(w.x - cx) for w in p.wells] + [abs(w.y - cy) for w in p.wells] + [0.0])

    half = half_width if np.isfinite(half_width) else p.grid_half_width
    if not np.isfinite(half):
        if pressure_radius > 0:
            half = 1.35 * (spread + max(pressure_radius, plume_radius))
        else:
            return Grid(nx=p.grid_nx, ny=p.grid_ny, dx=p.cell_size, dy=p.cell_size,
                        x0=cx - 0.5 * p.grid_nx * p.cell_size,
                        y0=cy - 0.5 * p.grid_ny * p.cell_size)
    fine = fine_half_width if np.isfinite(fine_half_width) else p.grid_fine_half_width
    if not np.isfinite(fine):
        fine = min(spread + 1.6 * max(plume_radius, p.cell_size * 5), half)
    return Grid.telescoping(center=(cx, cy), fine_cell=p.cell_size,
                            fine_half_width=fine, total_half_width=half,
                            growth=p.grid_growth)


def _grid_widths(g: Grid) -> tuple[float, float]:
    """Total and fine-cell half-widths of a (possibly telescoping) grid, m."""
    half = 0.5 * max(g.xf[-1] - g.xf[0], g.yf[-1] - g.yf[0])
    fine_cells = g.dxs[g.dxs <= g.dxs.min() * 1.001]
    return float(half), float(0.5 * fine_cells.sum())


def _reaches_edge(plume_fields, dp_fields, plume_level: float, threshold: float,
                  ring: int = 2) -> bool:
    """Does the plume or the above-threshold pressure reach the outer cells?

    Either one there means the domain, not the physics, is drawing that part
    of the AoR line.
    """
    def on_ring(f):
        return bool(f[:, :ring, :].any() or f[:, -ring:, :].any()
                    or f[:, :, :ring].any() or f[:, :, -ring:].any())
    return (on_ring(np.asarray(plume_fields) >= plume_level)
            or on_ring(np.asarray(dp_fields) >= threshold))


# grow the VE domain at most this many times, and never past this many cells
VE_MAX_GROWTH = 3
VE_MAX_CELLS = 250_000


def _ve_boundary_check(ve, threshold_pressure: float) -> dict:
    """How much of the pressure signal is reaching the VE model boundary.

    EPA Section 3.3.3.2 asks that the domain and boundary conditions be tested
    so they "do not result in numerical artifacts that impact the model
    results".  This measures the buildup on the four edge rows over the whole
    run and compares it with the AoR threshold.  Both failure modes matter: a
    no-flow edge that is too close inflates the pressure front, and a
    constant-pressure edge that is too close drains it and truncates the AoR.
    """
    dp = np.asarray(ve.dp)
    faces = {
        "xmin": float(dp[:, :, 0].max()), "xmax": float(dp[:, :, -1].max()),
        "ymin": float(dp[:, 0, :].max()), "ymax": float(dp[:, -1, :].max()),
    }
    worst = max(faces.values())
    frac = worst / threshold_pressure if threshold_pressure else float("nan")
    return {
        "max_dp_on_faces_psi": {k: U.pressure_out(v, "psi") for k, v in faces.items()},
        "threshold_psi": U.pressure_out(threshold_pressure, "psi"),
        "fraction_of_threshold": frac,
        "verdict": (
            "boundary influence negligible" if frac < 0.05 else
            f"ENLARGE THE DOMAIN: pressure buildup at the model edge reaches "
            f"{100 * frac:.0f} % of the AoR threshold, so the boundary "
            "condition is shaping the pressure front"),
    }


def analytical_cross_checks(p: Project) -> dict:
    """Closed-form sanity numbers that should accompany any AoR.

    EPA suggests analytical models as "a relatively simple comparative check
    on numerical modeling results" (Section 2.3.2).  These are cheap, they
    take five seconds to explain, and if the numerical AoR disagrees with all
    of them by a large factor something is wrong with the numerical model.
    """
    fs = p.fluid_state()
    iz = p.injection_zone
    inp = PlumeInputs(iz.thickness, iz.porosity, iz.permeability,
                      fs.rho_co2, fs.mu_co2, fs.rho_brine, fs.mu_brine,
                      relperm=p.relperm)
    m = p.total_injected_mass()
    q_res = (m / max(p.injection_end(), 1e-9)) / fs.rho_co2 if m else 0.0
    gamma = endpoint_mobility_ratio(p.relperm, fs.mu_co2, fs.mu_brine)
    return {
        "co2_density_kg_m3": fs.rho_co2,
        "endpoint_mobility_ratio_gamma": gamma,
        "gravity_number": gravity_number(iz.permeability, iz.thickness,
                                         fs.delta_rho, fs.mu_co2, max(q_res, 1e-30)),
        "volumetric_radius_ft": U.length_out(VolumetricPlume(inp).radius(m), "ft"),
        "nordbotten_celia_radius_ft": U.length_out(
            NordbottenCeliaPlume(inp, gamma).radius(m), "ft"),
        "buckley_leverett_radius_ft": U.length_out(
            BuckleyLeverettPlume(inp).radius(m), "ft"),
        "residual_trapping_limit_radius_ft": U.length_out(
            residual_trapping_limit_radius(m, fs.rho_co2, iz.porosity,
                                           iz.thickness, p.relperm.sgr), "ft"),
        "note": (
            "These are single-well, homogeneous, horizontal estimates for the "
            "total injected mass. They bracket rather than replace the model: "
            "the volumetric radius is a floor, the Nordbotten-Celia nose "
            "accounts for the unfavourable mobility ratio, and the "
            "residual-trapping radius is the mass-balance ceiling on the "
            "ultimate footprint."),
    }


# ==========================================================================
def run_zone(p: Project, *, penetrations: list | None = None,
             progress: Callable[[str], None] | None = None,
             label: str = "") -> ProjectResult:
    """Execute the AoR/PISC workflow for a project with one injection zone.

    :func:`run` is the entry point; this is the single-zone body it calls, once
    per zone of a stacked completion.
    """
    say = progress or (lambda _msg: None)
    warnings = list(p.warnings)

    say("evaluating fluid properties")
    fs = p.fluid_state()
    warnings.extend(fs.notes)

    say("computing threshold pressure")
    th_all = threshold_methods(p)
    th = select_threshold(p, th_all)
    warnings.extend(th.warnings)

    say("running the flow model")
    checks = analytical_cross_checks(p)
    ve_result = None
    _grid_areas = None

    if p.engine == "ve":
        from .analytical.pressure import radius_of_investigation
        _m = _analytical_model(p)
        _q = max((sum(abs(_m.reservoir_rate(w, float(t))) for w in _to_analytical_wells(p))
                  for t in p.output_times), default=0.0)
        _r_press = max((radius_of_investigation(_m, float(t), th.delta_p_critical, _q)
                        for t in p.output_times), default=0.0)
        # The first domain comes from the analytical pressure and plume radii.
        # A buoyant plume can drift much further than either, so if the plume
        # or the above-threshold pressure reaches the outer cells the domain
        # is doubled (and the fine region widened) and the model run again.
        half_o = fine_o = float("nan")
        grown = []
        for attempt in range(VE_MAX_GROWTH + 1):
            g = _grid(p, plume_radius=U.length(checks["nordbotten_celia_radius_ft"], "ft"),
                      pressure_radius=_r_press, half_width=half_o, fine_half_width=fine_o)
            run_warnings: list[str] = []
            iz = p.injection_zone
            props = GridProperties(
                g, permeability=iz.permeability, porosity=iz.porosity,
                thickness=iz.thickness,
                anisotropy_y_over_x=1.0)
            if iz.dip_degrees:
                props.add_dip(iz.dip_degrees, iz.dip_azimuth)
            for f in p.faults:
                props.add_sealing_fault(f["points"], multiplier=f["multiplier"])
                run_warnings.append(
                    f"fault {f['name']!r} applied with transmissibility multiplier "
                    f"{f['multiplier']:g} along {len(f['points'])} trace points")
            solver = VESolver(
                props, rho_co2=fs.rho_co2, mu_co2=fs.mu_co2, rho_brine=fs.rho_brine,
                mu_brine=fs.mu_brine, total_compressibility=p.total_compressibility(),
                reference_pressure=iz.initial_pressure, relperm=p.relperm,
                # a VE grid is finite, so an "infinite" project maps to a
                # far-field constant-pressure edge, the closest finite analogue
                boundary=("noflow" if p.boundary.startswith("noflow")
                          else "constant_pressure"))
            ve_result = solver.run(_to_ve_wells(p), end_time=p.end_time,
                                   output_times=p.output_times)
            run_warnings.extend(ve_result.warnings)
            plume_fields = np.array([
                ve_result.saturation_proxy(i, props, p.relperm)
                for i in range(len(ve_result.times))])
            half_now, fine_now = _grid_widths(g)
            # a closed (no-flow) project is bounded on purpose: do not grow it
            if (p.boundary.startswith("noflow") or attempt == VE_MAX_GROWTH
                    or not _reaches_edge(plume_fields, ve_result.dp, p.plume_cutoff,
                                         th.delta_p_critical)):
                break
            half_o, fine_o = 2.0 * half_now, min(1.6 * fine_now, 2.0 * half_now)
            trial = _grid(p, half_width=half_o, fine_half_width=fine_o)
            if trial.ncells > VE_MAX_CELLS:
                run_warnings.append(
                    f"the AoR reaches the model edge and the domain was not enlarged "
                    f"further: the next grid would need {trial.ncells:,} cells "
                    f"(limit {VE_MAX_CELLS:,}). Set model.grid.half_width and cell_size by hand.")
                break
            grown.append((U.length_out(half_now, "mi"), U.length_out(half_o, "mi")))
        warnings.extend(run_warnings)
        if grown:
            warnings.append(
                "VE domain enlarged automatically because the plume or the pressure "
                "front reached the model edge: half-width "
                + " then ".join(f"{a:.1f} to {b:.1f} mi" for a, b in grown)
                + f" ({g.nx} x {g.ny} cells).")
        checks["domain_growth"] = {"steps_mi": grown, "half_width_mi": U.length_out(_grid_widths(g)[0], "mi")}
        x, y = g.xc, g.yc
        _grid_areas = g.areas
        times = ve_result.times
        dp_fields = ve_result.dp
        xs0 = [w.x for w in p.wells] or [0.0]
        ys0 = [w.y for w in p.wells] or [0.0]
        res_check = g.resolution_check(
            U.length(checks["nordbotten_celia_radius_ft"], "ft"),
            center=(float(np.mean(xs0)), float(np.mean(ys0))))
        checks["grid_resolution"] = res_check
        if res_check["verdict"] != "adequate":
            warnings.append(res_check["verdict"])
        checks["boundary_influence"] = _ve_boundary_check(
            ve_result, th.delta_p_critical)
        if checks["boundary_influence"]["verdict"] != "boundary influence negligible":
            warnings.append(checks["boundary_influence"]["verdict"])

    elif p.engine in ("analytical", "analytic"):
        model = _analytical_model(p)
        wells = _to_analytical_wells(p)
        times = p.output_times
        aor_prelim = delineate.delineate_analytical(
            model, wells, th.delta_p_critical, times,
            plume_criterion=p.plume_criterion)
        warnings.extend(aor_prelim.warnings)
        # rebuild the fields on the grid the delineation settled on so the
        # PISC and corrective-action steps see the same numbers
        reach = U.length(aor_prelim.metadata["evaluation_half_width_mi"], "mi")
        xs = [w.x for w in p.wells] or [0.0]
        ys = [w.y for w in p.wells] or [0.0]
        x = np.linspace(min(xs) - reach, max(xs) + reach, p.grid_nx)
        y = np.linspace(min(ys) - reach, max(ys) + reach, p.grid_ny)
        dp_fields, _ = model.pressure_grid(x, y, times, wells)
        X, Y = np.meshgrid(x, y)
        plume_fields = np.zeros((len(times), len(y), len(x)))
        for i, t in enumerate(times):
            f = np.zeros_like(X)
            for w in wells:
                if w.kind != "injector":
                    continue
                r = model.front_radius(w, float(t))
                if r > 0:
                    f = np.maximum(f, (np.hypot(X - w.x, Y - w.y) <= r).astype(float))
            plume_fields[i] = f
        checks["boundary_influence"] = model.influence_check(
            wells, float(times[-1]), th.delta_p_critical)
    else:
        raise ValueError(
            f"engine {p.engine!r} is not run by this function; import the "
            "simulation with containment.io.load_grid_csv and call "
            "containment.delineate.delineate directly")

    say("delineating the AoR")
    plume_level = (p.plume_cutoff if p.engine == "ve" else 0.5)
    aor = delineate.delineate(
        x, y,
        dp_field=delineate.envelope(dp_fields),
        threshold_pressure=th.delta_p_critical,
        plume_field=delineate.envelope(plume_fields),
        plume_level=plume_level,
        plume_criterion=p.plume_criterion,
        method=("vertical-equilibrium numerical model" if p.engine == "ve"
                else "analytical superposition"),
        wells=[w.name for w in p.wells if w.kind == "injector"],
        metadata={"engine": p.engine, "threshold_method": th.method},
    )
    warnings.extend(aor.warnings)

    say("computing PISC metrics")
    pisc_res = pisc.analyse(
        times, plume_fields=plume_fields, plume_level=plume_level,
        dp_fields=dp_fields, threshold_pressure=th.delta_p_critical,
        cell_area=(_grid_areas if _grid_areas is not None
                   else abs(float(np.median(np.diff(x))) * float(np.median(np.diff(y))))),
        injection_end=p.injection_end(), x=x, y=y,
        origins=[(w.x, w.y) for w in p.wells if w.kind == "injector"])
    warnings.extend(pisc_res.warnings)

    ca = None
    if penetrations is None and p.penetrations_csv:
        say("loading artificial penetrations")
        penetrations = corrective.load_wells_csv(
            p.penetrations_csv, unit=p.penetrations_unit, crs=project_crs(p))
    if penetrations:
        say("screening artificial penetrations")
        cz_top = (p.confining_zone.top_depth if np.isfinite(p.confining_zone.top_depth)
                  else p.injection_zone.top_depth - U.length(100, "ft"))
        cz_base = (p.confining_zone.base_depth if np.isfinite(p.confining_zone.base_depth)
                   else p.injection_zone.top_depth)
        ca = corrective.screen(
            penetrations, aor, cz_top, cz_base,
            injectors=[(w.x, w.y) for w in p.wells if w.kind == "injector"])
        ca = corrective.arrival_times(
            ca, x, y, times, plume_fields=plume_fields, plume_level=plume_level,
            dp_fields=dp_fields, threshold_pressure=th.delta_p_critical)
        warnings.extend(ca.warnings)

    if p.engine == "ve":
        well_rows = well_pressure_check(p, ve_result=ve_result)
    else:
        well_rows = well_pressure_check(
            p, model=_analytical_model(p), wells=_to_analytical_wells(p),
            times=times)
    for row in well_rows:
        if row["verdict"] == "EXCEEDS LIMIT":
            warnings.append(
                f"well {row['well']} reaches {row['max_bhp_psi']:,.0f} psi at "
                f"year {row['year_of_max']:,.1f}, above its declared limit of "
                f"{row['limit_psi']:,.0f} psi. The schedule is not injectable "
                "as written, so the AoR below is not this project's.")

    if label:
        aor.metadata["zone"] = label

    return ProjectResult(
        project=p, fluid=fs, thresholds=th_all, selected_threshold=th,
        aor=aor, x=x, y=y, times=times, dp_fields=dp_fields,
        plume_fields=plume_fields, pisc=pisc_res, corrective=ca,
        ve=ve_result, analytical_checks=checks, warnings=warnings,
        well_pressure=well_rows,
    )


# ==========================================================================
def well_pressure_check(p: Project, ve_result=None, model=None,
                        wells=None, times=None) -> list[dict]:
    """Highest bottomhole pressure per well, against the declared limit.

    A rate schedule that cannot be injected is not a plan, and the AoR that
    follows from an unachievable rate is not this project's AoR. Where a well
    declares `max_bhp` the run now says whether the schedule fits inside it.
    A well with no declared limit is reported without a verdict rather than
    quietly passed.
    """
    rows: list[dict] = []
    for w in p.wells:
        if w.kind == "monitor":
            continue
        peak, when = float("nan"), float("nan")
        if ve_result is not None and getattr(ve_result, "bhp", None):
            series = np.asarray(ve_result.bhp.get(w.name, []), float)
            if series.size:
                i = int(np.nanargmax(series))
                peak = float(series[i])
                when = float(np.asarray(ve_result.times)[i])
        elif model is not None and wells is not None and times is not None:
            match = [x for x in wells if x.name == w.name]
            if match:
                vals = [model.bottomhole_pressure(match[0], float(t), wells)
                        for t in times]
                i = int(np.nanargmax(vals))
                peak, when = float(vals[i]), float(times[i])
        if not np.isfinite(peak):
            continue

        row = {"well": w.name, "kind": w.kind,
               "max_bhp_psi": U.pressure_out(peak, "psi"),
               "year_of_max": U.time_out(when, "yr")}
        date = p.calendar(when)
        if date is not None:
            row["date_of_max"] = str(date)
        held = ((getattr(ve_result, "meta", None) or {}).get("throttled") or {}).get(w.name)
        if np.isfinite(w.max_bhp):
            row["limit_psi"] = U.pressure_out(w.max_bhp, "psi")
            row["margin_psi"] = U.pressure_out(w.max_bhp - peak, "psi")
            if held:
                # the VE model held this well at its limit by cutting the rate
                row["verdict"] = "held at limit (throttled)"
                row["throttled_years"] = round(held["years"], 1)
                row["injected_share"] = round(held["injected_share"], 3)
            else:
                row["verdict"] = ("pass" if peak <= w.max_bhp * (1 + 1e-9)
                                  else "EXCEEDS LIMIT")
        else:
            row["limit_psi"] = float("nan")
            row["verdict"] = "no limit declared"
        rows.append(row)
    return rows


def reevaluation_times(p: Project) -> np.ndarray:
    """The dates the AoR is delineated at, in seconds.

    40 CFR 146.84(e) sets the cadence: at least every five years, and the
    project file may ask for a different one.
    """
    step = U.time(float(p.aor_reevaluation_years or 5.0), "yr")
    end = float(p.end_time)
    if step <= 0 or end <= 0:
        return np.array([end])
    marks = np.arange(step, end + 1e-9, step)
    if marks.size == 0 or marks[-1] < end - 1e-6:
        marks = np.append(marks, end)
    return marks


def threshold_methods(p: Project) -> list[threshold.ThresholdResult]:
    """Every threshold method for this project's (single) injection zone."""
    th_all = threshold.compare_methods(
        p_usdw=(p.usdw.initial_pressure if np.isfinite(p.usdw.initial_pressure)
                else fluids.hydrostatic_pressure(p.usdw.base_depth)),
        p_inj=p.injection_zone.initial_pressure,
        depth_usdw=p.usdw.base_depth,
        depth_inj=p.threshold_depth,
        temperature_inj=p.injection_zone.temperature,
        temperature_usdw=(p.usdw.temperature if np.isfinite(p.usdw.temperature)
                          else U.temperature(70, "F")),
        salinity_inj=p.injection_zone.salinity,
        salinity_usdw=(p.usdw.salinity if np.isfinite(p.usdw.salinity) else 0.0005),
        mud_weight_ppg=p.mud_weight_ppg, gel_strength=p.gel_strength,
        mud_datum_depth=(p.mud_datum_depth if np.isfinite(p.mud_datum_depth)
                         else None))
    if p.offshore:
        offshore_wording(th_all, p.reference_label)
    return th_all


def model_years(res) -> list[float]:
    """The model output times of a result, in years, for a time picker."""
    zones = getattr(res, "zones", []) or []
    t = zones[0].times if zones else res.times
    return [float(U.time_out(v, "yr")) for v in np.asarray(t, float)]


def view_at(p: Project, res, year: float, show: str = "now") -> delineate.AoRResult:
    """The plume, the pressure front and the AoR at one model year, for the maps.

    ``show="now"`` draws the CO2 plume and the above-threshold pressure where
    they are at that year (the pressure front shrinks after injection stops),
    with the AoR as it stands at that year: the largest extent up to then.
    ``show="to_date"`` draws all three as the largest extent up to that year,
    which is the Area of Review a reviewer would approve if the project were
    evaluated then (EPA 816-R-13-005; 40 CFR 146.84(e)).

    A stacked completion is sliced zone by zone, on each zone's own grid and
    threshold, and the pieces are combined as the project AoR is.
    """
    from shapely.ops import unary_union

    level = p.plume_cutoff if p.engine == "ve" else 0.5
    zones = getattr(res, "zones", []) or []
    if zones:
        sources = [(z.x, z.y, z.times, z.dp_fields, z.plume_fields,
                    z.threshold.delta_p_critical, z.plume_level) for z in zones]
    else:
        sources = [(res.x, res.y, res.times, res.dp_fields, res.plume_fields,
                    res.selected_threshold.delta_p_critical, level)]
    want = U.time(float(year), "yr")
    plumes, fronts, aors, at_years, fronts_now = [], [], [], [], []
    for x, y, times, dpf, plf, thr, lev in sources:
        t = np.asarray(times, float)
        i = max(int(np.searchsorted(t, want + 1e-6, side="right")) - 1, 0)
        at_years.append(float(U.time_out(t[i], "yr")))
        dpf = None if dpf is None else np.asarray(dpf)
        plf = None if plf is None else np.asarray(plf)
        cum = delineate.delineate(
            x, y, threshold_pressure=thr, plume_level=lev,
            dp_field=None if dpf is None else delineate.envelope(dpf[:i + 1]),
            plume_field=None if plf is None else delineate.envelope(plf[:i + 1]))
        aors.append(cum.aor)
        now = delineate.delineate(
            x, y, threshold_pressure=thr, plume_level=lev,
            dp_field=None if dpf is None else dpf[i],
            plume_field=None if plf is None else plf[i])
        fronts_now.append(now.pressure_front)
        if show == "now":
            plumes.append(now.plume)
            fronts.append(now.pressure_front)
        else:
            plumes.append(cum.plume)
            fronts.append(cum.pressure_front)

    def union(gs):
        gs = [g for g in gs if g is not None and not g.is_empty]
        return unary_union(gs) if gs else delineate.MultiPolygon()

    shown = max(at_years) if at_years else float(year)
    words = ("where they are" if show == "now" else "largest extent up to then")
    meta = {"year": shown, "show": show}
    # After injection stops the pressure falls: the above-threshold area at
    # this year can be much smaller than the largest so far. Keep it so a map
    # can draw it as an outline inside the AoR, which never shrinks.
    front_now, front_max = union(fronts_now), union(fronts)
    if (show != "now" and not front_max.is_empty
            and front_now.area < 0.98 * front_max.area):
        meta["front_now"] = front_now
        meta["front_now_acres"] = U.area_out(front_now.area, "acres")
    return delineate.AoRResult(
        plume=union(plumes), pressure_front=union(fronts), aor=union(aors),
        threshold_pressure=float(sources[0][5]),
        plume_criterion=p.plume_criterion,
        method=f"year {shown:,.1f}: plume and pressure front {words}; "
               "AoR = largest extent up to this year",
        injection_wells=[w.name for w in p.wells if w.kind == "injector"],
        metadata=meta)


def choose_offshore_reference(p: Project) -> Project:
    """Offshore 'most_protective': compute the threshold against the mud line
    and against the base of the first permeable stratum, and keep the reference
    with the lower critical pressure (the larger, more protective AoR). On a
    stacked completion the lowest over every zone decides. Returns the project
    with that reference in place and the comparison recorded."""
    from .config import OFFSHORE_REFERENCES

    alts = (p.offshore or {}).get("alternatives")
    if not alts:
        return p
    zones = list(zip(p.zones, p.seals, strict=True)) if p.is_stacked else \
        [(p.injection_zone, p.confining_zone)]
    rows = []
    for key, ref_zone in alts.items():
        off = {**p.offshore, "reference": key, "label": OFFSHORE_REFERENCES[key]}
        best = None
        for z, seal in zones:
            sub = replace(p, usdw=ref_zone, offshore=off, injection_zone=z,
                          confining_zone=seal, injection_zones=[], confining_zones=[])
            th = select_threshold(sub, threshold_methods(sub))
            if best is None or th.delta_p_critical < best.delta_p_critical:
                best = th
        rows.append({"key": key, "reference": OFFSHORE_REFERENCES[key],
                     "depth_ft": round(U.length_out(ref_zone.base_depth, "ft"), 1),
                     "threshold_psi": round(best.delta_p_psi, 1),
                     "method": best.method.split(" - ")[0]})
    chosen = min(rows, key=lambda r: r["threshold_psi"])
    for r in rows:
        r["used"] = r is chosen
    off = {k: v for k, v in p.offshore.items() if k != "alternatives"}
    off.update(reference=chosen["key"], label=chosen["reference"],
               comparison=[{k: v for k, v in r.items() if k != "key"} for r in rows])
    return replace(p, usdw=alts[chosen["key"]], offshore=off)


def offshore_wording(results, label: str) -> None:
    """Offshore, the threshold is measured against the mud line (or the first
    permeable stratum below it), not a USDW: say so in every method's inputs
    and warnings, so no table or report calls the seafloor a USDW."""
    for r in results:
        r.inputs = {k.replace("usdw", "reference"): v for k, v in r.inputs.items()}
        r.warnings = [w.replace("the USDW", f"the {label}").replace("USDW", label)
                      for w in r.warnings]
        r.citation = (r.citation + "; offshore reference depth "
                      "(16 TAC 4.101, 5.206(b)(2))")


def run(p: Project, *, penetrations: list | None = None,
        progress: Callable[[str], None] | None = None,
        run_uncertainty: bool | None = None) -> ProjectResult:
    """Execute the whole AoR/PISC workflow, over every injection zone.

    A single-zone project runs exactly as it always has. A project with
    stacked injection zones is run once per zone, each on its own grid with
    its own fluids and its own threshold pressure, and the project AoR is the
    geometric union of the zone AoRs: the rule protects a USDW from fluid
    movement out of any injection zone, so ground that only the deepest zone
    reaches is still inside the Area of Review.

    Either way the result carries a series of AoRs on the re-evaluation
    cadence, so the growth a reviewer will ask about is already computed.
    """
    say = progress or (lambda _msg: None)
    marks = reevaluation_times(p)
    # Make the model report at the dates the rule asks about. Without this the
    # five-year AoR falls back to whichever output time happens to precede it,
    # and a series meant to read 5, 10, 15 reads 3.8, 9.2, 14.6 instead.
    p = replace(p, output_times=np.unique(np.concatenate(
        [np.asarray(p.output_times, float), marks])))
    p = choose_offshore_reference(p)

    if not p.is_stacked:
        result = run_zone(p, penetrations=penetrations, progress=progress)
        say("delineating the AoR through time")
        result.series = delineate.aor_series(
            result.x, result.y, result.times,
            dp_fields=result.dp_fields,
            threshold_pressure=result.selected_threshold.delta_p_critical,
            plume_fields=result.plume_fields,
            plume_level=(p.plume_cutoff if p.engine == "ve" else 0.5),
            plume_criterion=p.plume_criterion, at_times=marks,
            wells=[w.name for w in p.wells if w.kind == "injector"])
    else:
        result = _run_stacked(p, marks, penetrations=penetrations, progress=progress)

    do_unc = (p.uncertainty.get("enabled", False)
              if run_uncertainty is None else run_uncertainty)
    if do_unc:
        say("running uncertainty analysis")
        result.uncertainty = run_uncertainty_analysis(
            p, result.selected_threshold, progress=progress)
    return result


def _run_stacked(p: Project, marks: np.ndarray, *, penetrations=None,
                 progress=None) -> ProjectResult:
    """Run every injection zone, then union the delineations."""
    say = progress or (lambda _msg: None)
    zones, seals = p.zones, p.seals
    warnings = list(p.warnings)
    if np.isfinite(p.threshold_datum_depth):
        warnings.append(
            f"threshold.datum_depth = {U.length_out(p.threshold_datum_depth, 'ft'):,.0f} ft "
            f"is used for every injection zone. On a stacked completion each zone "
            f"is normally evaluated at its own depth: use threshold.datum: top, or "
            f"leave the datum out for each zone's mid-point.")
    per_zone: list[ZoneResult] = []
    zone_runs: list[ProjectResult] = []

    for i, z in enumerate(zones):
        name = z.name or f"zone {i + 1}"
        say(f"running {name} ({i + 1} of {len(zones)})")
        zw = p.zone_wells(i)
        sub = replace(
            p, injection_zone=z, confining_zone=seals[i],
            injection_zones=[], confining_zones=[],
            relperm=z.relperm if z.relperm is not None else p.relperm,
            output_times=zone_output_times(p, zw, marks),
            wells=zw, uncertainty={}, warnings=[])
        r = run_zone(sub, progress=None, label=name)
        zone_runs.append(r)

        series = delineate.aor_series(
            r.x, r.y, r.times, dp_fields=r.dp_fields,
            threshold_pressure=r.selected_threshold.delta_p_critical,
            plume_fields=r.plume_fields,
            plume_level=(p.plume_cutoff if p.engine == "ve" else 0.5),
            plume_criterion=p.plume_criterion, at_times=marks,
            wells=[w.name for w in sub.wells if w.kind == "injector"])

        per_zone.append(ZoneResult(
            name=name, zone=z, threshold=r.selected_threshold, aor=r.aor,
            x=r.x, y=r.y, times=r.times, dp_fields=r.dp_fields,
            plume_fields=r.plume_fields,
            plume_level=(p.plume_cutoff if p.engine == "ve" else 0.5),
            injected_mass=sub.total_injected_mass(),
            pisc=r.pisc, series=series,
            warnings=[f"[{name}] {w}" for w in r.warnings]))
        warnings.extend(per_zone[-1].warnings)

    say("combining the zone delineations")
    combined = delineate.combine([zr.aor for zr in per_zone],
                                 labels=[zr.name for zr in per_zone])
    warnings.extend(combined.warnings)

    # The AoR at each re-evaluation date is likewise the union over zones.
    series = []
    for k in range(min(len(zr.series) for zr in per_zone)):
        snaps = [zr.series[k] for zr in per_zone]
        series.append(delineate.AoRSnapshot(
            time=max(sn.time for sn in snaps),
            aor=delineate.combine([sn.aor for sn in snaps],
                                  labels=[zr.name for zr in per_zone],
                                  method="union of zone delineations")))

    # Grid-based products need one grid. The zone with the largest AoR is the
    # one a reviewer argues about, so its fields are the ones carried forward,
    # and the choice is recorded rather than left implicit.
    lead = max(range(len(per_zone)), key=lambda i: per_zone[i].aor.area_m2)
    base = zone_runs[lead]
    if len(per_zone) > 1:
        warnings.append(
            f"pressure and plume fields, PISC timing and corrective-action "
            f"arrival times are reported from {per_zone[lead].name}, the zone "
            f"with the largest AoR. Per-zone numbers are in the zone table; a "
            f"penetration's arrival time in another zone may be earlier.")

    # PISC: the site cannot be released until every zone has stabilised.
    pisc_res, pisc_zone = base.pisc, per_zone[lead].name
    # Larger AoRs first, so a tie (two zones never stabilising, or the same
    # year) stays with the bigger zone.
    for zr in sorted(per_zone, key=lambda z: -z.aor.area_m2):
        if zr.pisc is None or pisc_res is None:
            continue
        if _pisc_years(zr.pisc) > _pisc_years(pisc_res):
            pisc_res, pisc_zone = zr.pisc, zr.name
    if pisc_res is not None and pisc_zone != per_zone[lead].name:
        warnings.append(
            f"PISC is governed by {pisc_zone}, not by the zone with the "
            f"largest AoR: the last zone to stabilise sets the timeframe, and a "
            f"zone that does not stabilise in the model leaves PISC not "
            f"demonstrated.")

    ca = None
    if penetrations is None and p.penetrations_csv:
        penetrations = corrective.load_wells_csv(
            p.penetrations_csv, unit=p.penetrations_unit, crs=project_crs(p))
    if penetrations:
        say("screening artificial penetrations")
        shallowest = min(zones, key=lambda z: (z.top_depth if np.isfinite(z.top_depth)
                                               else np.inf))
        seal = seals[zones.index(shallowest)]
        cz_top = (seal.top_depth if np.isfinite(seal.top_depth)
                  else shallowest.top_depth - U.length(100, "ft"))
        cz_base = (seal.base_depth if np.isfinite(seal.base_depth)
                   else shallowest.top_depth)
        ca = corrective.screen(
            penetrations, combined, cz_top, cz_base,
            injectors=[(w.x, w.y) for w in p.wells if w.kind == "injector"])
        ca = corrective.arrival_times(
            ca, base.x, base.y, base.times, plume_fields=base.plume_fields,
            plume_level=(p.plume_cutoff if p.engine == "ve" else 0.5),
            dp_fields=base.dp_fields,
            threshold_pressure=base.selected_threshold.delta_p_critical)
        warnings.extend(ca.warnings)

    return ProjectResult(
        project=p, fluid=base.fluid, thresholds=base.thresholds,
        selected_threshold=base.selected_threshold, aor=combined,
        x=base.x, y=base.y, times=base.times, dp_fields=base.dp_fields,
        plume_fields=base.plume_fields, pisc=pisc_res, corrective=ca,
        ve=base.ve, analytical_checks=base.analytical_checks,
        warnings=list(dict.fromkeys(warnings)),
        zones=per_zone, series=series,
        # Every zone shares the same wellbore, so the binding pressure is the
        # highest any zone's run demanded of it.
        well_pressure=_worst_well_pressure(zone_runs),
    )


def _worst_well_pressure(runs) -> list:
    worst: dict[str, dict] = {}
    for r in runs:
        for row in getattr(r, "well_pressure", []) or []:
            cur = worst.get(row["well"])
            if cur is None or row["max_bhp_psi"] > cur["max_bhp_psi"]:
                worst[row["well"]] = row
    return list(worst.values())


def _pisc_years(r) -> float:
    try:
        v = r.summary()["recommended_pisc"].get("recommended_years", float("nan"))
        # A zone that never stabilises in the model holds the site open
        # longest, so it must win: the project is then "not demonstrated".
        return float(v) if np.isfinite(v) else float("inf")
    except Exception:
        return -1.0


# ==========================================================================
def run_uncertainty_analysis(p: Project, th: threshold.ThresholdResult,
                             progress: Callable[[str], None] | None = None
                             ) -> dict:
    """Tornado + Monte Carlo on AoR area, using the fast analytical engine.

    The analytical engine is used deliberately: a few hundred realisations of
    a vertical-equilibrium model is hours, a few hundred analytical
    realisations is seconds, and the *ranking* of parameter importance and the
    *spread* of AoR area are what the sensitivity requirement asks for.
    Re-run the two or three most influential cases through the VE model to
    confirm.
    """
    from . import uncertainty as unc

    cfg = p.uncertainty or {}
    n = int(cfg.get("realisations", 200))
    spread = float(cfg.get("spread", 0.5))
    seed = cfg.get("seed", 0)

    iz = p.injection_zone
    rp = p.relperm
    # Relative permeability is only varied when it is the Brooks-Corey form
    # the parameters below name; another model keeps its base values.
    corey_like = all(hasattr(rp, a) for a in ("swr", "sgr", "krg0", "m"))
    params = unc.default_parameters(
        permeability_md=U.permeability_out(iz.permeability, "mD"),
        porosity=iz.porosity,
        thickness_ft=U.length_out(iz.thickness, "ft"),
        compressibility_1_psi=U.compressibility_out(p.total_compressibility(), "1/psi"),
        spread=spread,
        initial_pressure_psi=U.pressure_out(iz.initial_pressure, "psi"),
        temperature_f=U.temperature_out(iz.temperature, "F"),
        salinity_ppm=(iz.salinity * 1e6 if np.isfinite(iz.salinity) else None),
        swr=(rp.swr if corey_like else None),
        sgr=(rp.sgr if corey_like else None),
        krg0=(rp.krg0 if corey_like else None),
        corey=(float(rp.m) if corey_like else None),
        threshold_psi=U.pressure_out(th.delta_p_critical, "psi"))

    base_times = p.output_times
    wells = _to_analytical_wells(p)
    xs = [w.x for w in wells] or [0.0]
    ys = [w.y for w in wells] or [0.0]

    def _case_fluid(case: dict):
        """Fluid state for this realisation.

        Pressure, temperature and salinity move CO2 density through the
        equation of state, so a realisation that changed them and kept the
        base fluid would be varying the label and not the physics.
        """
        pres = (U.pressure(case["initial_pressure_psi"], "psi")
                if "initial_pressure_psi" in case else iz.initial_pressure)
        temp = (U.temperature(case["temperature_f"], "F")
                if "temperature_f" in case else iz.temperature)
        sal = (case["salinity_ppm"] * 1e-6
               if "salinity_ppm" in case else iz.salinity)
        return fluids.evaluate(pres, temp, sal), pres

    def _case_relperm(case: dict):
        if not corey_like or "sgr" not in case:
            return rp
        from .analytical.relperm import BrooksCorey

        return BrooksCorey(swr=case.get("swr", rp.swr), sgr=case["sgr"],
                           krw0=getattr(rp, "krw0", 1.0),
                           krg0=case.get("krg0", rp.krg0),
                           m=case.get("corey", rp.m), n=case.get("corey", rp.n))

    def _case_threshold(case: dict) -> float:
        return (U.pressure(case["threshold_psi"], "psi")
                if "threshold_psi" in case else th.delta_p_critical)

    def build(case: dict) -> AquiferModel:
        fs, pres = _case_fluid(case)
        return AquiferModel(
            permeability=U.permeability(case["permeability_md"], "mD"),
            thickness=U.length(case["thickness_ft"], "ft"),
            porosity=case["porosity"],
            total_compressibility=U.compressibility(case["compressibility_1_psi"], "1/psi"),
            mu_brine=fs.mu_brine, mu_co2=fs.mu_co2, rho_co2=fs.rho_co2,
            initial_pressure=pres, relperm=_case_relperm(case),
            boundary=Boundary(kind="infinite"))

    def area_of(case: dict) -> float:
        m = build(case)
        r = delineate.delineate_analytical(m, wells, _case_threshold(case),
                                           base_times, n=121, max_expansions=4)
        return r.area_acres

    say = progress or (lambda _m: None)
    say("  tornado (one parameter at a time)")
    tor = unc.tornado(area_of, params, metric="AoR area (acres)")

    say(f"  Monte Carlo ({n} Latin-hypercube realisations)")
    # One fixed grid for every realisation, so the cell-wise inclusion
    # probability is comparable across the ensemble.  Size it from the widest
    # AoR the tornado produced, with room to spare.
    widest = max([tor.base_value] + [max(r["low_value"], r["high_value"])
                                     for r in tor.rows])
    reach = 2.5 * float(np.sqrt(U.area(max(widest, 1.0), "acres") / np.pi))
    grid_x = np.linspace(min(xs) - reach, max(xs) + reach, 121)
    grid_y = np.linspace(min(ys) - reach, max(ys) + reach, 121)
    GX, GY = np.meshgrid(grid_x, grid_y)

    def evaluate(case: dict) -> dict:
        m = build(case)
        _, dp_max = m.pressure_grid(grid_x, grid_y, base_times, wells)
        inside = dp_max >= _case_threshold(case)
        for w in wells:
            if w.kind != "injector":
                continue
            r = max(m.front_radius(w, float(t)) for t in base_times)
            inside |= np.hypot(GX - w.x, GY - w.y) <= r
        # contoured, as the tornado's areas are, so the two compare directly
        area = delineate.field_to_polygons(
            grid_x, grid_y, inside.astype(float), 0.5).area
        return {"aor_area_acres": U.area_out(area, "acres"), "inside": inside}

    mc = unc.monte_carlo(evaluate, params, n=n, seed=seed,
                         grid_x=grid_x, grid_y=grid_y)

    # Spread relative to the ensemble's own base case, which is the number
    # that transfers across engines. The absolute acreages do not.
    pct = mc.percentiles("aor_area_acres")
    base = tor.base_value or float("nan")
    ratios = {k: (v / base if base else float("nan")) for k, v in pct.items()}

    caveat = (
        "This ensemble was run on the ANALYTICAL engine (homogeneous, "
        "horizontal, injection period only), because a few hundred "
        "vertical-equilibrium realisations is hours of compute. Its absolute "
        "areas are therefore NOT directly comparable to a vertical-equilibrium "
        "AoR, which additionally carries dip, heterogeneity and post-injection "
        "buoyant migration. What transfers is the ranking of parameter "
        "importance and the RELATIVE spread (see percentile_ratio_to_base). "
        "Re-run the two or three most influential cases through the chosen "
        "engine before quoting a probabilistic boundary."
        if p.engine != "analytical" else
        "This ensemble was run on the same analytical engine as the base case, "
        "so its absolute areas are directly comparable.")

    return {
        "engine_used": "analytical",
        "project_engine": p.engine,
        "comparability": caveat,
        "base_case_area_acres": base,
        "percentile_ratio_to_base": ratios,
        "tornado": tor.summary(),
        "monte_carlo": mc.summary(),
        "_tornado_obj": tor,
        "_monte_carlo_obj": mc,
    }


__all__ = ["ProjectResult", "run", "select_threshold", "analytical_cross_checks",
           "run_uncertainty_analysis", "project_crs"]
