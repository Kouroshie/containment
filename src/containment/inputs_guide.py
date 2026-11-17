"""What every project input is, why Containment needs it, and what range to expect.

One table drives every place a user meets an input: the form's tooltips and
captions, the Help panel's input reference, the Excel workbook's Input guide
sheet and the comments in the YAML template. Keeping it in one place stops
the form and the templates from telling a reviewer different things.

Ranges are in field units (ft, psi, degF, mD, MMT/yr). ``typical`` is what a
reviewer should expect in a Texas Class VI application; ``plausible`` is the
outer bound beyond which the number is almost certainly a typing or unit
error. Gradient-type inputs (pressure, temperature) carry their range as a
gradient and are turned into values at the zone's depth when one is known.
Each range cites its sources; ``seen`` is what the 15 Texas Class VI
applications rebuilt for Containment's validation used (October 2026).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class InputInfo:
    key: str                  # id used by the form
    path: str                 # where it sits in the project file
    label: str
    unit: str                 # field unit the range is written in
    what: str                 # what the number is
    why: str                  # what it changes in the AoR / PISC, and why it is asked for
    typical: tuple[float, float] | None = None
    plausible: tuple[float, float] | None = None
    seen: str = ""            # range in the 15 rebuilt Texas applications
    if_missing: str = ""      # how to estimate it when the application is silent
    sources: tuple[str, ...] = field(default_factory=tuple)
    gradient: str = ""        # "pressure" or "temperature": range is per ft of depth


def _load_ranges() -> dict:
    from .input_ranges import RANGES
    return {r["key"]: r for r in RANGES}


# key, path, label, unit, what, why  (ranges, sources and if_missing come from
# input_ranges.json, which records the literature behind each one)
_WHY = [
    ("iz_top", "formation.injection_zone.top_depth", "Injection zone top depth", "ft",
     "Depth to the top of the injection zone, below ground (or below sea level offshore).",
     "Sets the pressure and temperature the CO2 is stored at, and so its density and "
     "viscosity. It is also the depth the threshold pressure is measured at, and the "
     "separation from the USDW."),
    ("iz_h", "formation.injection_zone.thickness", "Net thickness", "ft",
     "Thickness of the sand or porous rock that actually takes CO2 (net, not gross).",
     "The same tonnage spreads over less area in a thicker zone, so the plume radius "
     "falls roughly as one over the square root of thickness. Pressure buildup scales "
     "with one over permeability times thickness (kh), so a thin zone gives a larger "
     "pressure front."),
    ("iz_phi", "formation.injection_zone.porosity", "Porosity", "fraction",
     "Fraction of the rock volume that is connected pore space.",
     "Pore volume decides how far the plume has to spread to hold the injected mass, and "
     "with compressibility it sets how fast pressure spreads."),
    ("iz_k", "formation.injection_zone.permeability", "Permeability", "mD",
     "Horizontal permeability of the injection zone.",
     "Controls the pressure buildup for a given rate: halving permeability roughly doubles "
     "the buildup and enlarges the pressure-front AoR. It also controls how fast a buoyant "
     "plume migrates up-dip after injection."),
    ("iz_t", "formation.injection_zone.temperature", "Formation temperature", "degF",
     "Temperature of the injection zone at its depth.",
     "With pressure it fixes CO2 density and viscosity (equation of state), which set the "
     "plume volume and its buoyancy."),
    ("iz_s", "formation.injection_zone.salinity_ppm", "Brine salinity", "ppm",
     "Total dissolved solids of the formation brine.",
     "Sets brine density and viscosity, so the density contrast that drives CO2 up-dip, "
     "and enters the threshold-pressure calculation through the brine column."),
    ("iz_p", "formation.injection_zone.initial_pressure", "Initial pressure", "psi",
     "Pre-injection reservoir pressure at the top of the zone.",
     "The threshold pressure is a difference between this pressure and the pressure that "
     "would lift brine to the USDW; buildup is measured from it. An over- or under-"
     "pressured zone changes the threshold directly."),
    ("iz_cr", "formation.injection_zone.rock_compressibility", "Rock compressibility", "1/psi",
     "How much the pore volume grows per unit pressure.",
     "With brine compressibility it sets storativity: how much pressure rises and how far "
     "it travels for a given injected volume."),
    ("iz_dip", "formation.injection_zone.dip_degrees", "Dip", "deg",
     "Structural dip of the top of the injection zone.",
     "Buoyant CO2 migrates up-dip, mostly after injection stops. Dip sets how far and how "
     "fast, which usually decides the plume AoR and the PISC timeframe."),
    ("iz_az", "formation.injection_zone.dip_azimuth", "Dip direction", "deg",
     "Compass direction the beds dip toward, degrees from north.",
     "CO2 migrates the opposite way (up-dip), so this sets which side of the wells the "
     "AoR grows toward."),
    ("iz_kvkh", "formation.injection_zone.anisotropy_kv_kh", "kv/kh", "fraction",
     "Ratio of vertical to horizontal permeability.",
     "Used in the analytical cross-checks and when judging how well a thick zone "
     "communicates vertically; low values keep CO2 near the perforations."),
    ("cz", "formation.confining_zone", "Confining zone thickness", "ft",
     "Top and base of the primary confining zone (caprock) above the injection zone.",
     "Sets which artificial penetrations cross the seal and so need corrective action, "
     "and the depth interval used in the threshold calculation."),
    ("usdw_base", "formation.usdw.base_depth", "Base of lowermost USDW", "ft",
     "Depth to the base of the deepest underground source of drinking water "
     "(water under 10,000 mg/L TDS).",
     "The rule protects this interval. The threshold pressure is the buildup that could "
     "lift brine from the injection zone up an open well to this depth, so a deeper USDW "
     "base means a lower threshold and a larger pressure-front AoR."),
    ("usdw_p", "formation.usdw.initial_pressure", "USDW pressure", "psi",
     "Pressure at the base of the lowermost USDW.",
     "With the USDW depth it sets the hydraulic head formation brine must overcome to "
     "enter the USDW (EPA Method 1)."),
    ("usdw_t", "formation.usdw.temperature", "USDW temperature", "degF",
     "Temperature at the base of the lowermost USDW.",
     "Used for the density of the fluid column between the USDW and the injection zone."),
    ("usdw_s", "formation.usdw.salinity_ppm", "USDW salinity", "ppm",
     "Salinity of the water at the base of the USDW.",
     "Used for the fluid density in the threshold calculation; by definition below "
     "10,000 mg/L."),
    ("water_depth", "offshore.water_depth", "Water depth (offshore)", "ft",
     "Sea level to the seafloor (mud line), offshore projects only.",
     "Offshore there is often no USDW; the threshold is measured against the mud line or "
     "the first permeable bed below it, whose pressure starts from this seawater column."),
    ("off_t", "offshore.seafloor_temperature", "Seafloor temperature", "degF",
     "Water temperature at the seafloor, offshore projects only.",
     "Used for fluid density at the offshore reference depth."),
    ("swr", "relative_permeability.swr", "Irreducible brine saturation Swr", "fraction",
     "Brine saturation CO2 cannot displace.",
     "Less pore space is available to CO2 when Swr is high, so the same mass spreads "
     "further: a larger plume."),
    ("sgr", "relative_permeability.sgr", "Residual CO2 saturation Sgr", "fraction",
     "CO2 left behind, trapped as droplets, as the plume moves on (residual trapping).",
     "The main control on whether a migrating plume stops: high Sgr traps CO2 along its "
     "path and shortens up-dip migration and the PISC timeframe."),
    ("krg0", "relative_permeability.krg0", "CO2 end-point relative permeability", "fraction",
     "Relative permeability of CO2 at irreducible brine.",
     "Sets how easily CO2 flows against brine: higher values let the plume spread and "
     "migrate faster."),
    ("krw0", "relative_permeability.krw0", "Brine end-point relative permeability", "fraction",
     "Relative permeability of brine with no CO2 present.",
     "Sets brine mobility ahead of the plume, which affects pressure buildup."),
    ("corey_w", "relative_permeability.m", "Brine Corey exponent m", "-",
     "Curvature of the brine relative-permeability curve.",
     "Higher exponents make brine harder to push out, which changes how sharp the plume "
     "front is and how far it reaches."),
    ("corey_g", "relative_permeability.n", "CO2 Corey exponent n", "-",
     "Curvature of the CO2 relative-permeability curve.",
     "Higher exponents slow CO2 at low saturation, so thin plume tongues move less."),
    ("threshold", "threshold.override", "Threshold pressure (if stated)", "psi",
     "The critical pressure increase the operator states, if you want to use it directly.",
     "Any cell whose pressure rise exceeds this is inside the pressure-front AoR. Normally "
     "Containment computes it (EPA Methods 1 and 2, mud column); give it only to match an "
     "operator's stated value."),
    ("ppg", "threshold.mud_weight_ppg", "Mud weight", "ppg",
     "Weight of drilling mud assumed to stand in an old well, mud-column method.",
     "A heavier mud column resists more pressure, so it raises the threshold."),
    ("gel", "threshold.gel_strength", "Mud gel strength", "psi",
     "Extra pressure needed to start a gelled mud column moving.",
     "Adds directly to the mud-column threshold."),
    ("rate", "wells[].rate", "CO2 injection rate per well", "MMT/yr",
     "Million tonnes of CO2 per year for each well, over its start and stop years.",
     "Plume size grows with injected mass, and pressure buildup with rate. This is the "
     "number the AoR is most directly proportional to."),
    ("brine_rate", "wells[].rate (kind: extractor)", "Brine extraction rate", "bbl/day",
     "Brine produced by a pressure-management (extraction) well.",
     "Offsets injection: removing brine lowers the pressure buildup and can shrink the "
     "pressure-front AoR several-fold."),
    ("max_bhp", "wells[].max_bhp", "Maximum bottomhole pressure", "psi",
     "The injection pressure limit, normally 90 percent of fracture pressure.",
     "If the scheduled rate would need more pressure than this, Containment throttles the "
     "rate and reports how much CO2 could actually be injected."),
    ("radius", "wells[].radius", "Wellbore radius", "ft",
     "Radius of the injection well at the perforations.",
     "Used for the bottomhole pressure check (Peaceman well index); it does not move the "
     "AoR."),
    ("open_h", "wells[].open_thickness", "Open interval thickness (staged)", "ft",
     "For a staged completion: net thickness of the interval open in that stage.",
     "The stage's whole rate goes into this thin interval, so its pressure rise is not "
     "spread over the full zone. Isolated stages give the upper bound of the pressure-front "
     "AoR; the full zone gives the lower bound."),
    ("engine", "model.engine", "Model engine", "-",
     "Which model computes the pressure and the CO2 plume through time.",
     "It decides what physics the AoR rests on: dip, faults, buoyant migration after "
     "injection and residual trapping are only in the VE simulator; the analytical engine "
     "is a fast closed-form screen. The PISC timeframe needs the VE simulator."),
    ("method", "threshold.method", "Threshold pressure method", "-",
     "How the threshold (critical) pressure increase is computed: the buildup above which "
     "brine could be pushed up an open old well into the lowermost USDW.",
     "The pressure front, and often the whole AoR, is drawn at this buildup, so it is the "
     "largest single choice in the delineation: a smaller threshold draws a larger front. "
     "Each method rests on a different assumption about the fluid in a hypothetical open "
     "well, and each applies only to some pressure regimes."),
    ("cutoff", "plume.cutoff", "Plume saturation cutoff", "fraction",
     "The CO2 saturation that counts as 'inside the plume'.",
     "A disclosed choice rather than a physical constant: a lower cutoff draws the plume "
     "edge further out."),
    ("end_year", "model.end_year", "Simulation end", "yr",
     "Years from the start of injection to the end of the model run.",
     "Must run well past injection for the plume to stop moving; the AoR is the largest "
     "extent over this period and the PISC case rests on it."),
    ("cell", "model.grid.cell_size", "Fine cell size", "ft",
     "Cell size of the numerical grid around the wells.",
     "Smaller cells resolve the plume edge better at a cost in run time; the run warns when "
     "the plume is too few cells across."),
]


# what Containment uses when the input is left blank (see reference_defaults)
BLANK = {
    "iz_t": "regional surface temperature plus gradient at mid-zone (Gulf Coast 70 degF + "
            "1.33 degF/100 ft; Permian 65 + 0.75), calibrated on 15 Texas applications",
    "iz_p": "a hydrostatic column of the site's brine, integrated with depth from its "
            "salinity and temperature (about 0.45 to 0.47 psi/ft on the Gulf Coast)",
    "iz_s": "100,000 ppm (Texas applications 59,000 to 200,000)",
    "iz_cr": "Hall (1953) from porosity for sandstone; Newman (1973) for carbonate "
             "(set lithology: carbonate)",
    "iz_kvkh": "0.1",
    "iz_dip": "0 (flat); give the dip whenever the plan has a structure map",
    "usdw_p": "a hydrostatic column of 10,000 ppm water to the USDW base",
    "usdw_t": "regional surface temperature plus gradient at the USDW base",
    "usdw_s": "10,000 ppm, the USDW limit at its base",
    "swr": "0.25 (median of the Texas applications)",
    "sgr": "0.25 (median of the Texas applications)",
    "krg0": "0.50 (median of the Texas applications)",
    "krw0": "1.0",
    "corey_w": "3.5 (median of the Texas applications)",
    "corey_g": "2.5 (median of the Texas applications)",
    "ppg": "9.0 ppg",
    "gel": "0 psi (not credited unless documented)",
    "end_year": "the last injection plus 50 years (40 CFR 146.93)",
    "cutoff": "0.01",
    "engine": "analytical in a project file (the form starts on ve); use ve for any AoR "
              "you will rely on",
    "method": "auto",
    "radius": "0.33 ft",
    "cell": "500 ft",
}


# what each option of a choice input does (form captions, tooltips, templates)
OPTIONS = {
    "engine": {
        "ve": "Vertical-equilibrium numerical simulator, Containment's main engine. It "
              "solves pressure implicitly on a grid and moves CO2 as a buoyant layer at "
              "the top of the zone, with dip, sealing faults, residual trapping, brine "
              "extraction wells, bottomhole-pressure limits, staged intervals and the plume's "
              "drift after injection stops. The grid grows by itself if the AoR reaches its "
              "edge. Use it for every AoR and PISC case. Limit: one layer per zone, with "
              "vertical flow assumed in equilibrium, so in very thick or layered packages it "
              "floats the CO2 to the top and spreads it further up-dip than a 3-D model.",
        "analytical": "Closed-form solutions: Theis line-source pressure for every well, "
                      "added together (superposition), with image wells for closed or "
                      "constant-pressure boundaries; plume radius from Nordbotten and Celia. "
                      "Runs in seconds; good for screening, sweeps and checking the VE "
                      "answer. Limits: a flat, uniform zone with no dip, no faults and no "
                      "buoyant migration after injection, and a circular plume per well, so "
                      "it cannot support a PISC timeframe.",
    },
    "method": {
        "auto": "Runs every method, keeps those that apply to the site's pressure regime "
                "(under-pressured, hydrostatic or over-pressured, EPA Eq-2), and uses the "
                "smallest threshold among them, which draws the largest, most protective "
                "pressure front. The recommended setting.",
        "method1": "Method 1, Thornhill equal hydraulic head (EPA Eq-1 and Eq-2): the "
                   "pressure at which the injection zone's head, through a column of its own "
                   "brine, equals the head at the base of the USDW. Applies to "
                   "under-pressured zones. The method most Class VI applications use.",
        "method2": "Method 2, Nicot uniform-density column (EPA Eq-3 and Eq-4): the open well "
                   "holds a fluid whose density changes linearly from the injection-zone brine "
                   "to the USDW water, so only the density contrast resists flow. Applies to "
                   "hydrostatic zones, where Method 1 gives about zero; it gives small "
                   "thresholds and large fronts.",
        "method2b": "Method 2b, variable-density lifted column: Method 1 refined, with "
                    "the brine density computed at each depth from the pressure and "
                    "temperature (Batzle and Wang) and integrated up the well. Uses the "
                    "measured pressures like Method 1 and, like it, applies only to under-pressured zones; "
                    "not an EPA method, a check on Method 1's constant density.",
        "mud_column": "Method 3, static mud column plus gel strength (Texas Class I "
                      "practice): an old well is assumed to still hold drilling mud (default "
                      "9.0 ppg) that must be pushed out, plus the mud's gel strength (default "
                      "0, credited only if documented). Usually the largest threshold and the "
                      "smallest front, so use it only where the mud is documented; EPA (2019 "
                      "letter to PEC) questioned relying on it otherwise.",
    },
}
OPTIONS_SHORT = {
    "engine": "ve (vertical-equilibrium simulator: dip, faults, migration, PISC) | analytical "
              "(closed-form screen, no dip or migration)",
    "method": "auto (smallest applicable, recommended) | method1 (equal head, under-pressured) "
              "| method2 (uniform-density column, hydrostatic) | method2b (variable-density "
              "column) | mud_column (Method 3, documented mud only)",
}


def options_text(key: str) -> str:
    """Every option of a choice input, one paragraph each, for tooltips and templates."""
    return "\n\n".join(f"{k}: {v}" for k, v in OPTIONS.get(key, {}).items())


def _merge() -> dict[str, InputInfo]:
    rng = _load_ranges()
    out: dict[str, InputInfo] = {}
    for key, path, label, unit, what, why in _WHY:
        r = rng.get(key, {})
        out[key] = InputInfo(
            key=key, path=path, label=label, unit=r.get("unit", unit), what=what, why=why,
            typical=tuple(r["typical"]) if r.get("typical") else None,
            plausible=tuple(r["plausible"]) if r.get("plausible") else None,
            seen=r.get("seen", ""), if_missing=r.get("if_missing", ""),
            sources=tuple(r.get("sources", ())), gradient=r.get("gradient", ""))
    return out


INPUTS: dict[str, InputInfo] = _merge()


def _fmt(v: float) -> str:
    if v == 0:
        return "0"
    a = abs(v)
    if a >= 1000:
        return f"{v:,.0f}"
    if a >= 10:
        return f"{v:.0f}"
    if a >= 1:
        return f"{v:.2g}" if a < 3 else f"{v:.1f}".rstrip("0").rstrip(".")
    if a >= 0.001:
        return f"{v:.3g}"
    return f"{v:.1e}"


def range_text(key: str, depth_ft: float | None = None) -> str:
    """'typical 0.15 to 0.32' in the input's own unit, or '' if none is defined.

    Pressure and temperature ranges are gradients; given the depth they apply
    at (ft), they are turned into values there.
    """
    info = INPUTS.get(key)
    if not info or not info.typical:
        return ""
    lo, hi = info.typical
    if info.gradient and depth_ft and depth_ft > 0:
        if info.gradient == "pressure":
            return (f"typical {_fmt(lo * depth_ft)} to {_fmt(hi * depth_ft)} psi at "
                    f"{depth_ft:,.0f} ft ({_fmt(lo)} to {_fmt(hi)} psi/ft)")
        if info.gradient == "temperature":
            return (f"typical {_fmt(62 + lo * depth_ft / 100)} to "
                    f"{_fmt(74 + hi * depth_ft / 100)} degF at {depth_ft:,.0f} ft "
                    f"(62 to 74 degF at surface plus {_fmt(lo)} to {_fmt(hi)} degF per 100 ft)")
    if info.gradient == "pressure":
        return f"typical {_fmt(lo)} to {_fmt(hi)} psi/ft times depth"
    if info.gradient == "temperature":
        return (f"typical 62 to 74 degF at surface plus {_fmt(lo)} to {_fmt(hi)} degF "
                "per 100 ft of depth")
    unit = "" if info.unit in ("fraction", "-") else f" {info.unit}"
    what = "thickness " if key == "cz" else ""
    return f"typical {what}{_fmt(lo)} to {_fmt(hi)}{unit}"


def help_text(key: str, base: str = "", depth_ft: float | None = None) -> str:
    """The full tooltip: what it is, why it matters, range, and what to do if missing."""
    info = INPUTS.get(key)
    if not info:
        return base
    parts = [f"What: {info.what}", f"Why Containment uses it: {info.why}"]
    rt = range_text(key, depth_ft)
    if rt:
        plaus = ""
        if info.plausible and not info.gradient:
            plaus = f" (plausible {_fmt(info.plausible[0])} to {_fmt(info.plausible[1])})"
        elif info.plausible:
            plaus = f" (plausible {_fmt(info.plausible[0])} to {_fmt(info.plausible[1])} {info.unit})"
        parts.append(f"Range: {rt[0].upper() + rt[1:]}{plaus}.")
    if info.seen:
        parts.append(f"In 15 Texas Class VI applications: {info.seen}.")
    if info.if_missing:
        parts.append(f"If the application does not give it: {info.if_missing}")
    if key in OPTIONS:
        parts.append("Options:\n\n" + options_text(key))
    if key in BLANK:
        parts.append(f"Left blank, Containment uses: {BLANK[key]}. It says so in the "
                     "run summary and the report.")
    if info.sources:
        parts.append("Sources: " + "; ".join(info.sources))
    return "\n\n".join(parts)


def check_value(key: str, value: float) -> str:
    """A warning if ``value`` (field units; a gradient for gradient inputs) is
    outside the plausible range, else ''."""
    info = INPUTS.get(key)
    if not info or not info.plausible or value is None:
        return ""
    lo, hi = info.plausible
    try:
        v = float(value)
    except (TypeError, ValueError):
        return ""
    if v < lo or v > hi:
        what = f"{info.label} gradient" if info.gradient else info.label
        return (f"{what} = {_fmt(v)} {info.unit} is outside the plausible range "
                f"{_fmt(lo)} to {_fmt(hi)} {info.unit}; check the value and its unit")
    return ""


__all__ = ["InputInfo", "INPUTS", "BLANK", "OPTIONS", "OPTIONS_SHORT", "options_text",
           "range_text", "help_text", "check_value"]
