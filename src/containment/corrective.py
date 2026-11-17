"""Artificial penetrations inside the AoR, and corrective action planning.

Delineating the AoR is only half of 40 CFR 146.84.  The other half is finding
every penetration inside it that may reach the confining zone, deciding which
ones need corrective action, and -- where the Director allows phased
corrective action -- deciding *when*.

What this module adds beyond a point-in-polygon query:

* the EPA well-evaluation decision tree (Figure 4-3 of 816-R-13-005) applied
  automatically from record completeness, plugging depth, plug material and
  abandonment date, with the reasoning attached to every well;
* **phased corrective action scheduling** -- for each well, the year the
  modelled plume or pressure front first reaches it, so corrective action can
  be sequenced by arrival time rather than by distance.  40 CFR
  146.84(b)(2)(iv) permits phasing but nothing tells an operator how to phase
  it; arrival time is the defensible criterion, and it falls straight out of
  the same model that produced the AoR;
* an AoR-reevaluation differencing helper so newly included wells are flagged
  as requiring assessment under 146.84(e)(2)-(3).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

import numpy as np

from . import units as U

# The API standard for oil-well cements dates from 1952; EPA notes that "it is
# likely that any wells abandoned before 1952 may have inadequate plugs"
# (816-R-13-005 Section 4.2, citing Ide et al. 2006).
API_CEMENT_STANDARD_YEAR = 1952
# A plug top reported within this distance of the confining zone still counts
# as set across it: depth records are rounded and log/driller depths differ
# by a few feet. 1 m (about 3.3 ft); depths are model metres.
PLUG_DEPTH_TOLERANCE = 1.0
# Texas well-history rules from Johnston & Knape (1986), Texas Water Commission
# LP 86-06, "Pressure effects of the static mud column in abandoned wells".
# They add context and adjust field-testing priority; they never clear a well,
# because EPA's Class VI tree (above) still decides the action.
TX_RULE14_YEAR = 1967          # RRC Rule 14 (Jan 1, 1967): cement plugs, >=9.5 lb/gal mud between
TX_FIRST_PLUGGING_RULE_YEAR = 1919
TX_SHALLOW_ERA_YEAR = 1930     # before this, wells rarely deeper than 3,000-4,000 ft
TX_SHALLOW_ERA_DEPTH_FT = 4000.0
TX_GULF_WEST_LONGITUDE = -99.0  # same east/west split as reference_defaults
JK = "Johnston & Knape 1986"

CO2_INCOMPATIBLE_PLUGS = {
    "mechanical", "bridge plug", "cast iron bridge plug", "cibp",
    "mud", "drilling mud", "none", "unknown",
}


@dataclass
class ArtificialPenetration:
    """One well, mine or other man-made penetration.

    Only ``name``, ``x`` and ``y`` are required.  Everything else improves the
    screening; missing information is treated as *unknown*, which is what
    pushes a well toward field testing rather than toward "no action".
    """

    name: str
    x: float
    y: float
    api: str = ""
    kind: str = "unknown"              # oil, gas, injection, water, dry hole, mine...
    status: str = "unknown"            # active, shut-in, plugged, abandoned, unknown
    total_depth: float = float("nan")  # m
    year_drilled: int | None = None
    year_abandoned: int | None = None
    plug_depths: tuple[float, ...] = ()     # m, cement plug tops
    plug_material: str = "unknown"
    cased: bool | None = None
    records_complete: bool | None = None
    mit_passed: bool | None = None
    notes: str = ""
    latitude: float = float("nan")
    longitude: float = float("nan")

    # populated by the screen
    in_aor: bool = False
    penetrates_confining_zone: bool | None = None
    action: str = ""
    action_reason: str = ""
    priority: int = 0
    arrival_year_plume: float = float("nan")
    arrival_year_pressure: float = float("nan")
    distance_to_nearest_injector: float = float("nan")
    history_note: str = ""

    def as_row(self) -> dict:
        return {
            "name": self.name,
            "api": self.api,
            "x_m": self.x, "y_m": self.y,
            "type": self.kind,
            "status": self.status,
            "total_depth_ft": U.length_out(self.total_depth, "ft"),
            "year_drilled": self.year_drilled,
            "year_abandoned": self.year_abandoned,
            "plug_material": self.plug_material,
            "in_aor": self.in_aor,
            "penetrates_confining_zone": self.penetrates_confining_zone,
            "distance_to_injector_ft": U.length_out(self.distance_to_nearest_injector, "ft"),
            "action": self.action,
            "reason": self.action_reason,
            "priority": self.priority,
            "texas_history_note": self.history_note,
            "plume_arrival_yr": self.arrival_year_plume,
            "pressure_arrival_yr": self.arrival_year_pressure,
            "notes": self.notes,
        }


# ==========================================================================
# EPA Figure 4-3 decision tree
# ==========================================================================
def evaluate_well(w: ArtificialPenetration, confining_zone_top: float,
                  confining_zone_base: float,
                  injection_zone_top: float | None = None) -> ArtificialPenetration:
    """Apply EPA's well-evaluation decision tree to one penetration.

    The outcome is one of:

    ``no action``
        does not reach the confining zone, or is adequately plugged across it
        with CO2-compatible cement and complete records;
    ``field testing``
        records are missing, incomplete or ambiguous -- EPA Section 4.3.2
        requires field tests before the well can be cleared;
    ``corrective action``
        records positively show inadequate plugging, an unplugged hole, a
        failed MIT, or plug material that will not survive contact with CO2;
    ``monitor``
        an active well under the operator's control, tracked but not plugged.

    Depths are metres below the same datum as the AoR model.
    """
    d = w.total_depth
    if np.isfinite(d) and d < confining_zone_top:
        w.penetrates_confining_zone = False
        w.action = "no action"
        w.action_reason = (
            f"total depth {U.length_out(d, 'ft'):,.0f} ft is above the confining "
            f"zone top at {U.length_out(confining_zone_top, 'ft'):,.0f} ft "
            "[40 CFR 146.84(c)(2) applies to penetrations that may penetrate "
            "the confining zone]")
        w.priority = 0
        return w

    w.penetrates_confining_zone = True if np.isfinite(d) else None

    if w.status.lower().startswith("permitted"):
        w.action = "track"
        w.action_reason = (
            "permitted but not drilled, so not yet a penetration; if it is drilled "
            "through the confining zone it becomes one, and its casing and cement "
            "must isolate the injection and confining zones [40 CFR 146.84(c)]")
        w.priority = 1
        return w

    if (w.status.lower() in ("active", "producing", "injecting", "shut-in", "shut in")
            or w.status.lower().startswith("open")):
        w.action = "monitor"
        w.action_reason = (
            "active or shut-in well penetrating the confining zone; confirm "
            "mechanical integrity and CO2-compatible construction, and include "
            "in the testing and monitoring plan")
        w.priority = 2
        return w

    if w.mit_passed is False:
        w.action = "corrective action"
        w.action_reason = "a mechanical integrity test on record failed and the leak was not shown to be repaired"
        w.priority = 5
        return w

    if w.records_complete is False or w.records_complete is None:
        w.action = "field testing"
        w.action_reason = (
            "plugging records are absent or incomplete, so adequacy cannot be "
            "demonstrated from records alone [EPA Section 4.3.1]; run the "
            "non-destructive log sequence before deciding")
        w.priority = 4
        return w

    if not w.plug_depths:
        w.action = "corrective action"
        w.action_reason = "records show no cement plug in the wellbore"
        w.priority = 5
        return w

    plugs = np.asarray(w.plug_depths, float)
    across_confining = np.any((plugs >= confining_zone_top - PLUG_DEPTH_TOLERANCE)
                              & (plugs <= confining_zone_base + PLUG_DEPTH_TOLERANCE))
    if not across_confining:
        w.action = "corrective action"
        w.action_reason = (
            "no cement plug at a depth corresponding to the primary confining "
            "zone; EPA recommends setting one there to prevent cross-migration "
            "[Section 4.4.1, Figure 4-2]")
        w.priority = 5
        return w

    mat = (w.plug_material or "unknown").strip().lower()
    if any(bad in mat for bad in CO2_INCOMPATIBLE_PLUGS):
        w.action = "corrective action"
        w.action_reason = (
            f"plug material recorded as {w.plug_material!r}; mechanical plugs "
            "and unknown materials are not adequate for long-term CO2 "
            "isolation [EPA Section 4.3.1, citing Randhol et al. 2007], and "
            "40 CFR 146.84(d) requires CO2-compatible materials")
        w.priority = 5
        return w

    yr = w.year_abandoned or w.year_drilled
    if yr is not None and yr < API_CEMENT_STANDARD_YEAR:
        w.action = "field testing"
        w.action_reason = (
            f"abandoned in {yr}, before the 1952 API cement standard; EPA notes "
            "such plugs may not have set properly and warrants verification")
        w.priority = 4
        return w

    if w.cased is False:
        w.action = "field testing"
        w.action_reason = (
            "open-hole abandonment; EPA notes open holes are susceptible to "
            "cross-migration and recommends confirming plug integrity")
        w.priority = 3
        return w

    w.action = "no action"
    w.action_reason = (
        "records show a CO2-compatible cement plug across the primary "
        "confining zone, post-1952 abandonment, and no adverse test results")
    w.priority = 1
    return w


# ==========================================================================
# Texas well-history screen (Johnston & Knape 1986)
# ==========================================================================
def texas_history_screen(w: ArtificialPenetration,
                         confining_zone_top: float) -> ArtificialPenetration:
    """Add the Johnston & Knape (1986) well-history notes to a screened well.

    Rules, each with the report's basis:

    * abandoned in or after 1967: RRC Rule 14 required cement plugs with at
      least 9.5 lb/gal mud between them, so the well "very probably" was
      properly plugged (conclusion 1). A well sent to field testing only for
      missing records drops one priority step (4 -> 3); it is not cleared.
    * abandoned 1919-1966: plugging rules existed, so it may be properly
      plugged even without records (conclusion 1); before 1919 there were none.
    * uncased hole: east of 99 W (Gulf Coast-type unconsolidated sediments)
      it probably closed by sloughing within hours (conclusion 2); west of it
      (consolidated rock) it can stay open for decades (conclusion 3), so a
      field-testing well there rises one priority step. Red beds close even
      in West Texas; the split is a screen, not the lithology.
    * casing left in an unplugged hole is itself a conduit, and casing is not
      assumed full of mud unless records say so (appendix, Kent; PB-KBB).
    * mud as the only plug: mud weight is the resisting column (9 lb/gal
      assumed, 9.5 after 1967); gel strength is a safety margin only, and acid
      (CO2-charged brine) can channel gel (conclusions 4-5; appendix, Smith).
    * depth unknown and drilled before 1930: wells then rarely went deeper
      than 3,000-4,000 ft (p. 5), so a confining zone deeper than 4,000 ft is
      probably not reached; the depth still has to be confirmed.
    """
    notes: list[str] = []
    if w.action in ("track", "monitor"):
        w.history_note = ""
        return w
    yr = w.year_abandoned
    if yr is not None:
        if yr >= TX_RULE14_YEAR:
            notes.append(f"abandoned {yr}, under RRC Rule 14 (1967): cement plugs with "
                         f">=9.5 lb/gal mud between them, very probably properly plugged")
            if (w.action == "field testing" and w.priority == 4
                    and (w.records_complete is None or w.records_complete is False)):
                w.priority = 3
        elif yr >= TX_FIRST_PLUGGING_RULE_YEAR:
            notes.append(f"abandoned {yr} (1919-1966): plugging rules existed, may be "
                         "properly plugged even without records")
        else:
            notes.append(f"abandoned {yr}, before Texas plugging rules (1919)")
    if w.cased is False:
        if np.isfinite(w.longitude):
            if w.longitude > TX_GULF_WEST_LONGITUDE:
                notes.append("uncased hole east of 99 W: in unconsolidated Gulf Coast "
                             "sediments it probably closed by sloughing; confirm lithology")
            else:
                notes.append("uncased hole west of 99 W: in consolidated rock it can stay "
                             "open for decades, treat as an open conduit (red beds close)")
                if w.action == "field testing":
                    w.priority = min(w.priority + 1, 5)
        else:
            notes.append("uncased hole: closes quickly in Gulf Coast sediments and red "
                         "beds, stays open for decades in hard West Texas rock")
    unplugged = not w.plug_depths
    if w.cased is True and unplugged and w.action != "no action":
        notes.append("casing left in an unplugged hole is itself a conduit; do not assume "
                     "the casing is full of mud unless records show it")
    mat = (w.plug_material or "").strip().lower()
    if "mud" in mat:
        notes.append("mud only: credit the mud weight (9 lb/gal, 9.5 after 1967) at most; "
                     "gel strength is a safety margin and CO2-charged brine can channel it")
    yd = w.year_drilled
    if (not np.isfinite(w.total_depth) and yd is not None and yd < TX_SHALLOW_ERA_YEAR
            and U.length_out(confining_zone_top, "ft") > TX_SHALLOW_ERA_DEPTH_FT):
        notes.append(f"drilled {yd}, when wells rarely exceeded 3,000-4,000 ft: probably "
                     f"above the confining zone at "
                     f"{U.length_out(confining_zone_top, 'ft'):,.0f} ft; confirm depth")
    w.history_note = ("; ".join(notes) + f" [{JK}]") if notes else ""
    return w


# ==========================================================================
# the screen
# ==========================================================================
@dataclass
class CorrectiveActionPlan:
    """Result of screening a well list against a delineated AoR."""

    wells: list[ArtificialPenetration]
    confining_zone_top: float
    confining_zone_base: float
    aor_area_acres: float = float("nan")
    warnings: list[str] = field(default_factory=list)

    @property
    def inside(self) -> list[ArtificialPenetration]:
        return [w for w in self.wells if w.in_aor]

    def by_action(self, action: str) -> list[ArtificialPenetration]:
        return [w for w in self.inside if w.action == action]

    def table(self) -> list[dict]:
        return [w.as_row() for w in sorted(
            self.inside, key=lambda w: (-w.priority, w.arrival_year_plume))]

    def phases(self, phase_boundaries_years: Sequence[float] = (5, 10, 20)) -> dict:
        """Group wells needing action into phases by modelled arrival time.

        Wells the plume or pressure front never reaches within the simulation
        fall into a final ``"beyond model horizon"`` bucket; EPA nonetheless
        expects all identified deficient wells to receive corrective action
        "before the end of the injection phase" (Section 4.4).
        """
        need = [w for w in self.inside if w.action in ("corrective action", "field testing")]
        out: dict[str, list[str]] = {}
        bounds = list(phase_boundaries_years)
        for i, b in enumerate(bounds):
            lo = 0.0 if i == 0 else bounds[i - 1]
            key = f"phase {i + 1}: arrival {lo:g}-{b:g} yr"
            out[key] = []
        out[f"phase {len(bounds) + 1}: arrival after {bounds[-1]:g} yr"] = []
        out["beyond model horizon"] = []

        for w in need:
            times = [t for t in (w.arrival_year_plume, w.arrival_year_pressure)
                     if t is not None and np.isfinite(t)]
            arrival = min(times) if times else np.inf
            if not np.isfinite(arrival):
                out["beyond model horizon"].append(w.name)
                continue
            placed = False
            for i, b in enumerate(bounds):
                lo = 0.0 if i == 0 else bounds[i - 1]
                if lo <= arrival < b:
                    out[f"phase {i + 1}: arrival {lo:g}-{b:g} yr"].append(w.name)
                    placed = True
                    break
            if not placed:
                out[f"phase {len(bounds) + 1}: arrival after {bounds[-1]:g} yr"].append(w.name)
        return out

    def summary(self) -> dict:
        inside = self.inside
        return {
            "aor_area_acres": self.aor_area_acres,
            "penetrations_evaluated": len(self.wells),
            "penetrations_inside_aor": len(inside),
            "penetrating_confining_zone": sum(
                1 for w in inside if w.penetrates_confining_zone is not False),
            "corrective_action_required": len(self.by_action("corrective action")),
            "field_testing_required": len(self.by_action("field testing")),
            "monitor": len(self.by_action("monitor")),
            "no_action": len(self.by_action("no action")),
            "permitted_not_drilled_track": len(self.by_action("track")),
            "warnings": list(self.warnings),
        }


def screen(wells: Iterable[ArtificialPenetration], aor_result,
           confining_zone_top: float, confining_zone_base: float,
           injectors: Sequence[tuple[float, float]] = (),
           ) -> CorrectiveActionPlan:
    """Flag which penetrations lie inside the AoR and what to do about each."""
    from shapely.geometry import Point

    geom = aor_result.aor if hasattr(aor_result, "aor") else aor_result
    wells = list(wells)
    warnings: list[str] = []

    for w in wells:
        w.in_aor = bool(geom is not None and not geom.is_empty
                        and geom.contains(Point(w.x, w.y)))
        if injectors:
            w.distance_to_nearest_injector = float(min(
                np.hypot(w.x - ix, w.y - iy) for ix, iy in injectors))
        if w.in_aor:
            evaluate_well(w, confining_zone_top, confining_zone_base)
            texas_history_screen(w, confining_zone_top)

    unknown_depth = [w.name for w in wells if w.in_aor and not np.isfinite(w.total_depth)]
    if unknown_depth:
        warnings.append(
            f"{len(unknown_depth)} well(s) inside the AoR have no recorded total "
            "depth, so whether they penetrate the confining zone is unknown; "
            "40 CFR 146.84(c)(2) requires depth to be reported for each: "
            + ", ".join(unknown_depth[:10]) + ("..." if len(unknown_depth) > 10 else ""))

    return CorrectiveActionPlan(
        wells=wells,
        confining_zone_top=confining_zone_top,
        confining_zone_base=confining_zone_base,
        aor_area_acres=getattr(aor_result, "area_acres", float("nan")),
        warnings=warnings,
    )


# ==========================================================================
# arrival times for phased corrective action
# ==========================================================================
def arrival_times(plan: CorrectiveActionPlan, x: np.ndarray, y: np.ndarray,
                  times: np.ndarray,
                  plume_fields: np.ndarray | None = None,
                  plume_level: float = 1e-6,
                  dp_fields: np.ndarray | None = None,
                  threshold_pressure: float = float("inf")
                  ) -> CorrectiveActionPlan:
    """Stamp each well with the year the plume / pressure front first reaches it.

    ``plume_fields`` and ``dp_fields`` are ``(nt, ny, nx)`` stacks on the
    ``(y, x)`` grid, matching ``times`` (seconds).  Values are sampled at the
    well location by nearest cell.
    """
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    times = np.asarray(times, float)

    for w in plan.wells:
        if not w.in_aor:
            continue
        i = int(np.argmin(np.abs(x - w.x)))
        j = int(np.argmin(np.abs(y - w.y)))

        if plume_fields is not None:
            series = np.asarray(plume_fields)[:, j, i]
            hit = np.nonzero(series >= plume_level)[0]
            w.arrival_year_plume = (U.time_out(float(times[hit[0]]), "yr")
                                    if hit.size else float("nan"))
        if dp_fields is not None and np.isfinite(threshold_pressure):
            series = np.asarray(dp_fields)[:, j, i]
            hit = np.nonzero(series >= threshold_pressure)[0]
            w.arrival_year_pressure = (U.time_out(float(times[hit[0]]), "yr")
                                       if hit.size else float("nan"))
    return plan


def newly_included(previous: CorrectiveActionPlan, current: CorrectiveActionPlan
                   ) -> list[str]:
    """Wells inside the reevaluated AoR that were not inside the previous one.

    These are the wells that "must be subjected to the artificial penetration
    identification, assessment, and corrective action procedures"
    [40 CFR 146.84(e)(2) and (3)].
    """
    before = {w.name for w in previous.inside}
    return [w.name for w in current.inside if w.name not in before]


def load_wells_csv(path: str, *, x_col="x", y_col="y", name_col="name",
                   unit: str = "m", crs=None, **column_map
                   ) -> list[ArtificialPenetration]:
    """Read a well table from CSV.

    Column names are configurable; anything matching an
    :class:`ArtificialPenetration` field is picked up automatically.
    ``unit`` converts the coordinate and depth columns (``"m"`` or ``"ft"``).
    Semicolon-separated plug depths in a ``plug_depths`` column are parsed.

    If the file has ``latitude`` and ``longitude`` columns and ``crs`` is a
    :class:`containment.io.exporters.LocalCRS`, those are used in preference to
    ``x``/``y`` and converted into the model frame. State well lists come out
    of RRC, TWDB and commercial databases in latitude and longitude, so this
    is usually the path of least resistance.
    """
    import csv

    scale = U.length(1.0, unit)
    out: list[ArtificialPenetration] = []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            row = {(column_map.get(k, k) or k).strip(): (v.strip() if isinstance(v, str) else v)
                   for k, v in row.items() if k}
            lat = row.get("latitude") or row.get("lat")
            lon = row.get("longitude") or row.get("lon") or row.get("long")
            if crs is not None and lat and lon:
                import numpy as _np
                gx, gy = crs.from_lonlat(_np.array([float(lon)]), _np.array([float(lat)]))
                wx, wy = float(gx[0]), float(gy[0])
            else:
                wx = float(row[x_col]) * scale
                wy = float(row[y_col]) * scale
            w = ArtificialPenetration(
                name=row.get(name_col) or row.get("name") or row.get("api") or "unnamed",
                x=wx, y=wy,
            )
            if lat and lon:
                w.latitude, w.longitude = float(lat), float(lon)
            for f in ("api", "kind", "status", "plug_material", "notes"):
                if row.get(f):
                    setattr(w, f, row[f])
            if row.get("type") and w.kind == "unknown":
                w.kind = row["type"]
            for f, conv in (("total_depth", lambda v: float(v) * scale),
                            ("year_drilled", int), ("year_abandoned", int)):
                if row.get(f):
                    try:
                        setattr(w, f, conv(row[f]))
                    except ValueError:
                        pass
            if row.get("plug_depths"):
                w.plug_depths = tuple(
                    float(p) * scale for p in row["plug_depths"].replace(",", ";").split(";")
                    if p.strip())
            for f in ("cased", "records_complete", "mit_passed"):
                v = (row.get(f) or "").lower()
                if v in ("true", "yes", "y", "1"):
                    setattr(w, f, True)
                elif v in ("false", "no", "n", "0"):
                    setattr(w, f, False)
            out.append(w)
    return out


__all__ = [
    "ArtificialPenetration", "CorrectiveActionPlan", "evaluate_well", "screen",
    "arrival_times", "newly_included", "load_wells_csv", "texas_history_screen",
    "API_CEMENT_STANDARD_YEAR",
]
