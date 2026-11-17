"""Browser front end for the Containment.

    streamlit run app/streamlit_app.py      (or: containment app)

Everything the app does goes through :mod:`containment.workflow`, so what you see
here is exactly what the CLI and the report produce.  The app is a way to turn
the knobs and see the AoR move; the project YAML remains the record of what
was actually run.

The page is split into steps (Start, Site and zones, Wells, Model settings) and
result pages (Summary, Maps, Corrective action, Threshold, PISC, Uncertainty),
with Export and Help beside them. Navigation is a sidebar list held
in session state, so every page is reachable from every other and a test
harness can drive it the same way a user does.
"""

from __future__ import annotations

import hashlib
import html as _html
import inspect
import io
import json
import os
import pathlib
import sys
import tempfile
from dataclasses import replace

import numpy as np
import streamlit as st

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "src"))
# `streamlit run` puts the script's own directory on the path, but a test
# harness need not, so the sibling modules below get it explicitly.
sys.path.insert(0, _HERE)

import guide  # noqa: E402  (sibling module: help text)
import theme  # noqa: E402  (sibling module: page styling)
import threshold_help  # noqa: E402  (sibling module: threshold method explanations)

from containment import delineate, report, viz, workflow  # noqa: E402
from containment import inputs_guide as IG  # noqa: E402
from containment import pisc as pisc_mod  # noqa: E402
from containment import units as U  # noqa: E402
from containment.config import Project  # noqa: E402
from containment.io import exporters  # noqa: E402

st.set_page_config(page_title="Containment", page_icon="*",
                   layout="wide", initial_sidebar_state="expanded")
theme.apply()

H = guide.FIELD
SS = st.session_state


# --------------------------------------------------------------------------
# Streamlit moved on: `use_container_width` became `width=`, and
# `st.components.v1.html` became `st.iframe`, which takes a source rather than
# a string. Both old spellings still work but warn on every rerun, which
# buries real messages in the app's log. These helpers use whichever API the
# installed version has, so the package keeps its loose Streamlit floor.
_FULL_WIDTH = ({"width": "stretch"}
               if "width" in inspect.signature(st.button).parameters
               else {"use_container_width": True})
_BORDER: dict = {}             # theme.css draws the metric cards itself


def _embed_html(html: str, height: int = 640) -> None:
    """Put a self-contained HTML document (the folium map) in the page.

    Folium sizes its map div at ``height: 100%``, which needs a parent of
    known height. ``st.iframe`` sizes itself to its content, so 100% collapses
    and Leaflet computes its ``fitBounds`` against a container of no height --
    the map comes up zoomed out to the whole world. The embedded copy
    therefore gets an explicit pixel height; the string handed to the download
    button is left alone so the standalone file still fills its window.
    """
    if hasattr(st, "iframe"):
        doc = html.replace(
            "</head>",
            f"<style>html,body{{height:{height}px;overflow:hidden}}</style></head>",
            1)
        d = SS.get("_embed_dir")
        if d is None:
            d = SS["_embed_dir"] = tempfile.mkdtemp(prefix="containment-")
        path = pathlib.Path(d) / (
            hashlib.sha1(doc.encode("utf-8")).hexdigest()[:16] + ".html")
        if not path.exists():
            path.write_text(doc, encoding="utf-8")
            # keep the session's scratch directory from growing without bound
            kept = sorted(pathlib.Path(d).glob("*.html"),
                          key=lambda q: q.stat().st_mtime, reverse=True)
            for stale in kept[6:]:
                stale.unlink(missing_ok=True)
        st.iframe(path, height=height)
    else:                                     # Streamlit without st.iframe
        import streamlit.components.v1 as components

        components.html(html, height=height, scrolling=False)


EXAMPLES = os.path.join(os.path.dirname(_HERE), "examples")
DOCS = os.path.join(_HERE, "documents")
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


# ==========================================================================
# Form state
#
# The inputs live on three pages, and Streamlit forgets a widget's value when
# the widget is not drawn. Every form key therefore gets a default here and is
# written back to itself on each rerun (the documented way to keep a widget's
# value across pages); the widgets are then created with their key only. The
# project is built from these values, so Run works from any page.
REF_T = ("Regional surface temperature plus gradient, calibrated on 15 Texas Class VI "
         "applications (Gulf Coast 70 degF + 1.33 degF per 100 ft; Permian 65 + 0.75).")
REF_P = ("Calculated as a hydrostatic column of this site's brine, from its salinity and "
         "the regional temperature profile (Gulf Coast about 0.45 to 0.47 psi/ft).")

DEFAULTS = {
    "p_name": "New storage project", "p_operator": "", "p_permit": "",
    "iz_top": 6000.0, "iz_h": 250.0, "iz_phi": 0.18, "iz_k": 150.0,
    "iz_t": 150.0, "ref_iz_t": False, "iz_s": 90000.0,
    "iz_p": 2600.0, "ref_iz_p": False, "iz_cr": 5.0e-6, "ref_iz_cr": True,
    "iz_dip": 0.5, "iz_az": 180.0,
    "cz_top": 5700.0, "cz_base": 6000.0,
    "off": False, "off_wd": 40.0, "off_ref": "most_protective", "off_fp": 1200.0,
    "off_t": 70.0,
    "us_d": 1200.0, "us_p": 520.0, "ref_us_p": False, "us_t": 80.0, "ref_us_t": False,
    "us_s": 800.0,
    "swr": 0.35, "sgr": 0.20, "krg0": 0.30, "corey": 3.0,
    "method": "auto", "ppg": 9.0, "gel": 0.0,
    "engine": "ve", "boundary": "infinite", "dx": 500.0, "hw": 15.0,
    "ref_end": True, "end_year": 100.0, "cutoff": 0.01,
    "stacked": False, "unc": False, "n_real": 150,
    "source": "Form", "map_view": "Plan view", "pens_unit": "ft",
    "fault_reach": 1.0, "fault_mult": 0.0,
}
# widgets whose default is known only when drawn; kept once they exist
_KEEP = ("example_pick", "fault_layers", "basemap")

DEFAULT_ZONES = [
    {"name": "Upper zone", "top_depth": 5200.0, "thickness": 180.0,
     "porosity": 0.20, "permeability": 220.0, "temperature": 140.0,
     "salinity_ppm": 70000.0, "initial_pressure": 2250.0,
     "confining_top": 5000.0, "confining_base": 5200.0, "threshold_override": None},
    {"name": "Lower zone", "top_depth": 6000.0, "thickness": 250.0,
     "porosity": 0.18, "permeability": 150.0, "temperature": 150.0,
     "salinity_ppm": 90000.0, "initial_pressure": 2600.0,
     "confining_top": 5700.0, "confining_base": 6000.0, "threshold_override": None},
]
DEFAULT_WELLS = [
    {"name": "INJ-1", "latitude": 31.9686, "longitude": -99.9018,
     "rate": 0.5, "start_year": 0.0, "stop_year": 20.0,
     "interval": "", "open_top_depth": None, "open_thickness": None},
    {"name": "INJ-2", "latitude": 31.9686, "longitude": -99.8890,
     "rate": 0.5, "start_year": 0.0, "stop_year": 20.0,
     "interval": "", "open_top_depth": None, "open_thickness": None},
]
_ZONE_COLUMNS = ("name", "top_depth", "thickness", "porosity", "permeability",
                 "temperature", "salinity_ppm", "initial_pressure",
                 "confining_top", "confining_base", "threshold_override")

for _k, _v in DEFAULTS.items():
    SS[_k] = SS[_k] if _k in SS else _v
for _k in _KEEP:
    if _k in SS:
        SS[_k] = SS[_k]
SS.setdefault("page", "start")
SS.setdefault("_ed_ver", 0)
SS.setdefault("zones_rows", [dict(r) for r in DEFAULT_ZONES])
SS.setdefault("wells_rows", [dict(r) for r in DEFAULT_WELLS])


def _go(page: str) -> None:
    """Navigation callback. A new visit also gives the table editors a fresh
    base, so edits made on an earlier visit are not applied twice."""
    SS["page"] = page
    SS["_ed_ver"] = SS.get("_ed_ver", 0) + 1


def _request_run() -> None:
    SS["_run_req"] = True


def _blank(v) -> bool:
    return v is None or (isinstance(v, float) and np.isnan(v)) or str(v).strip() in (
        "", "nan", "None")


def _rows(edited) -> list[dict]:
    """Rows out of st.data_editor, whatever shape this Streamlit hands back.

    The editor returns "the same type as the input", but the exact spelling has
    moved between versions: a list of dicts here, a DataFrame there, and a
    version that skips the first row of a list default. Reading the rows
    through one helper keeps a version difference from quietly costing an
    injection zone, which is how a stacked project collapsed to a single zone
    on the deployed app while passing locally.
    """
    if edited is None:
        return []
    if hasattr(edited, "to_dict"):                    # a pandas DataFrame
        return [dict(r) for r in edited.to_dict("records")]
    out = []
    for r in edited:
        if isinstance(r, dict):
            out.append(dict(r))
        elif hasattr(edited, "loc"):                  # an index, not a row
            out.append(dict(edited.loc[r]))
    return out


def _zones_from_rows(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        if not str(r.get("name") or "").strip():
            continue
        z = {k: r.get(k) for k in _ZONE_COLUMNS
             if k not in ("confining_top", "confining_base") and not _blank(r.get(k))}
        if not _blank(r.get("confining_top")) and not _blank(r.get("confining_base")):
            z["confining_zone"] = {"top_depth": r["confining_top"],
                                   "base_depth": r["confining_base"]}
        out.append(z)
    return out


def _wells_from_rows(rows: list[dict], stacked: bool) -> list[dict]:
    out = []
    for r in rows:
        if _blank(r.get("name")):
            continue
        r = {k: v for k, v in r.items()
             if not (k in ("interval", "open_top_depth", "open_thickness", "zone")
                     and _blank(v))}
        if not stacked:
            r.pop("zone", None)
        out.append(dict(r, kind="injector"))
    return out


def _form_dict() -> dict:
    """The project as the form describes it, read from session state."""
    g = SS.get

    def ref(k):
        return None if g(f"ref_{k}") else g(k)

    offshore = bool(g("off"))
    if offshore:
        ref_kind = g("off_ref")
        reference = {"offshore": {
            "water_depth": g("off_wd"), "reference": ref_kind,
            "first_permeable_base": g("off_fp") if ref_kind != "mud_line" else None,
            "seafloor_temperature": g("off_t")}}
    else:
        reference = {"usdw": {k: v for k, v in {
            "base_depth": g("us_d"), "initial_pressure": ref("us_p"),
            "temperature": ref("us_t"), "salinity_ppm": g("us_s")}.items()
            if v is not None}}
    half = float(g("hw"))
    d = {
        "project": {"name": g("p_name"), "operator": g("p_operator"),
                    "permit": g("p_permit"),
                    "datum": ("sea level, depths positive downward" if offshore
                              else "ground surface, depths positive downward")},
        **({"offshore": reference["offshore"]} if offshore else {}),
        "units": {"length": "ft", "depth": "ft", "pressure": "psi",
                  "temperature": "F", "permeability": "mD", "rate": "MMT/yr",
                  "time": "yr", "compressibility": "1/psi"},
        "formation": {
            "injection_zone": {k: v for k, v in {
                "top_depth": g("iz_top"), "thickness": g("iz_h"),
                "porosity": g("iz_phi"), "permeability": g("iz_k"),
                "temperature": ref("iz_t"), "salinity_ppm": g("iz_s"),
                "initial_pressure": ref("iz_p"),
                "rock_compressibility": None if g("ref_iz_cr") else g("iz_cr"),
                "dip_degrees": g("iz_dip"), "dip_azimuth": g("iz_az")}.items()
                if v is not None},
            "confining_zone": {"top_depth": g("cz_top"), "base_depth": g("cz_base")},
            **({} if offshore else reference),
        },
        "relative_permeability": {"model": "brooks_corey", "swr": g("swr"),
                                  "sgr": g("sgr"), "krg0": g("krg0"),
                                  "m": g("corey"), "n": g("corey")},
        "threshold": {"method": g("method"), "mud_weight_ppg": g("ppg"),
                      "gel_strength": g("gel")},
        "model": {"engine": g("engine"), "boundary": g("boundary"),
                  **({} if g("ref_end") else {"end_year": g("end_year")}),
                  "grid": {"cell_size": g("dx"), "half_width": half * 5280.0,
                           "fine_half_width": min(half * 5280.0, 25000.0)}},
        "plume": {"cutoff": g("cutoff"),
                  "criterion": f"column-averaged CO2 saturation >= {g('cutoff'):g}"},
    }
    stacked = bool(g("stacked"))
    zones = _zones_from_rows(SS["zones_rows"]) if stacked else []
    if zones:
        d["formation"]["injection_zones"] = zones
    d["wells"] = _wells_from_rows(SS["wells_rows"], bool(zones))
    return d


_EXAMPLE_LABELS = {
    "epa_hypothetical_site.yaml": "EPA hypothetical site (guidance Box 3-1): 3 wells, 30 years",
    "gulf_coast_hub.yaml": "Gulf Coast Storage Hub: Matagorda County, 4 injectors and brine "
                           "extraction",
    "offshore_state_waters.yaml": "Offshore, Texas state waters: pressure at the mud line",
    "showcase_full.yaml": "Coastal Bend Storage Hub: every feature in one project",
    "stacked_zones.yaml": "Stacked Frio completion: one well, two injection zones",
}


def _example_files() -> list[str]:
    return sorted(f for f in os.listdir(EXAMPLES) if f.endswith((".yaml", ".yml")))


def _current_dict() -> dict | None:
    src = SS.get("source")
    if src == "Upload project":
        return SS.get("_upload_dict")
    if src == "Shipped example":
        import yaml

        files = _example_files()
        pick = SS.get("example_pick") or (files[0] if files else None)
        if not pick:
            return None
        with open(os.path.join(EXAMPLES, pick), encoding="utf-8") as fh:
            return yaml.safe_load(fh)
    return _form_dict()


# ==========================================================================
# Input widgets
def _why(key: str, depth: float | None = None) -> str:
    """Full tooltip for an input: what it is, why it is used, range, sources."""
    return IG.help_text(key, depth_ft=depth)


def _range(key: str, depth: float | None = None) -> str:
    rng = IG.range_text(key, depth)
    return rng[0].upper() + rng[1:] if rng else ""


def _num(col, label, unit, key, guide=None, depth=None, ref=None, help=None, **kw):
    """A number input in a column: unit in the label, the full explanation in
    its tooltip, and the typical range on one line under it.

    ``ref`` adds a 'use the reference value' box above it: ticked, the input is
    left out of the project and Containment fills it from reference_defaults,
    labelled as such in the run summary and the report."""
    tip = "\n\n".join(t for t in (help, _why(guide, depth) if guide else "") if t)
    if ref:
        col.checkbox(f"use the reference {label}", key=f"ref_{key}",
                     help="For when the application does not give it. " + ref
                          + " The value used and its source are listed in the run "
                            "summary and the report.")
    col.number_input(f"{label} ({unit})" if unit else label, key=key,
                     disabled=bool(ref and SS.get(f"ref_{key}")), help=tip or None, **kw)
    if guide and _range(guide, depth):
        col.caption(_range(guide, depth))


# ==========================================================================
# Templates
@st.cache_data(show_spinner=False)
def _project_templates() -> tuple[bytes, str]:
    """Excel and YAML project templates, filled in from the Gulf Coast example
    (wells in latitude/longitude, with a penetration list) so every sheet
    shows its format."""
    import yaml

    from containment.io import templates

    with open(os.path.join(EXAMPLES, "gulf_coast_hub.yaml"), encoding="utf-8") as fh:
        d = yaml.safe_load(fh)
    pens = os.path.join(EXAMPLES, "gulf_coast_wells.csv")
    d.setdefault("penetrations", {})["csv"] = pens
    return (templates.project_xlsx_template(d, penetrations_csv=pens),
            templates.project_yaml_template(d))


def _has_documents() -> bool:
    """True when Word or PDF documents are shipped in app/documents."""
    try:
        return any(f.lower().endswith((".pdf", ".docx")) for f in os.listdir(DOCS))
    except FileNotFoundError:
        return False


def _documents(where: str) -> None:
    """Download buttons for the documents shipped with the app (Word and PDF)."""
    try:
        files = sorted(f for f in os.listdir(DOCS) if f.lower().endswith((".pdf", ".docx")))
    except FileNotFoundError:
        return
    side = where == "side"
    cols = [st] * len(files) if side else st.columns(max(len(files), 1))
    for col, name in zip(cols, files, strict=False):
        with open(os.path.join(DOCS, name), "rb") as fh:
            data = fh.read()
        pdf = name.lower().endswith(".pdf")
        title = name.rsplit(".", 1)[0].removeprefix("Containment - ").capitalize()
        col.download_button(
            (f"{title} ({'PDF' if pdf else 'Word'})"
             if side else
             ("Open / download PDF" if pdf else "Download Word file") + f": {name.rsplit('.', 1)[0]}"),
            data, file_name=name, key=f"doc_{where}_{name}",
            icon=":material/picture_as_pdf:" if pdf else ":material/description:",
            mime="application/pdf" if pdf else
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            **({} if side else _FULL_WIDTH))


# ==========================================================================
# Result helpers
def _screen_upload(project, res):
    """Screen the uploaded well list (Corrective action page) before any page is
    drawn, so the maps show the same wells, coloured by action. Returns (plan
    or None, error or None). The screened list is kept while the user is on
    other pages (the uploader is not drawn there) and dropped when the file is
    removed, the unit changes or the run changes."""
    if "pens" in SS:
        up = SS.get("pens")
    else:                                   # uploader not drawn this run: keep
        kept = SS.get("_pens_screened")
        return (kept[1], kept[2]) if kept and kept[0][2] == id(res) else (None, None)
    if up is None:
        SS.pop("_pens_screened", None)
        return None, None
    unit = SS.get("pens_unit", "ft")
    sig = (getattr(up, "file_id", None) or (up.name, up.size), unit, id(res))
    kept = SS.get("_pens_screened")
    if kept and kept[0] == sig:
        return kept[1], kept[2]

    from containment import corrective
    from containment.io import templates as _tpl

    is_xlsx = up.name.lower().endswith(".xlsx")
    with tempfile.NamedTemporaryFile("wb", suffix=".xlsx" if is_xlsx else ".csv",
                                     delete=False) as fh:
        fh.write(up.getvalue())
        tmp = fh.name
    tmp_csv = tmp[:-5] + ".csv" if is_xlsx else tmp
    plan, err = None, None
    try:
        if is_xlsx:
            _tpl.penetrations_xlsx_to_csv(tmp, tmp_csv)
        wells = corrective.load_wells_csv(
            tmp_csv, unit=unit, crs=workflow.project_crs(project))
    except (KeyError, ValueError) as exc:
        wells, err = None, str(exc)
    finally:
        for _f in {tmp, tmp_csv}:
            if os.path.exists(_f):
                os.unlink(_f)
    if wells:
        cz_top = (project.confining_zone.top_depth
                  if np.isfinite(project.confining_zone.top_depth)
                  else project.injection_zone.top_depth - U.length(100, "ft"))
        cz_base = (project.confining_zone.base_depth
                   if np.isfinite(project.confining_zone.base_depth)
                   else project.injection_zone.top_depth)
        plan = corrective.screen(
            wells, res.aor, cz_top, cz_base,
            injectors=[(w.x, w.y) for w in project.wells if w.kind == "injector"])
        plan = corrective.arrival_times(
            plan, res.x, res.y, res.times,
            plume_fields=res.plume_fields,
            plume_level=(project.plume_cutoff if project.engine == "ve" else 0.5),
            dp_fields=res.dp_fields,
            threshold_pressure=res.selected_threshold.delta_p_critical)
    SS["_pens_screened"] = (sig, plan, err)
    return plan, err


def _time_view(where: str, project, res):
    """Year picker for a map. Returns (AoR result to draw, pressure field to
    shade, caption). The map shows the AoR as it stands at that year: the
    largest plume and pressure front so far. After injection stops, the
    pressure front at that year is drawn too, as a dotted outline, because it
    shrinks while the AoR does not. The final year is the delineated AoR."""
    years = workflow.model_years(res)
    if len(years) < 2:
        return res.aor, res.dp_fields.max(axis=0), ""
    labels = [f"{y:,.1f}".rstrip("0").rstrip(".") for y in years]
    inj_end = U.time_out(project.injection_end(), "yr")
    pick = st.select_slider(
        "Model year to show", options=list(range(len(years))), value=len(years) - 1,
        format_func=lambda i: f"year {labels[i]}", key=f"yr_{where}",
        help="The map shows the Area of Review as it stands at that year: the largest "
             "CO2 plume and pressure front up to then, which is the AoR a reviewer "
             "would approve if the project were evaluated then (EPA 816-R-13-005; "
             "40 CFR 146.84(e)). After injection stops the pressure falls, so the "
             "pressure front at that year is also drawn, dotted. Injection ends at "
             f"year {inj_end:,.1f}.")
    year = years[pick]
    t = np.asarray(res.times, float)
    i = max(int(np.searchsorted(t, U.time(year, "yr") + 1e-6, side="right")) - 1, 0)
    view = workflow.view_at(project, res, year, "to_date")
    if pick == len(years) - 1:
        # the delineated AoR, plus the shrunk pressure front if there is one
        view = replace(res.aor, metadata={**(res.aor.metadata or {}),
                                          **{k: v for k, v in view.metadata.items()
                                             if k.startswith("front_now") or k == "year"}})
    dp = res.dp_fields[:i + 1].max(axis=0)
    cap = (f"Year {labels[pick]}: AoR {view.area_acres:,.0f} acres "
           f"(final {res.aor.area_acres:,.0f} acres).")
    now = view.metadata.get("front_now")
    if now is not None and now.is_empty:
        cap += (f" By year {labels[pick]} the pressure rise is below the threshold "
                "everywhere; the AoR keeps its largest extent.")
    elif now is not None:
        cap += (f" The dotted line is the pressure front at year {labels[pick]} "
                f"({view.metadata['front_now_acres']:,.0f} acres): pressure has fallen "
                "since injection stopped, but the AoR keeps its largest extent.")
    return view, dp, cap


def _fault_rerun(reach_mi: float, ctx, basemap: str, project, res) -> None:
    """Re-run the project with the mapped faults near its AoR in the model.

    A sensitivity test: each mapped trace becomes a barrier across the grid
    faces it crosses (multiplier 0 sealing, 0.1 partly sealing). The run's own
    results are unchanged; the comparison is shown beside them."""
    from containment import fault_layers as _FL
    from containment import gis

    st.markdown("**Sensitivity: re-run with these mapped faults in the model**")
    if project.engine != "ve":
        st.caption("Needs the ve engine: the analytical engine has no faults.")
        return
    a_final = gis.aor_lonlat(res.aor, ctx)
    c1, c2 = st.columns([2, 1], vertical_alignment="bottom")
    mult = c1.selectbox(
        "treat the mapped faults as", [0.0, 0.1], key="fault_mult",
        format_func=lambda m: {0.0: "sealing (multiplier 0)",
                               0.1: "partly sealing (multiplier 0.1)"}[m],
        help="The transmissibility multiplier across each mapped fault. A map does not say "
             "whether a fault cuts the injection zone or seals; run both and treat sealing "
             "as the bound.")
    if c2.button("Re-run with mapped faults", key="fault_run", icon=":material/replay:",
                 **_FULL_WIDTH):
        faults = _FL.as_model_faults(a_final, reach_mi, mult)
        if not faults:
            st.info("No mapped fault within the screening distance to add.")
            return
        d = project.to_dict()
        d["faults"] = list(d.get("faults") or []) + faults
        with st.spinner(f"running with {len(faults)} mapped fault trace(s)"):
            r2 = workflow.run(Project.from_dict(d), run_uncertainty=False)
        SS["_fault_rerun"] = {"res": id(res), "mult": mult, "reach": reach_mi,
                              "n": len(faults), "r2": r2}
    got = SS.get("_fault_rerun")
    if not got or got["res"] != id(res):
        st.caption("Adds every mapped fault that crosses the AoR or lies within the screening "
                   "distance to the model as a barrier, re-runs, and compares. Your run is "
                   "not changed.")
        return
    r2 = got["r2"]

    def mi2(g):
        return 0.0 if g is None or g.is_empty else U.area_out(g.area, "mi2")

    st.dataframe([
        {"run": "as entered", "AoR (sq mi)": round(res.aor.area_sq_mi, 2),
         "plume (sq mi)": round(mi2(res.aor.plume), 2),
         "pressure front (sq mi)": round(mi2(res.aor.pressure_front), 2),
         "peak pressure rise (psi)": round(float(U.pressure_out(np.nanmax(res.dp_fields), "psi")))},
        {"run": f"with {got['n']} mapped fault trace(s), multiplier {got['mult']:g}",
         "AoR (sq mi)": round(r2.aor.area_sq_mi, 2), "plume (sq mi)": round(mi2(r2.aor.plume), 2),
         "pressure front (sq mi)": round(mi2(r2.aor.pressure_front), 2),
         "peak pressure rise (psi)": round(float(U.pressure_out(np.nanmax(r2.dp_fields), "psi")))},
    ], hide_index=True)
    from shapely.geometry import mapping
    a0 = gis.aor_lonlat(res.aor, ctx)
    extra = ({"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": mapping(a0),
         "properties": {"what": "AoR as entered (no mapped faults)"}}]} if a0 is not None else None)
    try:
        html2 = gis.map_html(r2.aor, gis.MapContext.from_project(project), wells=project.wells,
                             basemap=basemap, extra_geojson=extra,
                             title=f"{project.name} - AoR with mapped faults (multiplier "
                                   f"{got['mult']:g})",
                             fault_layers=SS.get("fault_layers") or [])
        _embed_html(html2, height=520)
    except Exception as exc:                  # a sensitivity view must not break the page
        st.info(f"The comparison map could not be drawn: {exc}")
    st.caption("Coloured layers: the AoR, plume and pressure front with the mapped faults as "
               "barriers. 'Additional layer': the AoR as entered. A sealing fault traps "
               "pressure on the wells' side and dams the plume; it can also shrink a front "
               "where withdrawal wells share the block. A mapped trace is not the fault at "
               "injection depth: this bounds the effect, it does not predict it.")


def _faults_near(project, res, reach_mi: float):
    """Mapped faults near the final AoR, or None when the project is not
    georeferenced or no layers ship with this copy."""
    try:
        from containment import fault_layers as _FL
        from containment import gis

        if not list(_FL.manifest()):
            return None
        a = gis.aor_lonlat(res.aor, gis.MapContext.from_project(project))
        return _FL.near_aor(a, reach_mi) if a is not None else None
    except Exception:
        return None


# ==========================================================================
# Pages: set up
def page_start(project, proj_err, res) -> None:
    theme.banner(
        "Containment",
        "Delineate the Area of Review, screen the wells that need corrective action and "
        "test the post-injection site care timeframe, from a project file a reviewer can "
        "open and rerun.",
        ("40 CFR 146.84 and 146.93", "EPA 816-R-13-005", "Texas fault maps built in",
         "Engineering analysis, not a regulatory determination"))
    theme.flow(["Describe the site", "Add the wells", "Choose the model", "Run",
                "Review and export"])

    c1, c2, c3 = st.columns(3)
    with c1:
        theme.card("📝", "New project", "Fill in the form step by step. Every input "
                   "explains itself and shows its typical range.")
    with c2:
        theme.card("📂", "Open a project file", "An Excel workbook or YAML file from the "
                   "templates below, or exported from this app.")
    with c3:
        theme.card("⚡", "Try an example", "Run a shipped project to see every result "
                   "page in under a minute.")
    st.write("")
    st.radio("How do you want to start?", ["Form", "Upload project", "Shipped example"],
             key="source", horizontal=True,
             format_func=lambda k: {"Form": "New project (form)",
                                    "Upload project": "Open a project file",
                                    "Shipped example": "Shipped example"}[k],
             help="The form builds a project step by step. A project file is the Excel "
                  "or YAML template filled in. A shipped example is the fastest way to "
                  "see a finished run.")

    src = SS["source"]
    if src == "Upload project":
        with st.container(border=True):
            st.markdown("**Open a project file**")
            st.caption("No file yet? Download a template, fill it in, then upload it. "
                       "The templates hold a worked example so every field shows its "
                       "format.")
            xlsx_t, yaml_t = _project_templates()
            t1, t2 = st.columns(2)
            t1.download_button(
                "Project template (Excel, recommended)", xlsx_t,
                "containment_project_template.xlsx", XLSX_MIME,
                icon=":material/table_view:", **_FULL_WIDTH,
                help="One sheet per part of the project, a Read me sheet, and the "
                     "artificial penetrations in the same file. Keep the sheet names "
                     "and column headers; change the values.")
            t2.download_button(
                "Project template (YAML)", yaml_t,
                "containment_project_template.yaml", "text/yaml",
                icon=":material/code:", **_FULL_WIDTH,
                help="The same project as a text file. Penetrations are uploaded "
                     "separately on the Corrective action page.")
            up = st.file_uploader("project file", type=["yaml", "yml", "xlsx"],
                                  key="proj_up",
                                  help="A YAML project file, or the Excel workbook "
                                       "this app writes from the Export page.")
            if up is not None:
                fid = getattr(up, "file_id", None) or (up.name, up.size)
                if SS.get("_upload_id") != fid:
                    try:
                        SS["_upload_dict"] = _read_project_file(up)
                        SS["_upload_name"] = up.name
                        SS["_upload_id"] = fid
                    except Exception as exc:
                        st.error(f"Could not read {up.name}: {exc}")
            if SS.get("_upload_dict"):
                st.success(f"Loaded {SS.get('_upload_name', 'the project file')}.",
                           icon=":material/check_circle:")
    elif src == "Shipped example":
        with st.container(border=True):
            st.markdown("**Shipped examples**")
            st.selectbox("example", _example_files(), key="example_pick",
                         format_func=lambda f: _EXAMPLE_LABELS.get(f, f),
                         help="Projects that ship with Containment, from a single "
                              "Gulf Coast well to stacked and offshore cases. All are "
                              "invented except the EPA site, which is EPA's own "
                              "hypothetical.")
    if src != "Form" and project is not None:
        st.button("Run this project", type="primary", key="run_start",
                  icon=":material/play_arrow:", on_click=_request_run)
    elif src == "Form":
        st.button("Next: Site and zones", type="primary", key="next_site",
                  icon=":material/arrow_forward:", on_click=_go, args=("site",))
    if proj_err:
        st.error(f"Could not read the project: {proj_err}")

    if _has_documents():
        st.write("")
        with st.container(border=True):
            st.markdown("**Documentation**")
            st.caption("Every equation, model and decision rule Containment uses, with "
                       "its symbols, units, defaults, sources and where each input is "
                       "used.")
            _documents("top")


def _read_project_file(up) -> dict:
    if up.name.lower().endswith(".xlsx"):
        # the workbook reader needs a real file, and it writes the
        # penetration list out beside it
        from containment.io import workbook

        tmpdir = SS.get("_upload_dir")
        if tmpdir is None:
            tmpdir = SS["_upload_dir"] = tempfile.mkdtemp(prefix="containment-upload-")
        book = os.path.join(tmpdir, up.name)
        with open(book, "wb") as fh:
            fh.write(up.getvalue())
        return workbook.from_excel(book)
    import yaml

    return yaml.safe_load(up.getvalue().decode("utf-8"))


def _not_form_note() -> bool:
    if SS.get("source") == "Form":
        return False
    st.info("This project comes from a "
            + ("file" if SS["source"] == "Upload project" else "shipped example")
            + ". Its inputs are set in that file; choose **New project (form)** on Start "
              "to edit them here.", icon=":material/info:")
    return True


def page_site(project, proj_err, res) -> None:
    theme.page_header("⛰️", "Site and zones",
                      "Where the CO2 goes, what holds it in, and what is protected.",
                      step="Step 1 of 3")
    if _not_form_note():
        return
    with st.container(border=True):
        st.markdown("##### Project")
        c1, c2, c3 = st.columns(3)
        c1.text_input("Name", key="p_name", help="Used in the map titles and the report.")
        c2.text_input("Operator", key="p_operator", help="As on the application.")
        c3.text_input("Permit number", key="p_permit", help="Optional.")

    with st.container(border=True):
        st.markdown("##### Injection zone")
        st.checkbox("inject into more than one formation (stacked completion)",
                    key="stacked", help=H["stacked"])
        if SS["stacked"]:
            _zone_table()
        else:
            top = SS["iz_top"]
            c1, c2, c3 = st.columns(3)
            _num(c1, "top depth", "ft", "iz_top", guide="iz_top", step=100.0)
            _num(c2, "net thickness", "ft", "iz_h", guide="iz_h", step=10.0)
            _num(c3, "porosity", "", "iz_phi", guide="iz_phi", min_value=0.01,
                 max_value=0.45, step=0.01)
            c1, c2, c3 = st.columns(3)
            _num(c1, "permeability", "mD", "iz_k", guide="iz_k", step=10.0)
            _num(c2, "salinity", "ppm", "iz_s", guide="iz_s", step=5000.0)
            _num(c3, "temperature", "degF", "iz_t", guide="iz_t", depth=top, step=5.0,
                 ref=REF_T)
            c1, c2, c3 = st.columns(3)
            _num(c1, "initial pressure", "psi", "iz_p", guide="iz_p", depth=top,
                 step=50.0, ref=REF_P)

    with st.container(border=True):
        st.markdown("##### Confining zone")
        if SS["stacked"]:
            st.caption("Used for any zone in the table without its own confining zone.")
        c1, c2, _ = st.columns(3)
        _num(c1, "top depth", "ft", "cz_top", step=50.0, help=H["cz_top"])
        _num(c2, "base depth", "ft", "cz_base", step=50.0,
             help=H["cz_base"] + "\n\n" + _why("cz"))

    with st.container(border=True):
        st.markdown("##### Lowermost USDW (or offshore reference)")
        st.checkbox("offshore project (no USDW)", key="off", help=H["offshore"])
        if SS["off"]:
            c1, c2, c3 = st.columns(3)
            _num(c1, "water depth", "ft", "off_wd", guide="water_depth", step=5.0)
            c2.selectbox(
                "critical-pressure reference",
                ["most_protective", "mud_line", "first_permeable"],
                format_func=lambda k: {"most_protective": "whichever is more protective "
                                                          "(compare both)",
                                       "mud_line": "mud line (seafloor)",
                                       "first_permeable": "base of first permeable "
                                                          "stratum below the mud line"}[k],
                key="off_ref", help=H["off_ref"])
            _num(c3, "seafloor temperature", "degF", "off_t", guide="off_t", step=1.0)
            if SS["off_ref"] != "mud_line":
                c1, _, _ = st.columns(3)
                _num(c1, "base of first permeable stratum", "ft", "off_fp", step=50.0,
                     help=H["off_fp"])
        else:
            c1, c2 = st.columns(2)
            _num(c1, "base depth", "ft", "us_d", guide="usdw_base", step=50.0)
            _num(c2, "salinity", "ppm", "us_s", guide="usdw_s", step=100.0)
            c1, c2 = st.columns(2)
            _num(c1, "initial pressure", "psi", "us_p", guide="usdw_p",
                 depth=SS["us_d"], step=10.0, ref=REF_P)
            _num(c2, "temperature", "degF", "us_t", guide="usdw_t", step=5.0, ref=REF_T)

    with st.expander("Advanced: rock compressibility, dip and relative permeability",
                     icon=":material/tune:"):
        c1, c2, c3 = st.columns(3)
        c1.checkbox("use the reference rock compressibility", key="ref_iz_cr",
                    help="Calculated from porosity: Hall (1953) for sandstone, Newman "
                         "(1973) for carbonate. Ticked by default: a correlation on this "
                         "site's porosity is closer than any single constant.")
        c1.number_input("rock compressibility (1/psi)", format="%.2e", key="iz_cr",
                        help=_why("iz_cr"), disabled=SS["ref_iz_cr"])
        c1.caption(_range("iz_cr"))
        _num(c2, "dip", "deg", "iz_dip", guide="iz_dip", step=0.1)
        _num(c3, "dip azimuth, direction of dip", "deg", "iz_az", guide="iz_az", step=15.0)
        st.markdown("**Relative permeability (Brooks-Corey)**")
        c1, c2, c3, c4 = st.columns(4)
        c1.slider("residual brine Swr", 0.05, 0.6, step=0.01, key="swr", help=_why("swr"))
        c2.slider("residual CO2 Sgr", 0.0, 0.4, step=0.01, key="sgr", help=_why("sgr"))
        c3.slider("CO2 end-point krg0", 0.05, 1.0, step=0.01, key="krg0",
                  help=_why("krg0"))
        c4.slider("Corey exponents (m = n)", 1.5, 5.0, step=0.1, key="corey",
                  help=H["corey"] + "\n\n" + _why("corey_w") + "\n\n" + _why("corey_g"))
        st.caption(f"{_range('swr')} (Swr); {_range('sgr').lower()} (Sgr); "
                   f"{_range('krg0').lower()} (krg0). Brine exponent "
                   + IG.range_text("corey_w")[8:] + ", CO2 exponent "
                   + IG.range_text("corey_g")[8:] + ".")
    _nav_buttons(None, "wells", "Next: Wells")


def _zone_table() -> None:
    """Stacked injection zones, one row each, replacing the single zone."""
    st.caption("One row per injection zone, shallowest first. Everything else on these "
               "pages (USDW, relative permeability, threshold method, grid) applies to "
               "every zone, except that a zone given its own threshold_override (psi) "
               "uses it instead of the threshold method. " + H["zone_table"])
    ver = SS["_ed_ver"]
    if SS.get("_zones_base_ver") != ver:
        SS["_zones_base"] = [dict(r) for r in SS["zones_rows"]]
        SS["_zones_base_ver"] = ver
    zcfg = {c: st.column_config.NumberColumn(
                c, help=(_range(k) + ". " if _range(k) else "") + "Why: " + IG.INPUTS[k].why)
            for c, k in (("top_depth", "iz_top"), ("thickness", "iz_h"),
                         ("porosity", "iz_phi"), ("permeability", "iz_k"),
                         ("temperature", "iz_t"), ("salinity_ppm", "iz_s"),
                         ("initial_pressure", "iz_p"))}
    zcfg["threshold_override"] = st.column_config.NumberColumn(
        "threshold_override (psi)",
        help="Optional. This zone's critical pressure buildup, when the application "
             "states one per zone. Blank: the threshold method on Model settings, "
             "computed for this zone's own depth and pressure.")
    SS["zones_rows"] = _rows(st.data_editor(SS["_zones_base"], num_rows="dynamic",
                                            key=f"zones_{ver}", column_config=zcfg))
    n = len(_zones_from_rows(SS["zones_rows"]))
    if n < 2:
        st.warning(f"The zone table has {n} usable row(s), so this is not a stacked "
                   "project. Every row needs a name, and a stack needs at least two. "
                   "Untick the box above to go back to a single injection zone.")


def page_wells(project, proj_err, res) -> None:
    theme.page_header("🛢️", "Injection wells",
                      "Locations, rates and injection years.", step="Step 2 of 3")
    if _not_form_note():
        return
    stacked = bool(SS["stacked"])
    with st.container(border=True):
        c1, c2 = st.columns([3, 2])
        c1.caption("Latitude and longitude place the AoR on the GIS map; x/y in feet from any origin also works. "
                   + H["wells"] + (" " + H["well_zone"] if stacked else ""))
        up = c2.file_uploader("import wells (CSV)", type=["csv"], key="wells_csv",
                              help="Columns: name, latitude, longitude (or x, y), rate, "
                                   "start_year, stop_year; optional interval, "
                                   "open_top_depth, open_thickness"
                                   + (", zone" if stacked else "") + ".")
        if up is not None:
            fid = getattr(up, "file_id", None) or (up.name, up.size)
            if SS.get("_wells_csv_id") != fid:
                import pandas as pd

                try:
                    df = pd.read_csv(io.BytesIO(up.getvalue()))
                    df.columns = [str(c).strip().lower() for c in df.columns]
                    SS["wells_rows"] = [{k: (None if _blank(v) else v) for k, v in r.items()}
                                        for r in df.to_dict("records")]
                    SS["_wells_csv_id"] = fid
                    SS["_ed_ver"] += 1
                except Exception as exc:
                    st.error(f"Could not read {up.name}: {exc}")
        ver = SS["_ed_ver"]
        if SS.get("_wells_base_ver") != ver:
            base = [dict(r) for r in SS["wells_rows"]]
            if stacked:
                for r in base:
                    r.setdefault("zone", "")
            SS["_wells_base"] = base
            SS["_wells_base_ver"] = ver
        cfg = {
            "rate": st.column_config.NumberColumn(
                "rate (MMT/yr)", help=_range("rate") + " per well. Why: "
                + IG.INPUTS["rate"].why),
            "interval": st.column_config.TextColumn(
                "interval", help="Staged completion only: a name shared by the wells "
                                 "injecting into the same stage, e.g. 'stage 3'."),
            "open_top_depth": st.column_config.NumberColumn(
                "open_top_depth (ft)", help="Staged completion only: top of the open "
                                            "(perforated) interval.", format="%.0f"),
            "open_thickness": st.column_config.NumberColumn(
                "open_thickness (ft)", help="Staged completion only: net thickness of "
                                            "the open interval. Blank = the whole zone. "
                                            + _range("open_h") + ". "
                                            + IG.INPUTS["open_h"].why,
                format="%.0f"),
        }
        SS["wells_rows"] = _rows(st.data_editor(SS["_wells_base"], num_rows="dynamic",
                                                key=f"wells_{ver}", column_config=cfg,
                                                **_FULL_WIDTH))
        with st.popover("Staged completions", icon=":material/layers:"):
            st.markdown(H["staged"])
    st.caption("Artificial penetrations (old wells inside the AoR) come after the run, on "
               "the Corrective action page, uploaded from the penetration template.")
    _nav_buttons("site", "model", "Next: Model settings")


def page_model(project, proj_err, res) -> None:
    theme.page_header("⚙️", "Model settings",
                      "Threshold pressure, engine and run options.", step="Step 3 of 3")
    form = SS.get("source") == "Form"
    if form:
        c1, c2 = st.columns(2)
        with c1, st.container(border=True):
            st.markdown("##### Threshold pressure")
            st.selectbox("method", ["auto", "method1", "method2", "method2b", "mud_column"],
                         key="method", help=_why("method"))
            st.caption(IG.OPTIONS["method"][SS["method"]])
            a, b = st.columns(2)
            _num(a, "mud weight", "ppg", "ppg", guide="ppg", step=0.1)
            _num(b, "gel strength", "psi", "gel", guide="gel", step=1.0)
        with c2, st.container(border=True):
            st.markdown("##### Model")
            st.radio("engine", ["ve", "analytical"], key="engine", horizontal=True,
                     help=_why("engine"))
            st.caption(IG.OPTIONS["engine"][SS["engine"]])
            st.checkbox("end the model 50 years after the last injection", key="ref_end",
                        help="The 50-year default post-injection site care period of 40 CFR "
                             "146.93, counted from the last well's stop year. Untick to set "
                             "the end yourself, for example to match the operator's model.")
            st.number_input("simulation end (years)", step=10.0, key="end_year",
                            help=_why("end_year"), disabled=SS["ref_end"])
        with st.expander("Advanced: boundary, grid and plume cutoff", icon=":material/tune:"):
            c1, c2, c3, c4 = st.columns(4)
            c1.selectbox("boundary", ["infinite", "constant_pressure", "noflow"],
                         key="boundary", help=H["boundary"])
            _num(c2, "fine cell size", "ft", "dx", guide="cell", step=50.0)
            _num(c3, "domain half-width", "mi", "hw", step=1.0, help=H["half"])
            c4.number_input("plume saturation cutoff", step=0.005, format="%.3f",
                            key="cutoff", help=_why("cutoff"))
            c4.caption(_range("cutoff"))
    else:
        _not_form_note()

    with st.container(border=True):
        st.markdown("##### Run options")
        c1, c2 = st.columns(2)
        c1.checkbox("run uncertainty analysis", key="unc", help=H["uncertainty"])
        c2.number_input("realisations", 40, 1000, step=10, key="n_real",
                        disabled=not SS["unc"], help=H["realisations"])

    if project is not None:
        with st.container(border=True):
            st.markdown("##### Before you run")
            if project.is_stacked:
                theme.flag("info", "Stacked completion: " + ", ".join(
                    f"<b>{_html.escape(z.name)}</b> ({U.length_out(z.top_depth, 'ft'):,.0f} ft, "
                    f"{U.length_out(z.thickness, 'ft'):,.0f} ft net)" for z in project.zones)
                    + ". Each is delineated separately and the project AoR is their union.")
            for w in project.warnings:
                theme.flag("warn", _html.escape(w))
            used = list(getattr(project, "defaults_used", []) or [])
            if used:
                theme.flag("info", f"<b>{len(used)} input(s) filled from reference "
                                   "values</b>, listed in the run summary and the report.")
            if not project.warnings:
                theme.flag("ok", "All inputs are inside their plausible ranges.")
            with st.expander("The project as Containment reads it"):
                st.json(project.summary(), expanded=False)
    elif proj_err:
        st.error(f"Could not read the project: {proj_err}")
    _nav_buttons("wells" if form else "start", None, None, run=project is not None)


def _nav_buttons(back: str | None, nxt: str | None, label: str | None,
                 run: bool = False) -> None:
    st.write("")
    c1, _, c3 = st.columns([1, 2, 1])
    if back:
        c1.button("Back", key=f"back_{SS['page']}", icon=":material/arrow_back:",
                  on_click=_go, args=(back,), **_FULL_WIDTH)
    if nxt:
        c3.button(label, key=f"next_{SS['page']}", type="primary",
                  icon=":material/arrow_forward:", on_click=_go, args=(nxt,),
                  **_FULL_WIDTH)
    elif run:
        c3.button("Run the model", key="run_model", type="primary",
                  icon=":material/play_arrow:", on_click=_request_run, **_FULL_WIDTH)


# ==========================================================================
# Pages: results
PISC_GOVERNS_HELP = (
    "Each zone gets its own PISC: the years after its injection ends until its plume has "
    "stopped moving AND its pressure is below its own AoR threshold. The site cannot be "
    "released until every zone is, so the zone that takes the longest governs PISC for "
    "the project. A zone that does not reach both conditions before the model ends counts "
    "as the longest, so it governs and the project PISC is not demonstrated.\n\n"
    "When zones tie (the same year, or none of them stabilises), the mark goes to the one "
    "with the largest AoR, whose pressure and plume fields are the ones the Maps and "
    "Corrective action pages use. Then 'governs PISC' does not mean that zone stabilises "
    "last: raise the model end year until each zone shows a year in the table above.\n\n"
    "Pick any zone here to see its own curves.")


def page_summary(project, res) -> None:
    s = res.summary()
    theme.page_header("📊", "Summary", f"{_html.escape(project.name)}: the Area of Review "
                      "and what to review first.")
    m1, m2 = st.columns(2)
    # The second line of each tile restates the same quantity another way, or
    # names the basis for it. None of them is a change, so delta_color="off"
    # keeps Streamlit from painting them as a rise.
    m1.metric("AoR area", f"{s['aor']['aor_area_acres']:,.0f} acres",
              f"{s['aor']['aor_area_sq_mi']:,.1f} sq mi", delta_color="off", **_BORDER)
    m2.metric("Threshold dP", f"{s['threshold']['delta_p_critical_psi']:,.0f} psi",
              s["threshold"]["method"].split(" - ")[0], delta_color="off", **_BORDER)
    # CO2 mass is on the project inputs and the PISC years on the PISC page,
    # so the Summary keeps only the AoR and its threshold.

    if getattr(project, "offshore", None):
        from containment.config import OFFSHORE_BASIS

        st.info(f"**Offshore project.** Critical pressure referenced to the "
                f"{project.reference_label} at "
                f"{U.length_out(project.usdw.base_depth, 'ft'):,.0f} ft below sea level "
                f"(water depth {U.length_out(project.offshore['water_depth'], 'ft'):,.0f} "
                f"ft). {OFFSHORE_BASIS}")
        if project.offshore.get("comparison"):
            st.caption("Both references were compared; the lower critical pressure "
                       "(the more protective AoR) is used:")
            st.dataframe(project.offshore["comparison"], hide_index=True)

    left, right = st.columns([3, 2])
    with left:
        try:
            fig = viz.plotly_aor_map(
                res.aor, x=res.x, y=res.y, dp_field=res.dp_fields.max(axis=0),
                wells=project.wells,
                penetrations=(res.corrective.wells if res.corrective else None))
            st.plotly_chart(fig, key="summary_map")
        except ImportError:
            st.pyplot(viz.aor_map(res.aor, x=res.x, y=res.y,
                                  dp_field=res.dp_fields.max(axis=0), wells=project.wells))
        st.caption("The final Area of Review. Maps has every model year, the GIS map with "
                   "Texas fault layers, and the AoR over time.")
    with right:
        st.markdown("##### Review flags")
        ctrl = s["aor"].get("controlling_component", "")
        theme.flag("info", f"The AoR is set by the <b>{_html.escape(str(ctrl))}</b>: plume "
                           f"{s['aor']['plume_area_acres']:,.0f} acres, pressure front "
                           f"{s['aor']['pressure_front_area_acres']:,.0f} acres.")
        if res.warnings:
            for w in dict.fromkeys(res.warnings):
                theme.flag("warn", _html.escape(w))
        else:
            theme.flag("ok", "Domain size, grid resolution, boundary influence, mass "
                             "balance and pressure regime all passed their checks.")
        well_rows = getattr(res, "well_pressure", []) or []
        over = [r for r in well_rows if r.get("verdict") == "EXCEEDS LIMIT"]
        if over:
            theme.flag("bad", f"<b>{len(over)} well(s) above the declared pressure "
                              "limit.</b> See the table below.")
        elif well_rows:
            theme.flag("ok", "Every well stays within its declared pressure limit.")
        thr = res.selected_threshold
        if thr.regime == "overpressured" or not any(t.applicable for t in res.thresholds):
            theme.flag("warn", "<b>Over-pressured injection zone</b>: the Method 1 threshold "
                               "is negative. Read the Threshold page before relying on the "
                               "pressure front.")
        near = _faults_near(project, res, 1.0)
        if near is not None:
            cross = sum(r["crosses the AoR"] == "yes" for r in near)
            if cross:
                theme.flag("warn", f"<b>{cross} mapped fault(s) cross the AoR</b> and "
                                   f"{len(near) - cross} more lie within 1 mi. See Maps, "
                                   "GIS map and faults.")
            elif near:
                theme.flag("info", f"{len(near)} mapped fault(s) within 1 mi of the AoR; "
                                   "none crosses it.")
            else:
                theme.flag("ok", "No mapped fault crosses the AoR or lies within 1 mi.")
        if res.corrective:
            theme.flag("info", "Corrective-action screen loaded: see Corrective action.")
        else:
            theme.flag("info", "No artificial-penetration list yet: "
                               "upload it on Corrective action.")
        if well_rows:
            with st.expander("Well pressure check", expanded=bool(over)):
                st.caption(H["well_pressure"])
                st.dataframe(well_rows, hide_index=True)

    st.markdown("##### Next")
    c1, c2, c3, c4 = st.columns(4)
    for col, (p, lab, ic) in zip((c1, c2, c3, c4), (
            ("maps", "Maps", ":material/map:"),
            ("corrective", "Corrective action", ":material/build:"),
            ("pisc", "PISC", ":material/hourglass_bottom:"),
            ("export", "Export", ":material/download:")), strict=True):
        col.button(lab, key=f"go_{p}", icon=ic, on_click=_go, args=(p,), **_FULL_WIDTH)


def page_maps(project, res) -> None:
    theme.page_header("🗺️", "Maps", "The AoR at any model year, on real imagery with "
                      "Texas fault layers, and over time.")
    zones = getattr(res, "zones", []) or []
    views = ["Plan view", "GIS map and faults", "Over time"] + (["Zones"] if zones else [])
    if SS.get("map_view") not in views:
        SS["map_view"] = "Plan view"
    view = st.radio("Map view", views, key="map_view", horizontal=True,
                    label_visibility="collapsed",
                    help="Plan view: the AoR on the model grid. GIS map: the same on "
                         "imagery with fault and earthquake layers. Over time: the AoR at "
                         "each re-evaluation date.")
    if view == "Plan view":
        _map_plan(project, res)
    elif view == "GIS map and faults":
        _map_gis(project, res)
    elif view == "Over time":
        _map_series(project, res)
    else:
        _map_zones(project, res, zones)


def _map_plan(project, res) -> None:
    s = res.summary()
    theme.lead(guide.LEAD["aor"])
    v, dp, cap = _time_view("aor", project, res)
    if cap:
        st.caption(cap)
    try:
        fig = viz.plotly_aor_map(
            v, x=res.x, y=res.y, dp_field=dp, wells=project.wells,
            penetrations=(res.corrective.wells if res.corrective else None))
        st.plotly_chart(fig)
    except ImportError:
        st.pyplot(viz.aor_map(v, x=res.x, y=res.y, dp_field=dp, wells=project.wells))
    st.caption("Hover any point for its pressure buildup; drag to zoom, double-click to "
               "reset. The camera icon saves a PNG.")
    with st.expander("Components, closed-form cross-checks and extent by azimuth"):
        c1, c2 = st.columns(2)
        c1.markdown("**Components**")
        c1.json({k: s["aor"][k] for k in
                 ("plume_area_acres", "pressure_front_area_acres",
                  "controlling_component", "plume_criterion")})
        c2.markdown("**Closed-form cross-checks**")
        c2.json({k: v for k, v in s["analytical_checks"].items() if k != "note"})
        st.caption(s["analytical_checks"]["note"])
        inj = [w for w in project.wells if w.kind == "injector"]
        if inj:
            az = res.aor.extent_by_azimuth(inj[0].x, inj[0].y, 16)
            st.markdown(f"**AoR extent by azimuth from {inj[0].name}**")
            st.dataframe(
                [{"azimuth (deg)": k, "distance (ft)": U.length_out(v, "ft"),
                  "distance (mi)": U.length_out(v, "mi")} for k, v in az.items()],
                hide_index=True)


def _map_series(project, res) -> None:
    theme.lead(guide.LEAD["series"])
    series = getattr(res, "series", []) or []
    if not series:
        st.info("No time series for this run.")
        return
    try:
        st.plotly_chart(viz.plotly_aor_series(series, wells=project.wells))
    except ImportError:
        st.pyplot(viz.aor_series_map(series, wells=[
            w for w in project.wells if w.kind == "injector"]))
    last, first = series[-1], series[0]
    st.info(f"The AoR grows from {first.area_acres:,.0f} acres at year {first.year:,.0f} "
            f"to {last.area_acres:,.0f} acres at year {last.year:,.0f}. Each snapshot is "
            "delineated from the largest fields up to that date: the AoR a reviewer would "
            "approve if the project were evaluated then.")
    st.pyplot(viz.aor_growth_chart(series, injection_end=project.injection_end()))
    st.markdown("**The re-evaluation ledger**")
    st.dataframe(delineate.series_growth(series), hide_index=True)
    st.caption("`newly_included_acres` is ground inside the AoR at that date that was "
               "outside it at the one before: the area 40 CFR 146.84(e)(2) makes subject to "
               "artificial-penetration identification and corrective action.")


def _map_zones(project, res, zones) -> None:
    theme.lead(guide.LEAD["zones"])
    try:
        st.plotly_chart(viz.plotly_zone_map(zones, res.aor, wells=project.wells))
    except ImportError:
        st.pyplot(viz.zone_map(zones, res.aor, wells=[
            w for w in project.wells if w.kind == "injector"]))
    union = res.aor.metadata.get("union_area_acres", res.aor.area_acres)
    summed = res.aor.metadata.get("sum_of_zone_areas_acres", union)
    c1, c2, c3 = st.columns(3)
    c1.metric("Project AoR (union)", f"{union:,.0f} acres", delta_color="off", **_BORDER)
    c2.metric("Zone areas added up", f"{summed:,.0f} acres",
              "not the AoR: double-counts the overlap", delta_color="off", **_BORDER)
    c3.metric("Overlap", f"{summed - union:,.0f} acres",
              f"{100 * (summed - union) / summed:,.0f} % of the sum" if summed else "",
              delta_color="off", **_BORDER)
    st.markdown("**Each zone on its own terms**")
    st.dataframe([z.summary() for z in zones], hide_index=True)
    st.caption("Each zone is modelled on its own grid, with CO2 properties at its own "
               "pressure and temperature and a threshold pressure from its own depth. "
               "Nothing is averaged across zones.")
    st.markdown("**How each zone's share of the rate was set**")
    st.dataframe(project.zone_allocation(), hide_index=True)
    st.caption(H["allocation_note"])


def _map_gis(project, res) -> None:
    theme.lead(guide.LEAD["gis"])
    try:
        from containment import fault_layers as _FL
        from containment import gis

        ctx = gis.MapContext.from_project(project)
        man = list(_FL.manifest())
        c1, c2 = st.columns([1, 2])
        base = c1.selectbox("basemap", list(gis.BASEMAPS), key="basemap",
                            format_func=lambda k: gis.BASEMAPS[k]["name"],
                            help=H["basemap"])
        shown = []
        if man:
            titles = {m["id"]: f"{m['title']} [{m['kind']}]" for m in man}
            kw = {} if "fault_layers" in SS else {
                "default": [m["id"] for m in man if m.get("show")]}
            shown = c2.multiselect(
                "Fault and earthquake layers", [m["id"] for m in man], key="fault_layers",
                format_func=lambda k: titles[k], **kw,
                help="Public fault maps bundled with the app (no internet needed). Surface "
                     "layers show where faults reach the ground; subsurface layers are "
                     "regional or basement interpretations. Neither is the application's own "
                     "fault interpretation at injection depth. Sources are listed below.")
        gview, _gdp, gcap = _time_view("gis", project, res)
        if gcap:
            st.caption(gcap)
        if not res.corrective:
            st.caption("To show wells here, coloured by corrective action, pull or upload "
                       "a well list on the Corrective action page.")
        yr = gview.metadata.get("year")
        html = gis.map_html(gview, ctx, wells=project.wells,
                            penetrations=res.corrective, basemap=base,
                            title=f"{project.name} - Area of Review"
                                  + (f", year {yr:,.1f}" if yr is not None else ""),
                            fault_layers=shown)
        _embed_html(html, height=620)
        st.caption(f"Georeferencing: {ctx.note}")
        d1, d2 = st.columns([1, 2])
        d1.download_button("Download this map (HTML)", html, "aor_map.html", "text/html",
                           icon=":material/download:", **_FULL_WIDTH,
                           help="Opens offline in any browser, with the basemaps, the layer "
                                "switcher and the measuring tool. The file to send to a "
                                "landman, a field inspector or a surface owner.")

        if man:
            with st.container(border=True):
                st.markdown("##### Mapped faults near the AoR")
                reach = st.number_input(
                    "screening distance from the AoR (mi)", min_value=0.0, step=0.5,
                    key="fault_reach",
                    help="List every mapped fault that crosses the AoR or lies within this "
                         "distance of it.")
                a_ll = gis.aor_lonlat(gview, ctx)
                near = _FL.near_aor(a_ll, reach)
                cross = [r for r in near if r["crosses the AoR"] == "yes"]
                if near:
                    (st.warning if cross else st.info)(
                        f"{len(cross)} mapped fault(s) cross the AoR and "
                        f"{len(near) - len(cross)} more lie within {reach:g} mi. Check "
                        "whether the application identifies them at injection depth, says "
                        "whether they seal or could be pathways, and accounts for them in "
                        "its model (40 CFR 146.82(a)(3)(ii), 146.83(a)(1)).")
                    st.dataframe(near, hide_index=True)
                else:
                    st.success(f"No mapped fault crosses the AoR or lies within {reach:g} mi.")
                eq = _FL.earthquakes_near(a_ll, max(reach, 5.0))
                if eq:
                    st.caption(
                        f"TexNet: {eq['count']} earthquake(s) of magnitude 2 or more since "
                        f"2017 within {eq['distance_mi']:g} mi of the AoR"
                        + (f", largest M{eq['max_magnitude']:.1f}." if eq["count"] else ".")
                        + " Earthquakes can mark active faults that no map shows.")
                st.caption(
                    "Mapped faults are context, not a model input: most are surface traces "
                    "or regional trends, not fault planes at injection depth. The model uses "
                    "the faults entered in the project (Faults sheet, or faults: in YAML).")
                _fault_rerun(reach, ctx, base, project, res)
            with st.expander("Sources of the fault and earthquake layers"):
                st.dataframe([{"layer": m["title"], "kind": m["kind"], "features": m["count"],
                               "source": m["source"], "licence": m["licence"],
                               "note": m["note"]} for m in man], hide_index=True)

        with st.expander("The same map as a picture, for documents"):
            st.caption(H["static_map"])
            cols = st.columns(len(gis.BASEMAPS))
            for col, key in zip(cols, gis.BASEMAPS, strict=True):
                if col.button(gis.BASEMAPS[key]["name"], key=f"static_{key}", **_FULL_WIDTH):
                    SS["_static_basemap"] = key
            chosen = SS.get("_static_basemap")
            if chosen:
                with st.spinner(f"fetching {gis.BASEMAPS[chosen]['name']} tiles"):
                    try:
                        figure = gis.static_map(
                            res.aor, ctx, basemap=chosen, wells=project.wells,
                            penetrations=res.corrective,
                            title=f"{project.name} - Area of Review")
                        buf = io.BytesIO()
                        figure.savefig(buf, dpi=200, bbox_inches="tight",
                                       facecolor=figure.get_facecolor())
                        st.pyplot(figure)
                        st.download_button(
                            f"Download the {gis.BASEMAPS[chosen]['name']} map (PNG)",
                            buf.getvalue(), f"aor_{chosen}.png", "image/png")
                    except Exception as exc:
                        st.warning(f"the basemap tiles could not be fetched: {exc}")
    except ImportError as exc:
        st.warning(str(exc))
    except ValueError as exc:
        st.info(str(exc))


def page_corrective(project, res, pens_plan, pens_error) -> None:
    theme.page_header("🛠️", "Corrective action",
                      "Old wells inside the AoR, screened against the seal and the modelled "
                      "arrival of pressure and CO2.")
    theme.lead(guide.LEAD["corrective"])
    from containment.io import templates as _templates

    with st.container(border=True):
        st.markdown("##### Upload the artificial penetrations")
        st.caption("One row per well, from the template. Only name and a "
                   "location (latitude/longitude, or x/y) are required; plug depths and "
                   "records decide whether a well is a candidate for re-entry.")
        p1, p2 = st.columns(2)
        p1.download_button(
            "Penetration template (Excel)", _templates.penetrations_xlsx_template(),
            "penetrations_template.xlsx", XLSX_MIME, icon=":material/table_view:",
            **_FULL_WIDTH,
            help="A Penetrations sheet with three example rows, a Columns sheet saying "
                 "what each column takes, and Instructions.")
        p2.download_button(
            "Penetration template (CSV)", _templates.penetrations_csv_template(),
            "penetrations_template.csv", "text/csv", icon=":material/csv:", **_FULL_WIDTH,
            help="The same columns and example rows as a CSV file.")
        c1, c2 = st.columns([3, 1])
        with c1:                            # st.file_uploader: tests stand in for it
            up = st.file_uploader("well list", type=["xlsx", "csv"], key="pens",
                                  help="The filled-in penetration template.")
        c2.radio("coordinate and depth unit", ["ft", "m"], horizontal=True,
                 help=H["pens_unit"], key="pens_unit")
    plan = pens_plan if up is not None else (pens_plan or res.corrective)
    if up is not None and pens_error:
        st.error(f"Could not read the well list ({pens_error}). Every row needs a location: "
                 "x and y, or latitude and longitude. Latitude/longitude only works when the "
                 "project is georeferenced (injection wells given in latitude/longitude, or "
                 "a CRS set). Compare your file with the template.")
    elif up is not None and pens_plan is None:
        st.warning("The well list has no rows.")
    elif plan:
        if up is not None:
            st.caption("These wells are also on the GIS map, coloured by action.")
        st.dataframe(plan.table(), hide_index=True)
        st.caption("Action follows EPA's decision tree (816-R-13-005 Figure 4-3). The "
                   "texas_history_note column adds Texas well-history context from Johnston "
                   "and Knape (1986, TWC LP 86-06): plugging after RRC Rule 14 (1967) lowers "
                   "a records-only field-testing priority by one, and an uncased hole west "
                   "of 99 W (hard rock, stays open) raises it by one. It never clears a "
                   "well.")
        c1, c2 = st.columns(2)
        with c1.expander("Screen summary"):
            st.json(plan.summary())
        with c2.expander("Phased corrective action by modelled arrival time"):
            st.json(plan.phases())
    else:
        st.info("No well list loaded yet.")


def page_threshold(project, res) -> None:
    theme.page_header("📈", "Threshold pressure",
                      "The pressure rise that would lift brine into the USDW through an "
                      "open well.")
    theme.lead(guide.LEAD["threshold"])
    over = (res.selected_threshold.regime == "overpressured"
            or any(t.regime == "overpressured" for t in res.thresholds)
            or not any(t.applicable for t in res.thresholds))
    if over:
        st.warning("This injection zone is over-pressured relative to the lowermost USDW: "
                   "the threshold from Method 1 is negative. Read the note below before "
                   "relying on the pressure-front AoR.")
    c1, c2 = st.columns([3, 2])
    c1.pyplot(viz.threshold_comparison(res.thresholds, res.selected_threshold))
    with c2:
        with st.expander("Positive or negative threshold: what it means and what to do",
                         expanded=over):
            st.markdown(guide.THRESHOLD_SIGN)
        st.caption("Methods 1 and 2 follow EPA 816-R-13-005 section 3.4.1. Method 2b is "
                   "Method 1 with the brine density recalculated at every depth; Method 3 "
                   "assumes drilling mud still stands in the hole. Each is explained below "
                   "the table.")
    st.dataframe([t.summary() for t in res.thresholds], hide_index=True)
    threshold_help.render(res.thresholds, res.selected_threshold,
                          label=res.project.reference_label,
                          requested=res.project.threshold_method)


def page_pisc(project, res) -> None:
    theme.page_header("⏳", "Post-injection site care",
                      "Does the model support a timeframe other than 50 years?")
    theme.lead(guide.LEAD["pisc"])
    if res.pisc is None:
        st.info("No PISC analysis for this run.")
        return
    s = res.summary()
    _rp = s["pisc"]["recommended_pisc"]
    (st.success if np.isfinite(_rp.get("recommended_years", float("nan"))) else st.warning)(
        _rp["verdict"], icon=":material/gavel:")
    shown = res.pisc
    zones = [zr for zr in (getattr(res, "zones", None) or []) if zr.pisc is not None]
    if len(zones) > 1:
        # Each zone has its own plume, pressure and threshold; the project's
        # PISC is set by the last zone to stabilise.
        st.markdown("##### Every injection zone")
        st.caption("Each zone is modelled on its own and has its own threshold. The project "
                   "cannot be released until every zone is, so one zone is marked 'governs "
                   "PISC' and its curves are shown first (the ? next to the zone list says "
                   "how it is picked). Years are after the end of that zone's injection; a "
                   "blank was not reached in the model.")
        st.dataframe(pisc_mod.zone_table(zones, res.pisc), hide_index=True)
        names = [zr.name for zr in zones]
        first = next((i for i, zr in enumerate(zones) if zr.pisc is res.pisc), 0)
        pick = st.selectbox("show the curves of", names, index=first, key="pisc_zone",
                            format_func=lambda n: n + ("  (governs PISC)" if
                                                       zones[names.index(n)].pisc is res.pisc
                                                       else ""),
                            help=PISC_GOVERNS_HELP)
        shown = zones[names.index(pick)].pisc
    try:
        st.plotly_chart(viz.plotly_pisc(shown))
    except ImportError:
        st.pyplot(viz.pisc_panels(shown))
    st.markdown("\n".join(f"- **{name}.** {text}" for name, text in pisc_mod.CURVE_NOTES)
                + "\n- The dotted vertical line on every panel is the end of injection.")
    st.dataframe(shown.table(), hide_index=True)
    c1, c2 = st.columns([2, 3])
    if res.pisc.directional:
        c1.pyplot(viz.migration_rose(res.pisc.directional))
    with c2:
        st.markdown("**40 CFR 146.93(c) demonstration checklist**")
        st.dataframe(pisc_mod.alternative_timeframe_checklist(
            res.pisc,
            abandoned_wells_assessed=bool(res.corrective),
            conduits_identified=bool(res.corrective),
            sensitivity_analysis_done=bool(res.uncertainty),
            usdw_separation=(project.injection_zone.top_depth - project.usdw.base_depth),
            reference_label=project.reference_label), hide_index=True)


def page_uncertainty(project, res) -> None:
    theme.page_header("🎲", "Uncertainty",
                      "Which inputs move the AoR, and how wide the answer is.")
    theme.lead(guide.LEAD["uncertainty"])
    unc = res.uncertainty or {}
    if not unc:
        st.info("Tick 'run uncertainty analysis' on Model settings and run again for a "
                "tornado chart and a probabilistic AoR. 40 CFR 146.93(c)(2)(vi) requires a "
                "sensitivity analysis to support an alternative PISC timeframe.")
        return
    st.warning(unc.get("comparability", ""))
    st.pyplot(viz.tornado_chart(unc["_tornado_obj"]))
    mc = unc["_monte_carlo_obj"]
    c1, c2 = st.columns(2)
    with c1:
        st.pyplot(viz.monte_carlo_histogram(mc))
    with c2:
        st.pyplot(viz.probabilistic_aor_map(mc, wells=project.wells))
    st.markdown("**Rank correlation with AoR area**")
    st.dataframe(mc.correlations("aor_area_acres"), hide_index=True)
    st.json({"percentiles (acres)": mc.percentiles("aor_area_acres"),
             "ratio to the ensemble base case": unc.get("percentile_ratio_to_base", {})})


def page_export(project, res) -> None:
    theme.page_header("📦", "Export", "Maps, report, inputs and fields, as files.")
    theme.lead(guide.LEAD["export"])
    s = res.summary()
    crs = None
    with st.expander("Georeference the map files (optional)", icon=":material/public:"):
        use_crs = st.checkbox("georeference the exports", help=H["georef"])
        if use_crs:
            kind = st.radio("transform", ["EPSG code (exact)", "origin lon/lat (approximate)"],
                            horizontal=True)
            if kind.startswith("EPSG"):
                epsg = st.number_input("EPSG", value=32614, step=1, help=H["epsg"])
                try:
                    crs = exporters.LocalCRS(epsg=int(epsg))
                except ImportError as exc:
                    st.error(str(exc))
            else:
                lon = st.number_input("origin longitude", value=-99.9, format="%.5f")
                lat = st.number_input("origin latitude", value=31.97, format="%.5f")
                crs = exporters.LocalCRS(origin_lon=lon, origin_lat=lat)
                st.caption(crs.describe()["note"])

    c1, c2, c3 = st.columns(3)
    with c1, st.container(border=True):
        st.markdown("##### 🗺️ Map files")
        st.download_button("AoR GeoJSON", json.dumps(exporters.to_geojson(res.aor, crs),
                                                     indent=2),
                           "aor.geojson", "application/geo+json", **_FULL_WIDTH)
        st.download_button("AoR KML (Google Earth)", exporters.to_kml(res.aor, crs),
                           "aor.kml", "application/vnd.google-earth.kml+xml", **_FULL_WIDTH)
        try:
            st.download_button(
                "AoR shapefile (.zip)",
                exporters.shapefile_bytes(res.aor, crs, {"project": project.name}),
                "aor_shapefile.zip", "application/zip", help=H["shapefile"], **_FULL_WIDTH)
        except ImportError:
            st.caption("Install pyshp for the ESRI shapefile export.")
    with c2, st.container(border=True):
        st.markdown("##### 📄 Report")
        st.download_button("Full HTML report", report.build_html(res),
                           "containment_report.html", "text/html", type="primary",
                           **_FULL_WIDTH)
        st.download_button("Result summary (JSON)",
                           json.dumps(report._clean(s), indent=2, default=str),
                           "summary.json", "application/json", **_FULL_WIDTH)
    with c3, st.container(border=True):
        st.markdown("##### 🧾 Inputs and fields")
        try:
            from containment.io import workbook as _workbook

            with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as fh:
                tmp_book = fh.name
            _workbook.to_excel(project, tmp_book,
                               penetrations_csv=project.penetrations_csv or None)
            with open(tmp_book, "rb") as fh:
                book = fh.read()
            os.unlink(tmp_book)
            st.download_button("All inputs (Excel workbook)", book,
                               "containment_project_inputs.xlsx", XLSX_MIME,
                               help=H["workbook"], **_FULL_WIDTH)
        except ImportError:
            st.caption("Install openpyxl for the Excel workbook export.")
        import yaml as _yaml

        st.download_button("Project file (YAML)",
                           _yaml.safe_dump(project.to_dict(), sort_keys=False),
                           "project.yaml", "text/yaml", **_FULL_WIDTH)
        buf = io.BytesIO()
        np.savez_compressed(buf, x=res.x, y=res.y, times=res.times,
                            dp=res.dp_fields, plume=res.plume_fields)
        st.download_button("Gridded fields (.npz)", buf.getvalue(),
                           "fields.npz", "application/octet-stream", **_FULL_WIDTH)


def page_help(project, res) -> None:
    theme.page_header("📘", "Help", "How to use Containment, what the words mean, and "
                      "where it should not be trusted.")
    if _has_documents():
        with st.container(border=True):
            st.markdown("##### Documentation")
            _documents("help")
    guide.render()


# ==========================================================================
# Frame: build the project, sidebar, run, page
PAGES = [  # id, label, icon, group, needs a result
    ("start", "Start", ":material/flag:", "Set up", False),
    ("site", "Site and zones", ":material/landscape:", "Set up", False),
    ("wells", "Wells", ":material/oil_barrel:", "Set up", False),
    ("model", "Model settings", ":material/tune:", "Set up", False),
    ("summary", "Summary", ":material/dashboard:", "Results", True),
    ("maps", "Maps", ":material/map:", "Results", True),
    ("corrective", "Corrective action", ":material/build:", "Results", True),
    ("threshold", "Threshold", ":material/speed:", "Results", True),
    ("pisc", "PISC", ":material/hourglass_bottom:", "Results", True),
    ("uncertainty", "Uncertainty", ":material/casino:", "Results", True),
    ("export", "Export", ":material/download:", "More", True),
    ("help", "Help", ":material/help:", "More", False),
]

proj_dict = _current_dict()
project, proj_err = None, None
sig = None
if proj_dict:
    sig = hashlib.sha1(json.dumps(proj_dict, sort_keys=True, default=str)
                       .encode("utf-8")).hexdigest()
    try:
        project = Project.from_dict(proj_dict)
    except Exception as exc:
        proj_err = str(exc)
    # A project file that turns uncertainty on (the Coastal Bend example does)
    # ticks the run option when it is loaded; the user can still untick it.
    if SS.get("source") != "Form" and project is not None:
        _unc_cfg = project.uncertainty or {}
        _unc_id = (SS.get("source"), SS.get("example_pick"), SS.get("_upload_id"))
        if SS.get("_unc_loaded") != _unc_id:
            SS["_unc_loaded"] = _unc_id
            SS["unc"] = bool(_unc_cfg.get("enabled"))
            if _unc_cfg.get("realisations"):
                SS["n_real"] = int(min(max(int(_unc_cfg["realisations"]), 40), 1000))
res = SS.get("result")

with st.sidebar:
    theme.brand()
    if project is not None:
        line = f"<b>{_html.escape(project.name)}</b>"
    elif proj_err:
        line = "<b>Project inputs</b>"
    else:
        line = "<b>No project yet</b>"
    if proj_err:
        theme.status(line, "warn", "Inputs cannot be read")
    elif res is not None and SS.get("_run_sig") == sig:
        theme.status(line, "ok", f"Results up to date: AoR {res.aor.area_sq_mi:,.1f} sq mi")
    elif res is not None:
        theme.status(line, "warn", "Inputs changed since the last run")
    elif project is not None:
        n = len(project.warnings)
        theme.status(line, "warn" if n else "none",
                     f"{n} input note(s) to check" if n else "Ready to run")
    else:
        theme.status(line, "none", "Choose a starting point")
    with st.container(key="runbox"):
        st.button("Run", type="primary", key="run", icon=":material/play_arrow:",
                  disabled=project is None, on_click=_request_run, **_FULL_WIDTH)
    group = None
    for pid, label, icon, grp, needs in PAGES:
        if grp != group:
            theme.navhead(grp)
            group = grp
        st.button(label, key=f"nav_{pid}", icon=icon, on_click=_go, args=(pid,),
                  type="primary" if SS["page"] == pid else "secondary",
                  disabled=needs and res is None, **_FULL_WIDTH)
    if _has_documents():
        theme.navhead("Documentation")
        _documents("side")

if SS.pop("_run_req", False) and project is not None:
    if SS.get("unc"):
        _unc_cfg = (proj_dict or {}).get("uncertainty") or {}
        project.uncertainty = {"enabled": True, "realisations": int(SS["n_real"]),
                               "spread": float(_unc_cfg.get("spread", 0.5)),
                               "seed": int(_unc_cfg.get("seed", 0))}
    with st.status("Running the model...", expanded=True) as box:
        def _step(m: str) -> None:
            box.update(label=m[0].upper() + m[1:] + "...")
            box.write(f"• {m}")
        try:
            out = workflow.run(project, run_uncertainty=bool(SS.get("unc")), progress=_step)
        except Exception as exc:
            box.update(label="The run failed", state="error")
            st.exception(exc)
            st.stop()
        box.update(label="Done", state="complete")
    SS["result"] = out
    SS["_run_sig"] = sig
    SS.pop("_fault_rerun", None)
    SS["page"] = "summary"
    SS["_ed_ver"] += 1
    st.rerun()

page = SS["page"]
if page in ("start", "site", "wells", "model"):
    {"start": page_start, "site": page_site, "wells": page_wells,
     "model": page_model}[page](project, proj_err, res)
elif page == "help":
    rp = getattr(res, "project", None) or project if res is not None else project
    page_help(rp, res)
elif res is None:
    st.info("Run a project first: set it up, then press Run in the sidebar.",
            icon=":material/play_arrow:")
else:
    # A result lives in session state, and a session outlives a deployment:
    # after an update the page can still be holding a result built by the
    # previous version of the code, without the attributes added since. The
    # pages read those through getattr so such a session keeps the pages it
    # can draw, until the next Run replaces the object.
    rp = getattr(res, "project", None) or project
    pens_plan, pens_error = _screen_upload(rp, res)
    if pens_plan is not None:
        res.corrective = pens_plan
    if page == "summary":
        page_summary(rp, res)
    elif page == "maps":
        page_maps(rp, res)
    elif page == "corrective":
        page_corrective(rp, res, pens_plan, pens_error)
    elif page == "threshold":
        page_threshold(rp, res)
    elif page == "pisc":
        page_pisc(rp, res)
    elif page == "uncertainty":
        page_uncertainty(rp, res)
    elif page == "export":
        page_export(rp, res)
