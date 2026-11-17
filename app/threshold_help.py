"""Threshold page: what each method assumes, its equation, this run's numbers.

The Threshold page shows a bar per method. This module explains each bar:
the physical picture behind it, the equation with this run's inputs filled
in, when the method is meant to be used, and why the table says what it says
in the regime and applicable columns. Text only; the numbers come from the
``ThresholdResult`` objects the run already produced.
"""

from __future__ import annotations

import math

import streamlit as st

TOL_PSI = 10.0  # threshold.classify_regime tolerance


def _get(inputs: dict, key: str, default=float("nan")):
    """Inputs are renamed usdw -> reference offshore; accept either."""
    if key in inputs:
        return inputs[key]
    return inputs.get(key.replace("usdw", "reference"), default)


def _f(v, fmt="{:,.0f}") -> str:
    try:
        return "n/a" if v is None or not math.isfinite(float(v)) else fmt.format(v)
    except (TypeError, ValueError):
        return str(v)


def _pick(results, prefix):
    for r in results:
        if r.method.startswith(prefix):
            return r
    return None


def _short(r) -> str:
    return r.method.split(" - ")[0]


# --------------------------------------------------------------------------
def render(results, selected, label: str = "USDW", requested: str = "auto") -> None:
    """Draw the "How the methods work" section under the threshold chart."""
    m1, m2 = _pick(results, "Method 1"), _pick(results, "Method 2 ")
    m2b, m3 = _pick(results, "Method 2b"), _pick(results, "Method 3")
    over = _pick(results, "Over-pressurised")

    st.markdown("### How the methods work")
    st.markdown(
        f"Every method answers the same question: **how much can injection raise the "
        f"injection-zone pressure before fluid would flow up an old, unplugged well into "
        f"the {label}?** That allowable rise is the threshold, dP_c. The pressure "
        f"front, and so the pressure part of the AoR, is drawn where the modelled buildup "
        f"equals it. A smaller threshold gives a larger AoR. The methods differ only in "
        f"what they assume is standing in the old well and which starting pressures they "
        f"trust.")

    # ---------------------------------------------------------------- summary
    rows = [
        "| Method | What is assumed to fill the old well | Starting pressures used | "
        "Meant for | This run (psi) | Applies here |",
        "|---|---|---|---|---|---|",
    ]

    def row(r, fill, press, meant):
        if r is None:
            return
        rows.append(f"| {_short(r)} | {fill} | {press} | {meant} | "
                    f"{_f(r.delta_p_psi)} | {'yes' if r.applicable else 'no'} |")

    row(m1, "injection-zone brine at one (bottom-hole) density",
        f"measured: injection zone and {label}", "under-pressured zone (EPA)")
    row(m2, f"fluid grading linearly from {label} water at the top to brine at the bottom",
        "none: assumes the zone starts hydrostatic", "hydrostatic zone (EPA)")
    row(m2b, "injection-zone brine, density recalculated at every depth",
        f"measured: injection zone and {label}", "refinement of Method 1, under-pressured zone (not EPA)")
    row(m3, "drilling mud (weight and gel strength), measured from the wellhead",
        f"injection zone only ({label} not used)", "Texas Class I practice, documented mud")
    row(over, "as Method 2, minus the excess pressure already present",
        "measured", "over-pressured zone (EPA option 1)")
    st.markdown("\n".join(rows))

    # ---------------------------------------------------------------- regime
    st.markdown("#### Pressure regime of this site")
    if m1 is not None:
        dp_if = m1.delta_p_psi
        pu, pi = _get(m1.inputs, "p_usdw_psi"), _get(m1.inputs, "p_inj_psi")
        rho = _get(m1.inputs, "rho_inj_kg_m3")
        sep = _get(m1.inputs, "separation_ft")
        regime = m1.regime
        st.markdown(
            f"The regime decides which EPA method applies. Containment fills an imaginary "
            f"open well with injection-zone brine ({_f(rho)} kg/m3) from the base of the "
            f"{label} down to the threshold depth ({_f(sep)} ft of column) and compares "
            f"the pressure that column would produce with the measured injection-zone "
            f"pressure (EPA Eq-2):")
        st.latex(r"\Delta P_{i,f} = P_u + \rho_i\, g\, (d_i - d_u) - P_i")
        st.markdown(
            f"Here: {_f(pu)} psi + {_f(m1.p_threshold_psi - pu)} psi (brine column) - "
            f"{_f(pi)} psi = **{_f(dp_if)} psi**.\n\n"
            f"- more than +{TOL_PSI:.0f} psi: **under-pressured**. The zone holds less "
            f"pressure than the brine column, so it can take that much more before brine "
            f"would rise into the {label}.\n"
            f"- within +/-{TOL_PSI:.0f} psi: **hydrostatic**. The zone is already in balance "
            f"with the column; Method 1 would give about zero (an unbounded front).\n"
            f"- less than -{TOL_PSI:.0f} psi: **over-pressured**. The zone would already push "
            f"brine up an open well before any injection.\n\n"
            f"This site is **{regime}**.")
    st.markdown(
        "**What the 'regime' column in the table means.** It is this classification as each "
        "method sees it. Methods 1, 2, 2b and the over-pressured row report the site regime "
        "and are marked applicable only in their own regime (Method 2b shares Method 1's: "
        "under-pressured). **Method 3 shows n/a** because it never "
        f"compares the injection zone with the {label}: its test is injection-zone pressure "
        f"against a column of mud from the wellhead, which does not depend on the {label} "
        "pressure at all, so under-, normally or over-pressured relative to the "
        f"{label} is not a question it asks. It is therefore never excluded by regime; whether "
        "it is acceptable is a permitting decision about the wells (is there documented mud in "
        "them?), not a pressure test. A 'user override' row also shows n/a for the same reason.")

    # ---------------------------------------------------------------- 1 vs 2
    st.markdown("#### Method 1 and Method 2: the difference")
    st.markdown(
        "Both picture the same thing: an open well connecting the two formations, with the "
        f"threshold reached when injection-zone brine can be pushed up to the {label}. They "
        "differ in where the starting pressure comes from.\n\n"
        f"- **Method 1** uses the **measured** initial pressures of the injection zone and the "
        f"{label}. The answer is how far the zone is below the pressure of a full brine column. "
        "It needs good pressure data and only makes sense when that gap is positive "
        "(under-pressured).\n"
        "- **Method 2** **does not use measured pressures**. It assumes the zone and the "
        f"{label} start in hydrostatic balance and that the old well initially holds fluid "
        f"whose density grades from {label} water at the top to brine at the bottom. The only "
        "thing resisting flow is the extra weight of brine compared with that graded column, so "
        "the answer depends only on the density contrast and the vertical separation. EPA "
        "offers it for the hydrostatic case, where Method 1 gives about zero.\n\n"
        "When the measured pressures happen to equal Method 2's assumed starting state, the two "
        "give the same number; Method 1 equals Method 2 if P_i = P_u + g (d_i - d_u) "
        "(rho_i + rho_u)/2. Method 2 is usually much smaller (here "
        f"{_f(m2.delta_p_psi if m2 else None)} vs {_f(m1.delta_p_psi if m1 else None)} psi), "
        "so applying it where Method 1 is valid would enlarge the AoR without a physical basis, "
        "and applying Method 1 where the zone is hydrostatic would make it unbounded. That is "
        "why each is limited to its regime.")

    # ---------------------------------------------------------------- per method
    st.markdown("#### Each method in detail")
    if m1 is not None:
        with st.expander(f"Method 1: Thornhill, equal hydraulic head (this run "
                         f"{_f(m1.delta_p_psi)} psi)"):
            i = m1.inputs
            st.markdown(
                "**Idea.** Fill a hypothetical open well, perforated in both the injection zone "
                f"and the {label}, with injection-zone brine at its bottom-hole density. The "
                "threshold is reached when the injection-zone pressure equals the pressure at "
                f"the bottom of that brine column standing on the {label} pressure (equal "
                "hydraulic head).")
            st.latex(r"P_{i,f} = P_u + \rho_i\, g\, (d_i - d_u) \qquad "
                     r"\Delta P_c = P_{i,f} - P_i")
            st.markdown(
                f"**This run.** P_u = {_f(_get(i, 'p_usdw_psi'))} psi at "
                f"{_f(_get(i, 'depth_usdw_ft'))} ft; P_i = {_f(i.get('p_inj_psi'))} psi at "
                f"{_f(i.get('depth_inj_ft'))} ft; rho_i = {_f(i.get('rho_inj_kg_m3'))} kg/m3 "
                f"({_f(i.get('rho_inj_lb_ft3'), '{:,.1f}')} lb/ft3); separation "
                f"{_f(i.get('separation_ft'))} ft. P_i,f = {_f(m1.p_threshold_psi)} psi, "
                f"dP_c = **{_f(m1.delta_p_psi)} psi**.\n\n"
                "**When it is used.** EPA 816-R-13-005 Section 3.4.1 applies it to any Class VI "
                "well whose injection zone is under-pressured relative to the "
                f"{label} (Eq-2 positive). It is the standard UIC pressure-front method "
                "(Thornhill et al., 1982) and the one most Class VI applications use.\n\n"
                "**Strengths and limits.** Conservative: assumes a fully open, brine-filled "
                "well with no plug, mud or cement. It holds the brine at bottom-hole density "
                "all the way up (Method 2b checks that). Sensitive to the measured pressures: "
                "an error of X psi in P_i or P_u moves the threshold by X psi.")
    if m2 is not None:
        with st.expander(f"Method 2: Nicot, uniform-density column (this run "
                         f"{_f(m2.delta_p_psi)} psi)"):
            i = m2.inputs
            st.markdown(
                "**Idea.** Assume the injection zone and the "
                f"{label} start in hydrostatic balance and the open well initially holds fluid "
                f"whose density grades linearly from {label} water at the top to injection-zone "
                "brine at the bottom (average density (rho_i + rho_u)/2). To push injection-zone "
                "brine to the top, injection has to make up the difference between a full brine "
                "column and that graded column.")
            st.latex(r"\xi = \frac{\rho_i - \rho_u}{d_i - d_u} \qquad "
                     r"\Delta P_c = \tfrac{1}{2}\, g\, \xi\, (d_i - d_u)^2 = "
                     r"\tfrac{1}{2}\, g\, (\rho_i - \rho_u)(d_i - d_u)")
            st.markdown(
                f"**This run.** rho_i = {_f(i.get('rho_inj_kg_m3'))} kg/m3, rho_u = "
                f"{_f(_get(i, 'rho_usdw_kg_m3'))} kg/m3 (contrast "
                f"{_f(i.get('delta_rho_kg_m3'), '{:,.1f}')} kg/m3), separation "
                f"{_f(i.get('separation_ft'))} ft, xi = {_f(i.get('xi_kg_m4'), '{:.4f}')} "
                f"kg/m4. dP_c = **{_f(m2.delta_p_psi)} psi**.\n\n"
                "**When it is used.** EPA Section 3.4.1 Method 2, for the hydrostatic case "
                f"(Eq-2 within +/-{TOL_PSI:.0f} psi here), where Method 1 gives about zero. "
                "Sources: Nicot et al. (2008), Bandilla et al. (2012); Birkholzer et al. (2011) "
                "note the uniform-density form is the conservative one. EPA asks that the "
                "hydrostatic assumption be re-checked once site pressure data exist.\n\n"
                "**Strengths and limits.** Needs no pressure data, only densities and depths, "
                "so it is useful early. It ignores the measured pressures entirely, so on an "
                "under-pressured site it understates the threshold (larger AoR) and on an "
                "over-pressured site it overstates it. It is zero or negative if the "
                f"injection-zone brine is not denser than the {label} water.")
    if m2b is not None:
        with st.expander(f"Method 2b: variable-density lifted column (this run "
                         f"{_f(m2b.delta_p_psi)} psi)"):
            i = m2b.inputs
            st.markdown(
                "**Idea.** Method 1 holds the lifted brine at its bottom-hole density all the "
                "way up the well. Real brine expands as the pressure drops on the way up and "
                "gets denser as it cools. Method 2b drops the constant-density assumption: it "
                "splits the column into 401 points, computes brine density at each from its "
                "pressure and temperature (Batzle and Wang, injection-zone salinity, "
                f"temperature on a straight line between the {label} and the injection zone), "
                "and integrates the column weight, iterating twice because the pressure "
                "depends on the density.")
            st.latex(r"\Delta P_c = P_u + \int_{d_u}^{d_i} \rho(d, P, T)\, g\, \mathrm{d}d - P_i")
            st.markdown(
                f"**This run.** Mean column density {_f(i.get('mean_column_density_kg_m3'))} "
                f"kg/m3 (Method 1 uses {_f(m1.inputs.get('rho_inj_kg_m3') if m1 else None)}), "
                f"column weight {_f(i.get('column_head_psi'))} psi over "
                f"{_f(i.get('separation_ft'))} ft. dP_c = **{_f(m2b.delta_p_psi)} psi**"
                + (f", {_f(m2b.delta_p_psi - m1.delta_p_psi, '{:+,.0f}')} psi from Method 1."
                   if m1 else ".") + "\n\n"
                "**What it really is.** Despite the '2b' label it is a refinement of "
                "**Method 1**, not of Method 2: it uses the measured starting pressures and a "
                "column of injection-zone brine, and with a constant density it gives exactly "
                "Method 1. The difference from Method 1 is the density correction, usually a "
                "few percent.\n\n"
                "**When it is used.** It is not an EPA method; it is a check on how much "
                "Method 1's constant-density shortcut matters at this site. Use it to answer "
                "a reviewer who asks whether brine density varies up the hole, or to support "
                "a site-specific threshold. Because it is Method 1 underneath, it has the same "
                "gate: it is marked applicable only when the site is under-pressured, and "
                "with 'auto' it is chosen only if it is then the smallest applicable value.")
    if m3 is not None:
        with st.expander(f"Method 3: static mud column plus gel strength (this run "
                         f"{_f(m3.delta_p_psi)} psi)"):
            i = m3.inputs
            st.markdown(
                "**Idea.** Old wells in Texas were drilled with mud, and an abandoned hole that "
                "was never cemented is assumed to still be full of it. For injection-zone "
                "fluid to move up the hole it has to lift the whole mud column, measured from "
                "the wellhead, and break the mud's gel strength (the stress a resting mud "
                "builds up, like a weak solid). The threshold is the pressure of that column "
                "minus the injection-zone pressure.")
            st.latex(r"P_{col} = P_s + \nabla p_{mud}\, d + \tau_{gel} \qquad "
                     r"\Delta P_c = P_{col} - P_i \qquad "
                     r"\nabla p_{mud}\,[\text{psi/ft}] = 0.052 \times W\,[\text{lb/gal}]")
            st.markdown(
                f"**This run.** Mud weight {_f(i.get('mud_weight_ppg'), '{:,.1f}')} lb/gal = "
                f"{_f(i.get('mud_gradient_psi_ft'), '{:.4f}')} psi/ft over "
                f"{_f(i.get('depth_inj_ft'))} ft from the wellhead, gel strength "
                f"{_f(i.get('gel_strength_psi'))} psi: mud column "
                f"{_f(i.get('mud_column_pressure_psi'))} psi against P_i "
                f"{_f(i.get('p_inj_psi'))} psi. dP_c = **{_f(m3.delta_p_psi)} psi**.\n\n"
                "**When it is used.** Texas Class I (TCEQ) practice, and several Texas Class VI "
                "AoR plans. It is not one of EPA's Class VI methods; EPA (2019 letter to PEC) "
                "questioned relying on it unless the mud is documented. Use it only for wells "
                "whose records show they were left full of mud.\n\n"
                "**Basis: Johnston and Knape (1986), Texas Water Commission report LP 86-06.** "
                "The Class I criterion it reviews: reservoir pressure (initial plus injection "
                "buildup) at any unplugged abandoned well must not exceed the hydrostatic head "
                "of its mud column, with 9 lb/gal assumed where records are missing (drillers "
                "reported native muds 'invariably' above 9 lb/gal; RRC Rule 14, from January 1, "
                "1967, requires at least 9.5 lb/gal mud between plugs, and EPA Region IV "
                "suggested 9.5 lb/gal as a conservative value). The report adds:\n"
                "- **Gel strength** gives an extra displacement pressure P [psi] = GS h / "
                "(300 D), GS in lb/100 ft2, h the mud column in ft, D the hole diameter in "
                "inches. Its example: 25 lb/100 ft2, 5,000 ft, 15 in gives 28 psi. Literature "
                "range 25 to 120 lb/100 ft2; assume at least 25 with no data. The authors call "
                "the gel term 'a relatively minor pressure restriction which should be regarded "
                "as a safety factor and NOT considered when developing operating parameters'. "
                "That is why Containment defaults gel strength to 0 psi. If you do credit it, "
                "enter the psi from this formula in the gel strength box.\n"
                "- **Incomplete fill.** The column may be shorter than the well: mud lost to a "
                "thief zone or casing pulled for salvage. Cased abandoned wells are not assumed "
                "full unless records show it. The report's rule: take the top of the mud at the "
                "thief zone. In Containment, enter the length of mud that remains (thief zone "
                "down to the injection zone) as the mud datum depth, since the column is "
                "computed as mud gradient times that depth.\n"
                "- **Borehole closure.** Uncased Gulf Coast holes and Triassic red beds close "
                "within hours to days; uncased holes in hard West Texas rock stay open for "
                "decades, and casing left in a hole is itself a conduit.\n"
                "- **Gel is not guaranteed.** Oil-base muds have no gel strength. Over long "
                "times at temperature, gels can break into filter cake and fluid pockets; acid "
                "shrinks gel and opens channels, which may not heal. Both matter for CO2, whose "
                "brine is acidic, and are reasons not to credit gel for Class VI.\n\n"
                "**Why the regime column says n/a.** See above: it compares the injection zone "
                f"with the mud column, not with the {label}, so the under-, normally and "
                "over-pressured classification does not apply to it.\n\n"
                "**Strengths and limits.** Usually the largest threshold and the smallest AoR. "
                "Very sensitive to the depth datum (the mud is measured from the wellhead; "
                "tens of feet of datum error moves it 10-20 psi) and to the mud weight (0.5 "
                "lb/gal over 8,000 ft is about 200 psi). It says nothing about wells that were "
                "cemented, partly plugged, or drilled with air or water.")
    if over is not None:
        with st.expander(f"Over-pressured case: density-contrast offset (this run "
                         f"{_f(over.delta_p_psi)} psi)"):
            i = over.inputs
            st.markdown(
                "**Idea.** When the zone is already over-pressured, Method 1 is negative. EPA "
                "Section 3.4.1 lets the extra weight of the brine (Method 2's term) absorb "
                "part of that over-pressure; what is left over is the allowable increase.")
            st.latex(r"A = \tfrac{1}{2} g (\rho_i - \rho_u)(d_i - d_u) - "
                     r"\left|\Delta P_{i,f}\right| \qquad \Delta P_c = \max(A, 0)")
            st.markdown(
                f"**This run.** Method 2 term {_f(i.get('dP_c_method2_psi'))} psi, existing "
                f"over-pressure {_f(i.get('dP_if_psi'))} psi, allowance "
                f"{_f(i.get('allowable_psi'))} psi.\n\n"
                "**When it is used.** Only for an over-pressured zone (EPA option 1). If the "
                "allowance is zero or negative, no closed-form threshold is defensible and EPA "
                "options 2 (numerical leakage modelling of an open well) or 3 (showing the "
                f"leaked fluid would not endanger the {label}) are needed.")

    # ---------------------------------------------------------------- choice
    st.markdown("#### Which one this AoR uses")
    if selected is None:
        return
    if requested in ("auto", "", "recommended"):
        why = ("'auto' was selected, so Containment took the smallest positive threshold "
               "among the methods marked applicable, because the smallest threshold gives "
               "the largest, most protective pressure front. Methods outside their regime "
               "(hatched bars) are excluded. If none is applicable, the smallest positive "
               "value is used and flagged for review.")
    elif selected.method == "user override":
        why = "A threshold was entered directly in the project, so no method was used."
    else:
        why = (f"The project asked for '{requested}', so that method is used whether or not "
               "it is the smallest or applicable here; check its row in the table.")
    st.markdown(f"This run uses **{_short(selected)}**, dP_c = "
                f"**{_f(selected.delta_p_psi)} psi**. {why}")
