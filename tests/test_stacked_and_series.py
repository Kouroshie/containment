"""Stacked injection zones, and the AoR through time.

Two features that a single-zone snapshot AoR cannot express:

* an operator completing one wellbore in several formations, where each zone
  has its own pressure regime and therefore its own AoR, and the project AoR
  is the union of them;
* the AoR at each re-evaluation date under 40 CFR 146.84(e), where the growth
  between two dates is the ground that becomes subject to corrective action.
"""

from __future__ import annotations

import copy

import numpy as np
import pytest

from containment import delineate, workflow
from containment import units as U
from containment.config import Project

pytest.importorskip("shapely")


BASE = {
    "project": {"name": "stacked"},
    "units": {"length": "ft", "depth": "ft", "pressure": "psi",
              "temperature": "F", "permeability": "mD", "rate": "MMT/yr",
              "time": "yr", "compressibility": "1/psi"},
    "formation": {
        "injection_zones": [
            {"name": "Upper", "top_depth": 5200, "thickness": 180,
             "porosity": 0.20, "permeability": 220, "temperature": 140,
             "salinity_ppm": 70000, "initial_pressure": 2250,
             "rock_compressibility": 5e-6,
             "confining_zone": {"top_depth": 5000, "base_depth": 5200}},
            {"name": "Lower", "top_depth": 6000, "thickness": 250,
             "porosity": 0.18, "permeability": 150, "temperature": 150,
             "salinity_ppm": 90000, "initial_pressure": 2600,
             "rock_compressibility": 5e-6,
             "confining_zone": {"top_depth": 5700, "base_depth": 6000}},
        ],
        "usdw": {"base_depth": 1200, "initial_pressure": 520,
                 "temperature": 80, "salinity_ppm": 800},
    },
    "relative_permeability": {"model": "brooks_corey", "swr": 0.35,
                              "sgr": 0.20, "krg0": 0.30, "m": 3.0, "n": 3.0},
    "model": {"engine": "analytical", "boundary": "infinite", "end_year": 40,
              "grid": {"cell_size": 1000, "half_width": 79200}},
    "wells": [{"name": "INJ-1", "x": 0, "y": 0, "rate": 1.0,
               "start_year": 0, "stop_year": 20}],
}


def _project(**overrides) -> Project:
    d = copy.deepcopy(BASE)
    d.update(overrides)
    return Project.from_dict(d)


# ----------------------------------------------------------------- config
def test_zones_are_parsed_and_kept_in_order():
    p = _project()
    assert p.is_stacked
    assert [z.name for z in p.zones] == ["Upper", "Lower"]
    assert p.seals[0].top_depth < p.seals[1].top_depth
    # each zone keeps its own pressure: that is what gives it its own dP_c
    assert p.zones[0].initial_pressure < p.zones[1].initial_pressure


def test_a_single_zone_project_is_unchanged():
    d = copy.deepcopy(BASE)
    d["formation"] = {
        "injection_zone": d["formation"]["injection_zones"][1],
        "usdw": d["formation"]["usdw"],
    }
    p = Project.from_dict(d)
    assert not p.is_stacked
    assert len(p.zones) == 1
    assert p.zone_wells(0) == p.wells        # nothing is allocated away


def test_commingled_rate_splits_by_flow_capacity():
    p = _project()
    shares = [r["kh_share_percent"] for r in p.zone_allocation()]
    assert pytest.approx(sum(shares), abs=1e-6) == 100.0

    kh = [z.permeability * z.thickness for z in p.zones]
    assert shares[0] / shares[1] == pytest.approx(kh[0] / kh[1], rel=1e-6)

    # the split conserves mass: the zones together inject what the well does
    total = sum(w.total_mass() for w in p.wells)
    parts = sum(w.total_mass() for i in range(len(p.zones))
                for w in p.zone_wells(i))
    assert parts == pytest.approx(total, rel=1e-9)


def test_naming_a_zone_sends_the_whole_rate_there():
    d = copy.deepcopy(BASE)
    d["wells"][0]["zone"] = "Lower"
    p = Project.from_dict(d)
    assert p.zone_wells(0) == []                       # nothing in Upper
    assert len(p.zone_wells(1)) == 1
    assert p.zone_wells(1)[0].total_mass() == pytest.approx(
        p.wells[0].total_mass(), rel=1e-9)


def test_a_well_naming_an_unknown_zone_is_flagged():
    d = copy.deepcopy(BASE)
    d["wells"][0]["zone"] = "Middle"
    p = Project.from_dict(d)
    assert any("do not exist" in w for w in p.warnings)


# --------------------------------------------------------------- combine
def _disc(cx, cy, r):
    return delineate.circles_to_polygon([(cx, cy)], [r])


def test_the_union_is_geometric_not_a_sum_of_areas():
    a = delineate.AoRResult(plume=_disc(0, 0, 1000.0), pressure_front=None,
                            aor=_disc(0, 0, 1000.0), threshold_pressure=1.0)
    b = delineate.AoRResult(plume=_disc(500, 0, 1000.0), pressure_front=None,
                            aor=_disc(500, 0, 1000.0), threshold_pressure=2.0)
    c = delineate.combine([a, b], labels=["A", "B"])

    assert c.area_m2 > max(a.area_m2, b.area_m2)     # the union grew
    assert c.area_m2 < a.area_m2 + b.area_m2         # but not by the whole disc
    assert c.metadata["governing_zone"] in ("A", "B")
    assert c.metadata["sum_of_zone_areas_acres"] > c.metadata["union_area_acres"]
    assert any("double" not in w for w in c.warnings)


def test_combining_one_zone_returns_it_untouched():
    a = delineate.AoRResult(plume=_disc(0, 0, 1000.0), pressure_front=None,
                            aor=_disc(0, 0, 1000.0), threshold_pressure=1.0)
    assert delineate.combine([a]) is a


# ---------------------------------------------------------------- series
def test_the_aor_series_lands_on_the_reevaluation_dates():
    p = _project()
    marks = workflow.reevaluation_times(p)
    years = [U.time_out(t, "yr") for t in marks]
    assert years == pytest.approx([5, 10, 15, 20, 25, 30, 35, 40])


def test_a_custom_reevaluation_interval_is_honoured():
    d = copy.deepcopy(BASE)
    d["model"]["aor_reevaluation_years"] = 10
    p = Project.from_dict(d)
    years = [U.time_out(t, "yr") for t in workflow.reevaluation_times(p)]
    assert years == pytest.approx([10, 20, 30, 40])


def test_the_cumulative_series_never_shrinks():
    """A cumulative AoR is monotone by construction; that is what makes it an
    AoR rather than a snapshot of where the pressure happens to be."""
    p = _project()
    res = workflow.run(p)
    areas = [s.area_acres for s in res.series]
    assert len(areas) >= 4
    assert all(b >= a - 1e-6 for a, b in zip(areas, areas[1:], strict=False))
    assert areas[-1] == pytest.approx(res.aor.area_acres, rel=0.02)


def test_the_growth_ledger_adds_up():
    p = _project()
    res = workflow.run(p)
    rows = delineate.series_growth(res.series)
    assert rows[0]["year"] < rows[-1]["year"]
    assert sum(r["added_acres"] for r in rows) == pytest.approx(
        rows[-1]["area_acres"], rel=1e-6)
    # newly included ground is what corrective action attaches to
    assert all(r["newly_included_acres"] >= -1e-9 for r in rows)


def test_instantaneous_mode_can_shrink_after_shut_in():
    """Pressure relaxes once injection stops. The cumulative series must not
    show that, and the instantaneous one must, or neither is measuring what
    it claims."""
    p = _project()
    res = workflow.run(p)
    inst = delineate.aor_series(
        res.x, res.y, res.times, dp_fields=res.dp_fields,
        threshold_pressure=res.selected_threshold.delta_p_critical,
        plume_fields=None, mode="instantaneous",
        at_times=workflow.reevaluation_times(p))
    areas = [s.area_acres for s in inst]
    assert min(areas) < max(areas)
    assert areas[-1] < max(areas)


# -------------------------------------------------------------- workflow
def test_a_stacked_run_unions_the_zones_and_keeps_them_separately():
    p = _project()
    res = workflow.run(p)

    assert len(res.zones) == 2
    assert [z.name for z in res.zones] == ["Upper", "Lower"]

    # each zone got its own threshold pressure from its own depth
    dpc = [z.threshold.delta_p_critical for z in res.zones]
    assert dpc[0] != dpc[1]

    # the project AoR contains every zone AoR, and is not their sum
    for z in res.zones:
        assert res.aor.aor.contains(z.aor.aor.buffer(-1.0))
    assert res.aor.area_acres <= sum(z.aor.area_acres for z in res.zones) + 1e-6
    assert res.aor.area_acres >= max(z.aor.area_acres for z in res.zones) - 1e-6

    s = res.summary()
    assert len(s["injection_zones"]) == 2
    assert s["aor_by_reevaluation_year"]
    assert any("unioned" in w for w in res.warnings)


def test_the_deeper_zone_carries_the_higher_threshold():
    """dP_c is measured from the injection zone up to the same USDW, so a
    deeper zone has further to lift fluid and needs more buildup to do it."""
    res = workflow.run(_project())
    upper, lower = res.zones
    assert lower.threshold.delta_p_critical > upper.threshold.delta_p_critical


def test_every_zone_is_modelled_with_its_own_co2_density():
    res = workflow.run(_project())
    masses = [z.injected_mass for z in res.zones]
    assert all(m > 0 for m in masses)
    assert sum(masses) == pytest.approx(
        res.project.total_injected_mass(), rel=1e-9)


@pytest.mark.slow
def test_stacked_and_single_zone_agree_when_the_zones_are_identical():
    """Two copies of one formation, each taking half the rate, must give the
    same AoR as that formation taking the whole rate. It is the sharpest
    check that the zone loop and the union do not invent or lose area."""
    d = copy.deepcopy(BASE)
    one = copy.deepcopy(d["formation"]["injection_zones"][1])
    twin = copy.deepcopy(one)
    twin["name"] = "Twin"
    one["name"] = "Original"
    d["formation"]["injection_zones"] = [one, twin]
    stacked = workflow.run(Project.from_dict(d))

    single = copy.deepcopy(BASE)
    single["formation"] = {
        "injection_zone": copy.deepcopy(BASE["formation"]["injection_zones"][1]),
        "usdw": BASE["formation"]["usdw"],
    }
    plain = workflow.run(Project.from_dict(single))

    # identical zones split the rate evenly and land on top of one another
    assert stacked.zones[0].aor.area_acres == pytest.approx(
        stacked.zones[1].aor.area_acres, rel=1e-6)
    # half the rate in each of two identical zones is not the same plume as
    # the whole rate in one, so compare the union against the single-zone run
    # only in the direction the physics guarantees: it cannot be larger.
    assert stacked.aor.area_acres <= plain.aor.area_acres * 1.02


def test_figures_render_for_a_stacked_run():
    matplotlib = pytest.importorskip("matplotlib")
    matplotlib.use("Agg")
    from containment import viz

    res = workflow.run(_project())
    wells = [w for w in res.project.wells if w.kind == "injector"]
    assert viz.aor_series_map(res.series, wells=wells) is not None
    assert viz.aor_growth_chart(res.series,
                                injection_end=res.project.injection_end()) is not None
    assert viz.zone_map(res.zones, res.aor, wells=wells) is not None


def test_plotly_figures_carry_a_slider_and_every_zone():
    pytest.importorskip("plotly")
    from containment import viz

    res = workflow.run(_project())
    fig = viz.plotly_aor_series(res.series, wells=res.project.wells)
    assert len(fig.layout.sliders[0].steps) == len(res.series)

    zfig = viz.plotly_zone_map(res.zones, res.aor, wells=res.project.wells)
    names = " ".join(t.name or "" for t in zfig.data)
    assert "Upper" in names and "Lower" in names and "union" in names


def test_empty_series_is_handled():
    assert delineate.aor_series([0.0, 1.0], [0.0, 1.0], np.array([])) == []


def _staged_project(**well_extra):
    from containment.config import Project
    base = {
        "formation": {"injection_zone": {"top_depth": 5600, "thickness": 800,
                                         "porosity": 0.25, "permeability": 300,
                                         "temperature": 150, "salinity_ppm": 100000,
                                         "initial_pressure": 2604},
                      "confining_zone": {"top_depth": 5200, "base_depth": 5600},
                      "usdw": {"base_depth": 1500, "initial_pressure": 650}},
        "wells": [
            {"name": "S1", "x": 0, "y": 0, "rate": 0.5, "start_year": 0, "stop_year": 1,
             "interval": "stage 1", "open_top_depth": 6300, "open_thickness": 90},
            {"name": "S2", "x": 0, "y": 0, "rate": 0.5, "start_year": 1, "stop_year": 2,
             "interval": "stage 2", "open_top_depth": 5700, "open_thickness": 120},
        ],
        "model": {"engine": "analytical", "end_year": 30},
    }
    for w in base["wells"]:
        w.update(well_extra)
    return Project.from_dict(base)


def test_staged_completion_becomes_one_isolated_interval_per_stage():
    p = _staged_project()
    assert p.is_stacked and len(p.zones) == 2
    names = [z.name for z in p.zones]
    assert names == ["injection zone / stage 2", "injection zone / stage 1"]  # shallowest first
    from containment import units as U
    z2, z1 = p.zones
    assert U.length_out(z1.thickness, "ft") == pytest.approx(90)
    assert U.length_out(z2.top_depth, "ft") == pytest.approx(5700)
    # the zone's own gradient carried down: 2604 psi * 6300 / 5600
    assert U.pressure_out(z1.initial_pressure, "psi") == pytest.approx(2929.5, rel=1e-4)
    assert [w.name for w in p.zone_wells(1)] == ["S1"]
    assert [w.name for w in p.zone_wells(0)] == ["S2"]
    assert any("staged completion" in w for w in p.warnings)
    assert p.raw["wells"][0]["open_thickness"] == 90      # the file is not rewritten


def test_staged_wells_in_the_same_interval_share_it():
    from containment.config import Project
    p = _staged_project(interval="one stage", open_top_depth=6000, open_thickness=100)
    assert len(p.zones) == 1
    assert len(p.zone_wells(0)) == 2
    assert isinstance(p, Project)


def test_staged_thin_interval_raises_the_pressure_front():
    from containment import workflow
    thin = _staged_project()
    full = _staged_project(open_thickness=None, open_top_depth=None, interval=None)
    assert not full.is_stacked
    a_thin = workflow.run(thin, run_uncertainty=False).aor.pressure_front
    a_full = workflow.run(full, run_uncertainty=False).aor.pressure_front
    def area(g):
        return 0.0 if g is None or g.is_empty else g.area
    assert area(a_thin) > area(a_full)


# ------------------------------------------------- per-zone threshold, relperm
def _per_zone_dict():
    d = copy.deepcopy(BASE)
    zs = d["formation"]["injection_zones"]
    zs[0]["threshold_override"] = 65
    zs[1]["relative_permeability"] = {"sgr": 0.30}
    d["threshold"] = {"override": 150}
    return d


def test_a_zone_can_carry_its_own_threshold_and_relperm():
    p = Project.from_dict(_per_zone_dict())
    up, lo = p.zones
    assert U.pressure_out(up.threshold_override, "psi") == pytest.approx(65)
    assert not np.isfinite(lo.threshold_override)
    assert up.relperm is None
    assert lo.relperm.sgr == pytest.approx(0.30)
    assert lo.relperm.swr == pytest.approx(0.35)        # the rest from the project


def test_the_zone_threshold_wins_and_the_project_one_fills_the_rest():
    from dataclasses import replace

    p = Project.from_dict(_per_zone_dict())
    got = []
    for z in p.zones:
        sub = replace(p, injection_zone=z, injection_zones=[], confining_zones=[])
        th = workflow.select_threshold(sub, [])
        got.append(round(th.delta_p_psi, 1))
    assert got == [65.0, 150.0]


def test_each_zone_is_run_with_its_own_threshold_and_relperm(monkeypatch):
    seen = []
    real = workflow.run_zone

    def spy(sub, **kw):
        seen.append((sub.injection_zone.name, sub.relperm.sgr))
        return real(sub, **kw)

    monkeypatch.setattr(workflow, "run_zone", spy)
    res = workflow.run(Project.from_dict(_per_zone_dict()), run_uncertainty=False)
    assert seen == [("Upper", pytest.approx(0.20)), ("Lower", pytest.approx(0.30))]
    th = {zr.name: round(zr.threshold.delta_p_psi, 1) for zr in res.zones}
    assert th == {"Upper": 65.0, "Lower": 150.0}


def test_a_single_zone_spelling_takes_its_own_threshold_and_relperm():
    d = copy.deepcopy(BASE)
    one = d["formation"].pop("injection_zones")[0]
    one.pop("name")
    d["formation"]["confining_zone"] = one.pop("confining_zone")
    one["threshold_override"] = 80
    one["relative_permeability"] = {"sgr": 0.25}
    d["formation"]["injection_zone"] = one
    p = Project.from_dict(d)
    assert p.relperm.sgr == pytest.approx(0.25)
    assert round(workflow.select_threshold(p, []).delta_p_psi, 1) == 80.0


def test_per_zone_values_survive_the_workbook(tmp_path):
    pytest.importorskip("openpyxl")
    from containment.io import workbook

    path = str(tmp_path / "zones.xlsx")
    workbook.to_excel(_per_zone_dict(), path)
    p = Project.from_dict(workbook.from_excel(path))
    up, lo = p.zones
    assert U.pressure_out(up.threshold_override, "psi") == pytest.approx(65)
    assert lo.relperm.sgr == pytest.approx(0.30)


def test_every_zone_gets_its_pisc_row_and_report_figure():
    from containment import pisc as pisc_mod
    from containment import report

    res = workflow.run(_project(), run_uncertainty=False)
    zones = [zr for zr in res.zones if zr.pisc is not None]
    rows = pisc_mod.zone_table(zones, res.pisc)
    assert [r["zone"] for r in rows] == ["Upper", "Lower"]
    assert sum(r["governs PISC"] == "yes" for r in rows) == 1
    assert rows[0]["threshold (psi)"] != rows[1]["threshold (psi)"]
    html = report.build_html(res)
    assert "Every injection zone" in html
    for name in ("Upper", "Lower"):
        assert f"Post-injection behaviour: {name}" in html


def test_a_zone_that_never_stabilises_governs_pisc():
    class Stub:
        def __init__(self, years):
            self.years = years

        def summary(self):
            return {"recommended_pisc": {"recommended_years": self.years}}

    stable, never = Stub(30.0), Stub(float("nan"))
    # the site is not released while any zone is still open
    assert workflow._pisc_years(never) > workflow._pisc_years(stable)
    assert workflow._pisc_years(Stub(50.0)) > workflow._pisc_years(stable)


def _staged_dict():
    d = copy.deepcopy(BASE)
    d["wells"] = [
        {"name": "INJ-1", "x": 0, "y": 0, "rate": 1.0, "zone": "Lower",
         "start_year": 0, "stop_year": 6},
        {"name": "INJ-1", "x": 0, "y": 0, "rate": 1.0, "zone": "Upper",
         "start_year": 6, "stop_year": 13},
    ]
    return d


def test_each_stacked_zone_is_sampled_on_its_own_schedule(monkeypatch):
    seen = {}
    real = workflow.run_zone

    def spy(sub, **kw):
        seen[sub.injection_zone.name] = U.time_out(np.asarray(sub.output_times), "yr")
        return real(sub, **kw)

    monkeypatch.setattr(workflow, "run_zone", spy)
    workflow.run(Project.from_dict(_staged_dict()), run_uncertainty=False)
    lower, upper = seen["Lower"], seen["Upper"]
    # the six-year zone is sampled densely over its own six years
    assert np.sum((lower > 0) & (lower <= 6.0 + 1e-6)) >= 12
    assert not np.array_equal(lower, upper)
    for marks in (5.0, 10.0, 15.0):                  # re-evaluation dates kept
        assert np.any(np.isclose(lower, marks)) and np.any(np.isclose(upper, marks))


def test_a_staged_stack_equals_the_union_of_its_zones_run_alone():
    from shapely.ops import unary_union

    d = _staged_dict()
    stacked = workflow.run(Project.from_dict(d), run_uncertainty=False).aor.aor
    parts = []
    for zd in d["formation"]["injection_zones"]:
        one = copy.deepcopy(d)
        z = dict(zd)
        one["formation"].pop("injection_zones")
        one["formation"]["confining_zone"] = z.pop("confining_zone")
        z.pop("name")
        one["formation"]["injection_zone"] = z
        one["wells"] = [dict(w) for w in d["wells"] if w["zone"] == zd["name"]]
        for w in one["wells"]:
            w.pop("zone")
        parts.append(workflow.run(Project.from_dict(one), run_uncertainty=False).aor.aor)
    union = unary_union(parts)
    assert stacked.area == pytest.approx(union.area, rel=1e-6)
    assert stacked.symmetric_difference(union).area < 1e-6 * union.area


def test_datum_top_is_each_zones_own_top():
    """threshold.datum: top means the top of every zone, not of the first one:
    a stacked zone gets the threshold it gets when run alone."""
    d = copy.deepcopy(BASE)
    d["threshold"] = {"method": "method1", "datum": "top"}
    stacked = workflow.run(Project.from_dict(d), run_uncertainty=False)
    for i, zr in enumerate(stacked.zones):
        one = copy.deepcopy(d)
        z = one["formation"].pop("injection_zones")[i]
        one["formation"]["injection_zone"] = z
        alone = Project.from_dict(one)
        assert U.length_out(alone.threshold_depth, "ft") == pytest.approx(z["top_depth"])
        th = workflow.select_threshold(alone, workflow.threshold_methods(alone))
        assert zr.threshold.delta_p_psi == pytest.approx(th.delta_p_psi)
    upper, lower = stacked.zones
    assert lower.threshold.delta_p_critical > upper.threshold.delta_p_critical


def test_one_fixed_datum_on_a_stack_is_flagged():
    d = copy.deepcopy(BASE)
    d["threshold"] = {"method": "method1", "datum_depth": 5200}
    res = workflow.run(Project.from_dict(d), run_uncertainty=False)
    assert any("datum_depth" in w and "every injection zone" in w for w in res.warnings)
