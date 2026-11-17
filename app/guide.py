"""Help text for the browser app.

Three kinds of help live here, kept out of ``streamlit_app`` so that file
stays readable as a layout:

``FIELD``   one-line tooltips, hung off every input the user can turn.
``LEAD``    a short "what am I looking at" note at the top of each result tab.
``render`` draws the Help panel: quick start, glossary, limits, troubleshooting.

The wording assumes a permit engineer who knows the rule but not this tool.
Anything that is a modelling choice rather than a fact says so, because the
number a reviewer argues about is almost always a choice made here.
"""

from __future__ import annotations

import inspect

import streamlit as st

# --------------------------------------------------------------------------
# tooltips
# --------------------------------------------------------------------------
FIELD = {
    # ---- injection zone
    "iz_top": "Depth to the top of the injection zone, below ground surface. "
              "Sets the pressure and temperature the CO2 sees, and so its "
              "density.",
    "iz_h": "Net thickness that actually accepts CO2, not gross interval. "
            "The AoR scales roughly with the inverse of this: a thin zone "
            "spreads the same tonnage further.",
    "iz_phi": "Effective porosity of the net interval, as a fraction. Pore "
              "volume sets how far the plume has to travel to store the "
              "injected mass.",
    "iz_k": "Horizontal permeability of the injection zone. Drives the "
            "pressure buildup: lower permeability means a larger "
            "pressure-front AoR for the same rate.",
    "iz_t": "Formation temperature at injection depth. With pressure, it "
            "fixes CO2 density and viscosity through the equation of state.",
    "iz_s": "Formation brine salinity as total dissolved solids. Sets brine "
            "density and viscosity, and so the buoyancy contrast with CO2.",
    "iz_p": "Pre-injection (virgin) reservoir pressure at the datum. The "
            "buildup that matters for the AoR is measured from this.",
    "iz_cr": "Pore-volume compressibility of the rock. With brine "
             "compressibility it sets total storativity, which controls how "
             "fast pressure spreads.",
    "iz_dip": "Structural dip of the injection zone. Dip drives updip "
              "migration after injection stops, which is what usually decides "
              "the PISC timeframe.",
    "iz_az": "Compass direction the formation dips toward, in degrees from "
             "north. CO2 migrates in the opposite direction (updip).",
    # ---- confining zone and USDW
    "cz_top": "Top of the primary confining zone (the caprock). Used for the "
              "threshold-pressure calculation and for screening which "
              "artificial penetrations breach the seal.",
    "cz_base": "Base of the primary confining zone, normally the top of the "
               "injection zone.",
    "offshore": "Tick for a project in Texas state waters (Gulf of Mexico/America), "
                "where a USDW may not be present. The critical pressure is then "
                "measured against the mud line, or the base of the first permeable "
                "stratum below it, so that no fluid can be "
                "discharged to the seafloor [16 TAC 4.101, 5.206(b)(2)]. Measure "
                "every depth from sea level.",
    "water_depth": "Sea level to the mud line (seafloor). The mud-line pressure is "
                   "one atmosphere plus this much seawater (0.444 psi/ft).",
    "off_ref": "Whichever is more protective: the threshold is computed against "
               "both the mud line and the base of the first permeable stratum, and "
               "the lower critical pressure (the larger AoR) is used: the deepest depth "
               "necessary to ensure no discharge to the "
               "seafloor. Or pick one: the mud line (the seafloor itself), or the "
               "base of the first permeable bed below it.",
    "off_fp": "Depth below sea level of the base of the first permeable stratum "
              "under the mud line. Its pressure is taken as a seawater column "
              "from sea level.",
    "off_t": "Seafloor temperature, for the fluid density at the reference depth.",
    "usdw_base": "Depth to the base of the lowermost underground source of "
                 "drinking water. This is the interval 40 CFR 146.84 asks you "
                 "to protect, and the separation from it drives the "
                 "non-endangerment case.",
    "usdw_p": "Pressure in the lowermost USDW. With its depth, this sets the "
              "hydraulic head that formation fluid would have to overcome to "
              "reach the USDW.",
    "usdw_t": "Temperature in the lowermost USDW, for the fluid-density "
              "column used in the threshold calculation.",
    "usdw_s": "Salinity of the lowermost USDW. Under 10,000 ppm TDS is the "
              "regulatory definition of a USDW.",
    # ---- relative permeability
    "swr": "Irreducible brine saturation. Raising it shrinks the pore space "
           "available to CO2 and pushes the plume further out.",
    "sgr": "Residual CO2 saturation: the fraction left behind and trapped as "
           "the plume passes. The single most important control on whether "
           "the plume stops moving during PISC.",
    "krg0": "CO2 relative permeability at its end point. Higher values let "
            "CO2 move more freely against brine.",
    "corey": "Brooks-Corey exponent used for both phases. Higher exponents "
             "mean sharper, more piston-like displacement.",
    # ---- threshold pressure
    "method": "How the critical pressure buildup is computed. 'auto' runs "
              "every method, discards those that do not apply to this "
              "pressure regime, and takes the most protective survivor. "
              "Methods 1 and 2 follow EPA 816-R-13-005.",
    "ppg": "Drilling-mud weight assumed to be standing in an offset "
           "penetration, for the mud-column variant of the threshold "
           "calculation.",
    "gel": "Gel strength of that mud column, the extra pressure needed to "
           "break it into motion.",
    # ---- model
    "engine": "ve = vertical-equilibrium numerical solver: handles dip, "
              "heterogeneity and post-injection migration, and is what PISC "
              "needs. analytical = superposition of closed-form solutions: "
              "fast, but no gravity override and no migration after shut-in.",
    "boundary": "infinite acts as if the aquifer never ends (usually the "
                "conservative choice for pressure). constant_pressure "
                "represents an open, strongly connected aquifer. noflow "
                "represents sealing faults and gives the largest buildup.",
    "cell": "Fine-grid cell size near the wells. Smaller resolves the plume "
            "edge better and costs runtime; the run warns you if the AoR is "
            "resolved by too few cells.",
    "half": "Half-width of the modelled domain. It must comfortably exceed "
            "the pressure front, or the boundary condition contaminates the "
            "answer. The run warns you when it is too tight.",
    "end_year": "How far past the start of injection to simulate. It has to "
                "run well beyond the end of injection for the plume to "
                "stabilise, which is what the PISC demonstration rests on.",
    "cutoff": "Column-averaged CO2 saturation that counts as 'plume'. A "
              "defensible, disclosed choice, not a physical constant: "
              "lowering it grows the plume AoR.",
    # ---- run controls
    "uncertainty": "Adds a one-at-a-time tornado plus a Latin-hypercube Monte "
                   "Carlo, giving a probabilistic AoR. 40 CFR 146.93(c)(2)(vi) "
                   "requires a sensitivity analysis to support an alternative "
                   "PISC timeframe.",
    "realisations": "Monte Carlo sample count. 150 is enough for a stable "
                    "P10/P50/P90; more tightens the tails and costs runtime.",
    # ---- stacked injection zones
    "stacked": "Tick this when one wellbore is perforated in two or more "
               "formations. Each zone is then modelled separately, with its "
               "own pressure, its own CO2 density and its own threshold "
               "pressure, and the project AoR is the union of the zone AoRs.",
    "zone_table": "Give each zone its own confining interval where they "
                  "differ; leave those two columns blank to use the confining "
                  "zone section below for all of them.",
    "staged": "Staged completion (perforate a thin interval, inject, plug back, move "
              "up): give each stage its own row with open_thickness, and "
              "open_top_depth or an interval name. Each interval is modelled as its "
              "own isolated layer, so its pressure rise is not spread over the whole "
              "zone, and the AoR is the union. Leave these blank for a well open to "
              "the whole zone.",
    "well_zone": "Put a zone name in the `zone` column to send a well's whole "
                 "rate to that interval. Leave it blank for a commingled "
                 "completion and the rate is split between zones in "
                 "proportion to k*h.",
    "allocation_note": "A commingled rate is split by flow capacity, k*h, "
                       "which is where fluid goes when one tubing string "
                       "feeds several perforated intervals. It is an "
                       "assumption, not a measurement. If you have zonal "
                       "allocation from a spinner or distributed-temperature "
                       "survey, name the zone on each well row instead and "
                       "enter the measured rates.",
    # ---- well pressure and exports
    "well_pressure": "The highest bottomhole pressure the model demanded of "
                     "each well, against the limit that well declares. A rate "
                     "schedule that cannot be injected is not a plan, and the "
                     "AoR that follows from one is not this project's. Give a "
                     "well `max_bhp` to have it checked.",
    "static_map": "The same map as a PNG, on whichever basemap you pick. "
                  "Use it when the destination is a document: a permit "
                  "application, a board paper, a slide. The interactive HTML "
                  "map above is better wherever a browser is available.",
    "workbook": "Every input this run used, as one Excel workbook: project, "
                "units, zones, USDW, relative permeability, threshold, model, "
                "wells, faults, penetrations and uncertainty settings. It "
                "loads straight back in, so a colleague can fill it in without "
                "touching YAML. Type changes in the yellow 'your value' column; a "
                "blank cell keeps the value beside it.",
    "shapefile": "The same polygons as the GeoJSON, in the format state "
                 "agencies ask for. The zip holds .shp, .shx, .dbf and a .prj, "
                 "with the AoR, plume and pressure front as three records you "
                 "can symbolise apart.",
    # ---- wells and other panels
    "wells": "Rates are million tonnes of CO2 per year. start_year and "
             "stop_year are measured from the start of the simulation, so a "
             "well can come on late or stop early. A project file may give "
             "start_date and stop_date as calendar dates instead, and results "
             "then carry real dates alongside the model years.",
    "basemap": "Satellite imagery is the one to send to a landman. "
               "Topographic and shaded relief help when the argument is about "
               "surface access or drainage.",
    "pens_unit": "Unit for the x, y and depth columns in the uploaded CSV. "
                 "Everything is converted internally.",
    "georef": "Attach a coordinate reference system so the GeoJSON and KML "
              "land in the right place in GIS. An EPSG code is exact; an "
              "origin longitude and latitude is a local approximation that "
              "degrades with distance from that origin.",
    "epsg": "Projected CRS of the model's local frame. Texas State Plane and "
            "UTM zone 14N (EPSG:32614) cover most of the state. Check the "
            "units: several Texas codes are in US survey feet, not metres.",
}

# --------------------------------------------------------------------------
# panel leads
# --------------------------------------------------------------------------
LEAD = {
    "aor": "The <b>Area of Review</b> is the union of two footprints: where "
           "free-phase CO2 goes, and where pressure builds enough that "
           "formation fluid could reach a USDW through an open conduit. "
           "Whichever is larger controls, and the dashed outline is the "
           "union. Background shading is the maximum pressure buildup each "
           "location ever sees.",
    "gis": "The same delineation on real imagery, georeferenced from the well "
           "latitudes and longitudes. Toggle layers at the top right, and "
           "download a standalone copy to send to someone without this app.",
    "threshold": "The <b>threshold pressure</b> is the buildup above which "
                 "formation fluid could be driven into the lowermost USDW. It "
                 "is the largest discretionary lever in the whole "
                 "delineation, so every method is shown, not just the chosen "
                 "one. Hatched bars do not apply to this pressure regime and "
                 "are excluded from the automatic choice.",
    "pisc": "<b>Post-injection site care.</b> The default under 40 CFR 146.93 "
            "is 50 years. A shorter timeframe has to be earned with a "
            "demonstration that the plume has stopped moving and pressure has "
            "fallen below the threshold. The checklist at the bottom tracks "
            "what that demonstration still needs. With stacked zones every "
            "zone gets its own PISC numbers, and the last zone to stabilise "
            "sets the site's timeframe.",
    "corrective": "Artificial penetrations through the confining zone are the "
                  "realistic leakage pathway. Upload a well list and each one "
                  "is screened against the AoR, the seal, and the modelled "
                  "arrival time of pressure and of CO2, which is what phases "
                  "the corrective-action schedule.",
    "uncertainty": "Which inputs actually move the AoR, and how wide the "
                   "answer is when they move together. The tornado ranks them "
                   "one at a time; the Monte Carlo samples them jointly.",
    "zones": "This project injects into <b>more than one formation</b>. Each "
             "zone was modelled on its own grid, with CO2 properties at its "
             "own pressure and temperature and a threshold pressure from its "
             "own depth. The project AoR is the <b>geometric union</b> of the "
             "zone AoRs, because the rule protects a USDW from fluid movement "
             "out of any injection zone: ground only the deepest zone reaches "
             "is still inside the Area of Review. The zone table also gives "
             "each zone's PISC result.",
    "series": "The AoR as it would stand at each <b>re-evaluation date</b>. "
              "40 CFR 146.84(e) requires the delineation to be redone at "
              "least every five years, and the ground added between two "
              "dates is exactly what 146.84(e)(2) makes subject to "
              "artificial-penetration identification and corrective action.",
    "export": "Everything on this page, in formats a reviewer or a GIS can "
              "open. 40 CFR 146.84(g) requires the modelling inputs behind an "
              "AoR delineation to be retained for ten years: the project YAML "
              "plus the field archive is that record.",
    "help": "How to drive this tool, what the words mean, and where it should "
            "not be trusted.",
}

# --------------------------------------------------------------------------
# glossary
# --------------------------------------------------------------------------
# shown on the Threshold panel; opened automatically on an over-pressured site
THRESHOLD_SIGN = (
    "**Positive threshold (under-pressured or hydrostatic zone).** The injection zone "
    "starts below the pressure that would lift its brine up an open old well into the "
    "lowermost USDW. The threshold is how much injection can raise the pressure before "
    "that happens; the pressure front is drawn at that buildup. Methods 1 and 2 apply.\n\n"
    "**Negative threshold (over-pressured zone).** The zone is already above that "
    "pressure before any CO2 is injected, so Method 1's allowable increase is negative "
    "and Methods 1 and 2 do not apply. EPA 816-R-13-005 Section 3.4.1 gives three routes, "
    "in order: (1) a density-contrast offset: heavier brine can absorb some over-pressure, "
    "and Containment computes this as the 'Over-pressurised case' row; (2) if that is "
    "zero or negative too, numerical modelling of leakage up a hypothetical open well; "
    "(3) a demonstration that the leaked brine would not endanger the USDW (dilution or "
    "attenuation).\n\n"
    "**What Containment does.** With 'auto' it uses the smallest applicable positive "
    "value. If no method applies, it uses the smallest positive value from any method and "
    "labels it for review, which is a conservative bound, not a defensible threshold. "
    "Ask the operator for route 2 or 3. Example: Midland CCS #2 (offset disposal had "
    "raised the Devonian pressure; threshold -34 psi) ran borehole-leakage models and "
    "set its AoR on the CO2 plume.")

GLOSSARY = [
    ("Area of Review (AoR)",
     "The region around an injection well where formation fluids could be "
     "driven into a USDW. Under 40 CFR 146.84 it is delineated by computational "
     "modelling and re-evaluated at least every five years."),
    ("Texas well-history note",
     "A column on the Corrective action page from Johnston and Knape (1986, Texas "
     "Water Commission LP 86-06): what the abandonment date (RRC Rule 14 of 1967, "
     "rules from 1919), an uncased hole's region (closes on the Gulf Coast, stays open "
     "in hard West Texas rock), casing, mud plugs and a pre-1930 drilling date say "
     "about a well. It can move field-testing priority by one step; it never changes "
     "the action, which follows EPA's decision tree."),
    ("Over-pressured injection zone",
     "One whose initial pressure already exceeds what would lift its brine into the "
     "lowermost USDW through an open well, so the threshold pressure (Method 1) is "
     "negative. EPA 816-R-13-005 Section 3.4.1 then calls for a density-contrast offset, "
     "or failing that wellbore-leakage modelling or a USDW dilution demonstration. See "
     "the Threshold page."),
    ("Pressure-front AoR",
     "The contour where pressure buildup equals the threshold pressure. It is "
     "usually larger than the plume early in a project, and it shrinks once "
     "injection stops."),
    ("Plume AoR",
     "The footprint of free-phase (supercritical) CO2, taken here at the "
     "column-averaged saturation cutoff you set. Unlike pressure, it never "
     "shrinks: it keeps creeping updip until it is residually trapped."),
    ("Threshold (critical) pressure",
     "The pressure buildup in the injection zone that would just lift "
     "formation fluid into the lowermost USDW through a hypothetical open "
     "conduit. Computed here by the EPA 816-R-13-005 methods."),
    ("USDW",
     "Underground source of drinking water: an aquifer with less than "
     "10,000 mg/L total dissolved solids that is not exempted. The thing the "
     "whole programme exists to protect."),
    ("Confining zone",
     "The sealing interval above the injection zone. Its integrity is what "
     "makes the pressure-front criterion, rather than direct leakage, the "
     "governing concern."),
    ("Post-injection site care (PISC)",
     "Monitoring after injection stops, 50 years by default under "
     "40 CFR 146.93, until a non-endangerment demonstration is approved."),
    ("Non-endangerment demonstration",
     "The showing that the plume and pressure front have stabilised such that "
     "no further USDW endangerment is expected. Required to shorten PISC or "
     "close the site."),
    ("Corrective action",
     "Repair or re-plugging of artificial penetrations inside the AoR that "
     "could act as leakage conduits, under 40 CFR 146.84(d)."),
    ("Vertical equilibrium (VE)",
     "A modelling assumption that CO2 and brine segregate quickly compared "
     "with lateral flow, so the vertical saturation profile can be solved "
     "analytically and only the map view is stepped in time. Fast enough to "
     "run in a browser, and accurate for thin, well-connected zones."),
    ("Superposition (analytical engine)",
     "Closed-form pressure solutions summed over wells and time. No gravity "
     "override, no post-injection migration, so it is a cross-check and a "
     "Monte Carlo workhorse rather than a PISC tool."),
    ("Residual trapping (Sgr)",
     "CO2 left immobile behind the trailing edge of the plume. It is what "
     "eventually halts migration, and the PISC timeframe is highly sensitive "
     "to it."),
    ("Boundary condition",
     "How the model treats the edge of the domain: infinite, constant "
     "pressure (open aquifer), or no-flow (sealing faults). No-flow gives the "
     "largest buildup and the largest pressure-front AoR."),
    ("Plume cutoff",
     "The saturation that counts as plume edge. A disclosed modelling choice: "
     "state it in the permit, because a reviewer can and will ask."),
    ("Tornado / Monte Carlo",
     "One-at-a-time sensitivity ranking, and joint random sampling. Together "
     "they answer 'what moves the answer' and 'how wide is the answer'."),
    ("Stacked injection zones",
     "Two or more formations taking CO2 through one wellbore. Each is "
     "delineated on its own and the project AoR is the union of them; adding "
     "the zone acreages instead double-counts the overlap and overstates the "
     "AoR."),
    ("Commingled completion",
     "One tubing string open to several perforated intervals at once. Without "
     "a zonal allocation survey the rate into each is estimated from flow "
     "capacity k*h."),
    ("AoR re-evaluation",
     "The periodic redelineation required by 40 CFR 146.84(e), at least every "
     "five years. Ground newly inside the AoR must be screened for artificial "
     "penetrations and brought into the corrective-action plan."),
    ("Stabilisation",
     "The plume no longer expanding and pressure decaying below the "
     "threshold. Demonstrating it is the precondition for shortening PISC."),
]


# --------------------------------------------------------------------------
def render() -> None:
    """Draw the Help panel."""
    st.markdown("### Getting a result in five steps")
    st.markdown(
        "1. **Start.** Choose a new project (the form), open a project file (the Excel "
        "or YAML template), or a shipped example, which is the fastest way to see a "
        "finished run.\n"
        "2. **Site and zones.** Injection zone, confining zone and lowermost USDW. Every "
        "input has a tooltip saying what it is, why Containment needs it and where to "
        "find it, with its typical range under it. Tick 'use the reference' where the "
        "application does not give a value.\n"
        "3. **Wells.** One row per injection well. Latitude and longitude place the AoR "
        "on the GIS map.\n"
        "4. **Model settings, then Run.** The Run button is always in the sidebar; tick "
        "'run uncertainty analysis' first for the tornado and the probabilistic AoR. "
        "A project file that sets uncertainty enabled (the Coastal Bend example does) "
        "ticks it for you when it is loaded.\n"
        "5. **Read the results, then export.** Summary first, then Maps, Corrective "
        "action, Threshold and PISC. Export gives the GeoJSON, KML, shapefile, HTML "
        "report and project file that record what was run.\n\n"
        "The **User guide** and the **Equations and input data** document are under "
        "Documentation in the left menu, as Word and PDF. The guide walks through a "
        "whole project with real results; the equations document gives every formula "
        "and where each input goes.")

    st.markdown("### What each page is for")
    for label, key in (("Maps: plan view", "aor"), ("Maps: GIS map and faults", "gis"),
                       ("Maps: over time", "series"), ("Maps: zones", "zones"),
                       ("Threshold", "threshold"), ("PISC", "pisc"),
                       ("Corrective action", "corrective"),
                       ("Uncertainty", "uncertainty"), ("Export", "export")):
        st.markdown(
            f"<div class='aor-term'><dt>{label}</dt>"
            f"<dd>{LEAD[key]}</dd></div>", unsafe_allow_html=True)

    st.markdown("### Glossary")
    st.caption("Terms as 40 CFR 146 and EPA 816-R-13-005 use them.")
    left, right = st.columns(2)
    half = (len(GLOSSARY) + 1) // 2
    for col, chunk in ((left, GLOSSARY[:half]), (right, GLOSSARY[half:])):
        with col:
            for term, definition in chunk:
                st.markdown(
                    f"<div class='aor-term'><dt>{term}</dt>"
                    f"<dd>{definition}</dd></div>", unsafe_allow_html=True)

    st.markdown("### Input reference: why each input is needed, and its range")
    st.caption("For every input: what it is, what it changes in the AoR, the range to "
               "expect, what 15 Texas Class VI applications used, and how to estimate it "
               "when the application does not give it. Pressure and temperature ranges "
               "are gradients; the form turns them into values at your depth. Sources "
               "are in each input's tooltip and on the Input guide sheet of the workbook.")
    from containment import inputs_guide as ig
    st.dataframe(
        [{"input": i.label, "what it is": i.what, "why Containment uses it": i.why,
          "typical range": ig.range_text(i.key).replace("typical ", ""),
          "Texas applications": i.seen,
          "if the application does not give it": i.if_missing,
          "Containment's value if left blank": ig.BLANK.get(i.key, "required")}
         for i in ig.INPUTS.values()],
        hide_index=True,
        # newer Streamlit spells full width `width="stretch"`; older ones need the flag
        **({"width": "stretch"} if "width" in inspect.signature(st.dataframe).parameters
           else {"use_container_width": True}))

    st.markdown("### Injecting into more than one formation")
    st.markdown(
        "A well completed in two or more zones is not the same project as a "
        "well in one thicker zone, and cannot be modelled as one. Each zone "
        "sits at its own depth and pressure, so CO2 has a different density "
        "in each, each zone gets its own threshold pressure measured against "
        "the same USDW, and each spreads differently because k, h and "
        "porosity differ.\n\n"
        "This tool runs the whole delineation once per zone and takes the "
        "**geometric union** of the results. Two things follow that are worth "
        "stating in a permit:\n\n"
        "- The project AoR is **not** the sum of the zone AoRs. Stacked zones "
        "overlap heavily, so adding acreages can overstate the AoR by "
        "something approaching the number of zones. The Zones map view shows the "
        "union, the sum, and the overlap between them.\n"
        "- The **deepest zone often controls one direction and the shallowest "
        "another**, so the union has a shape neither zone has on its own. "
        "That shape is the thing to map and to screen for penetrations.\n\n"
        "Where the rate into each zone is not measured, it is split by flow "
        "capacity k*h. Name the zone on a well row to override that with a "
        "measured allocation.\n\n"
        "**Each zone on its own terms.** In the zone table a zone can carry its own "
        "threshold_override (psi), and in the project file or workbook its own "
        "relative permeability. That lets a staged project, where the same wells are "
        "recompleted zone by zone and each zone has its own critical pressure, run as "
        "one project: list each well once per zone with its zone and its years. Each "
        "zone is sampled on its own wells' schedule, and 'top' for the threshold datum "
        "means that zone's own top. On ten multi-zone Texas applications this gave the "
        "same AoR as running each zone alone and taking the union.\n\n"
        "**PISC per zone.** Every zone gets its own PISC result (zone table, and a "
        "zone picker above the PISC chart). The site cannot be released until every "
        "zone has stabilised, so the last zone to stabilise sets the timeframe (a zone "
        "that never stabilises in the model leaves PISC not demonstrated), and "
        "the run says so when that is not the zone with the largest AoR.")

    st.markdown("### Well history screen")
    st.markdown(
        "For every Texas penetration the corrective-action "
        "table adds a well-history note (Johnston and Knape 1986): rules and practice in "
        "force when the well was plugged, which can raise the priority of a "
        "records-only check. It never changes the action itself.")

    st.markdown("### Where this tool should not be trusted")
    st.warning(
        "**Thick injection zones.** The vertical-equilibrium engine assumes "
        "CO2 and brine segregate faster than they flow sideways. Validated "
        "against operator AoR figures it lands within about 2 percent on a "
        "250 ft zone, but runs 1.5 to 1.8 times wide on a 1,200 to 2,000 ft "
        "shale-punctuated interval. Treat a thick-zone AoR as a conservative "
        "upper bound and cross-check it against a full-physics simulator.")
    st.warning(
        "**Stacked zones are modelled as hydraulically independent.** Each "
        "zone is solved on its own grid, so pressure built up in one does not "
        "push back on another through a leaky seal or a shared aquifer leg. "
        "Where zones are known to be in communication, that assumption "
        "understates pressure buildup and the pressure-front AoR with it; "
        "carry such a case to a multi-layer simulator and import the result.")
    st.warning(
        "**Monte Carlo areas are not the base-case area.** The uncertainty "
        "run uses the fast analytical engine, so its absolute AoR areas are "
        "not comparable with a VE-engine result. Read the ratios and the "
        "ranking, not the raw acreage.")
    st.info(
        "**This is an engineering analysis, not a regulatory determination.** "
        "The permitting authority decides the AoR. What this tool produces is "
        "a defensible, reproducible, fully disclosed basis for proposing one.")

    st.markdown("### If something looks wrong")
    st.markdown(
        "- **The GIS map says it needs coordinates.** The wells were entered as x/y "
        "rather than latitude and longitude, so there is nothing to georeference "
        "against.\n"
        "- **A review flag on the Summary.** That is the run checking itself: domain "
        "too small for the pressure front, AoR resolved by too few cells, boundary "
        "influencing the answer, mass balance drifting, or a threshold method applied "
        "outside its pressure regime. Fix the flagged input and run again rather than "
        "reporting the number.\n"
        "- **The plume has not stopped moving.** Untick 'end the model 50 years after "
        "the last injection' on Model settings and raise the end year until it does. A "
        "PISC timeframe cannot be claimed from a run that ends while the plume is still "
        "migrating.\n"
        "- **A run is slow or runs out of memory.** Shrink the domain half-width or "
        "coarsen the cell size (Model settings, Advanced).")
