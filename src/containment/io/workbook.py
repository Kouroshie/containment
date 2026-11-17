"""The whole project as one Excel workbook, and back again.

A YAML project file is the better record: it diffs, it reviews, and it goes in
version control. It is also the thing that stops a team adopting a tool,
because the people who hold the reservoir data work in spreadsheets.

This module writes every input a run needs into one workbook, one sheet per
part of the project, and reads that workbook back into the same dictionary
:class:`containment.config.Project` takes. Nothing is lost in the round trip,
so a team can hand the workbook around, fill it in, and run it without ever
opening a text editor.

Numbers stay in the units the project declares. They are never converted on
the way out or the way in, because a spreadsheet that silently changes units
is worse than no spreadsheet.
"""

from __future__ import annotations

import csv
import os
from typing import Any

# Sheets that hold a flat key/value list rather than a table.
_KV_SHEETS = {
    "Project": "project",
    "Units": "units",
    "USDW": ("formation", "usdw"),
    "Offshore": "offshore",
    "Relative permeability": "relative_permeability",
    "Threshold": "threshold",
    "Model": "model",
    "Plume": "plume",
    "Uncertainty": "uncertainty",
}

_ZONE_COLUMNS = ["name", "top_depth", "base_depth", "thickness", "porosity",
                 "permeability", "temperature", "salinity_ppm",
                 "initial_pressure", "rock_compressibility", "dip_degrees",
                 "dip_azimuth", "anisotropy_kv_kh",
                 "confining_top_depth", "confining_base_depth",
                 "threshold_override", "rp_swr", "rp_sgr", "rp_krw0", "rp_krg0",
                 "rp_m", "rp_n"]
# A zone's own relative permeability, as rp_<key> columns on its row.
_RP_KEYS = ("swr", "sgr", "krw0", "krg0", "m", "n")

_WELL_COLUMNS = ["name", "kind", "zone", "latitude", "longitude", "x", "y",
                 "rate", "rate_unit", "start_year", "stop_year",
                 "start_date", "stop_date", "max_bhp", "radius", "schedule",
                 "interval", "open_top_depth", "open_thickness"]

_HEADER_FILL = "DDE6F2"
_FILL_IN = "FFF2CC"                 # pale yellow: the cells the user fills in
YOUR_VALUE = "your value"
EXAMPLE_VALUE = "example value"
_ROWS_TO_FILL = 40                  # blank, shaded rows offered under each table

# The Offshore sheet lists its keys even when blank, so a user can find them.
# Listed on the Uncertainty sheet even when the project leaves it out, so a
# user can switch it on. Off by default: it runs the model many times.
UNCERTAINTY_DEFAULTS = {"enabled": False, "realisations": 120, "spread": 0.5,
                        "seed": 42}

OFFSHORE_KEYS = ["water_depth", "reference", "first_permeable_base",
                 "seafloor_temperature", "salinity_ppm"]
OFFSHORE_NOTE = ("Leave every value blank for an onshore project. Offshore (Texas "
                 "state waters, no USDW): water_depth is sea level to the mud line; "
                 "reference is mud_line (default) or first_permeable, which needs "
                 "first_permeable_base. Depths are from sea level. The USDW sheet is "
                 "then ignored [16 TAC 4.101, 5.206(b)(2)].")


def _require_openpyxl():
    try:
        import openpyxl  # noqa: F401
    except ImportError as exc:      # pragma: no cover - environment dependent
        raise ImportError(
            "reading and writing project workbooks needs openpyxl: "
            "pip install openpyxl, or install containment[full]") from exc


def _flatten(d: dict, prefix: str = "") -> list[tuple[str, Any]]:
    """A nested dict as dotted key/value rows, so one sheet can hold it."""
    rows: list[tuple[str, Any]] = []
    for k, v in (d or {}).items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            rows.extend(_flatten(v, f"{key}."))
        elif isinstance(v, (list, tuple)):
            rows.append((key, ", ".join(str(x) for x in v)))
        else:
            rows.append((key, v))
    return rows


def _unflatten(rows) -> dict:
    """The inverse of :func:`_flatten`."""
    out: dict = {}
    for key, value in rows:
        if key is None or str(key).strip() == "":
            continue
        cur = out
        parts = str(key).split(".")
        for part in parts[:-1]:
            cur = cur.setdefault(part, {})
        cur[parts[-1]] = value
    return out


def _style_header(ws, ncols: int) -> None:
    from openpyxl.styles import Alignment, Font, PatternFill

    fill = PatternFill("solid", fgColor=_HEADER_FILL)
    for col in range(1, ncols + 1):
        cell = ws.cell(row=1, column=col)
        cell.font = Font(bold=True)
        cell.fill = fill
        cell.alignment = Alignment(vertical="center", wrap_text=True)
    ws.freeze_panes = "A2"


def _autosize(ws, limit: int = 46) -> None:
    for col in ws.columns:
        width = max((len(str(c.value)) for c in col if c.value is not None),
                    default=8)
        ws.column_dimensions[col[0].column_letter].width = min(width + 2, limit)


# key on a key/value sheet -> entry in containment.inputs_guide
_GUIDE_KEYS = {
    "USDW": {"base_depth": "usdw_base", "initial_pressure": "usdw_p",
             "temperature": "usdw_t", "salinity_ppm": "usdw_s"},
    "Offshore": {"water_depth": "water_depth", "seafloor_temperature": "off_t"},
    "Relative permeability": {"swr": "swr", "sgr": "sgr", "krg0": "krg0", "krw0": "krw0",
                              "m": "corey_w", "n": "corey_g"},
    "Threshold": {"method": "method", "override": "threshold", "mud_weight_ppg": "ppg",
                  "gel_strength": "gel"},
    "Model": {"engine": "engine", "end_year": "end_year", "grid.cell_size": "cell"},
    "Plume": {"cutoff": "cutoff"},
}
# column on a table sheet -> entry in containment.inputs_guide
_COLUMN_GUIDE = {
    "Injection zones": {"top_depth": "iz_top", "thickness": "iz_h", "porosity": "iz_phi",
                        "permeability": "iz_k", "temperature": "iz_t",
                        "salinity_ppm": "iz_s", "initial_pressure": "iz_p",
                        "rock_compressibility": "iz_cr", "dip_degrees": "iz_dip",
                        "dip_azimuth": "iz_az", "anisotropy_kv_kh": "iz_kvkh",
                        "confining_top_depth": "cz", "confining_base_depth": "cz",
                        "threshold_override": "threshold", "rp_swr": "swr",
                        "rp_sgr": "sgr", "rp_krw0": "krw0", "rp_krg0": "krg0",
                        "rp_m": "corey_w", "rp_n": "corey_g"},
    "Wells": {"rate": "rate", "max_bhp": "max_bhp", "radius": "radius",
              "open_thickness": "open_h"},
}


def _guide_cells(gkey: str | None, depth_ft: float | None = None) -> list[str]:
    from .. import inputs_guide as ig

    info = ig.INPUTS.get(gkey or "")
    if not info:
        return []
    rng = ig.range_text(gkey, depth_ft)
    if gkey in ig.OPTIONS:          # a choice: list every option and what it does
        return ["options: " + ", ".join(ig.OPTIONS[gkey]),
                info.why + "\n\n" + ig.options_text(gkey)]
    return [rng.replace("typical ", "") + (" (field units)" if rng else ""), info.why]


def _kv_sheet(wb, title: str, data: dict, note: str = "",
              depths: dict | None = None, value_label: str = EXAMPLE_VALUE) -> None:
    """Key, the shipped value, an empty yellow 'your value' column, then help.

    The reader takes 'your value' where it is filled and the value beside it
    where it is blank, so a user fills in only what their project changes.
    """
    from openpyxl.styles import Alignment, PatternFill

    from .. import inputs_guide as ig

    ws = wb.create_sheet(title)
    guide = _GUIDE_KEYS.get(title, {})
    ws.append(["key", value_label, YOUR_VALUE, "typical range", "why Containment uses it"]
              if guide else ["key", value_label, YOUR_VALUE])
    fill = PatternFill("solid", fgColor=_FILL_IN)
    for key, value in _flatten(data):
        ws.append([key, value, None,
                   *_guide_cells(guide.get(key), (depths or {}).get(key))])
        ws.cell(ws.max_row, 3).fill = fill
        if guide.get(key) in ig.OPTIONS:
            ws.cell(ws.max_row, 5).alignment = Alignment(wrap_text=True, vertical="top")
    if note:
        ws.append([])
        ws.append(["note", note])
    _style_header(ws, 5 if guide else 3)
    ws.cell(1, 3).fill = fill
    _autosize(ws)
    ws.column_dimensions["C"].width = 16
    if guide:
        ws.column_dimensions["E"].width = 90


def _table_sheet(wb, title: str, rows: list[dict], columns: list[str]) -> None:
    from openpyxl.comments import Comment
    from openpyxl.styles import PatternFill

    from .. import inputs_guide as ig

    ws = wb.create_sheet(title)
    ws.append(columns)
    for row in rows:
        ws.append([row.get(c) for c in columns])
    _style_header(ws, len(columns))
    _autosize(ws)
    # A table is filled in place, one row per item: shade every cell a user
    # may edit, plus blank rows below for the rows they add.
    fill = PatternFill("solid", fgColor=_FILL_IN)
    for r in range(2, len(rows) + 2 + _ROWS_TO_FILL):
        for c in range(1, len(columns) + 1):
            ws.cell(r, c).fill = fill
    # hover notes on the headers: range and reason, as in the browser form
    for i, col in enumerate(columns, start=1):
        gkey = _COLUMN_GUIDE.get(title, {}).get(col)
        info = ig.INPUTS.get(gkey or "")
        if info:
            rng = ig.range_text(gkey)
            text = ((rng[0].upper() + rng[1:] + ".\n") if rng else "") + "Why: " + info.why
            c = Comment(text, "Containment")
            c.width, c.height = 320, 160
            ws.cell(row=1, column=i).comment = c


def _input_guide_sheet(wb) -> None:
    """Every input with what it is, why it is used, its range and sources."""
    from openpyxl.styles import Alignment

    from .. import inputs_guide as ig

    ws = wb.create_sheet("Input guide")
    cols = ["input", "where in this workbook / project file", "unit", "what it is",
            "why Containment uses it", "typical range", "plausible range",
            "15 Texas Class VI applications", "if the application does not give it",
            "Containment's value if left blank", "sources"]
    ws.append(cols)
    for info in ig.INPUTS.values():
        pl = (f"{ig._fmt(info.plausible[0])} to {ig._fmt(info.plausible[1])}"
              if info.plausible else "")
        why = info.why + ("\n\nOptions:\n" + ig.options_text(info.key)
                          if info.key in ig.OPTIONS else "")
        ws.append([info.label, info.path, info.unit, info.what, why,
                   ig.range_text(info.key).replace("typical ", ""), pl, info.seen,
                   info.if_missing, ig.BLANK.get(info.key, "required"),
                   "\n".join(info.sources)])
    _style_header(ws, len(cols))
    for letter, width in zip("ABCDEFGHIJK", (28, 34, 9, 40, 60, 30, 18, 30, 60, 40, 90),
                             strict=True):
        ws.column_dimensions[letter].width = width
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")


# ==========================================================================
def to_excel(project, path: str, *, penetrations_csv: str | None = None,
             template: bool = False) -> str:
    """Write every input of a project into one workbook.

    ``project`` is a :class:`~containment.config.Project` or the dictionary one
    was built from. Values keep the units the project declared. ``template``
    labels the shipped values 'example value' (a download to fill in) rather
    than 'value in this project' (an export of the user's own run).
    """
    _require_openpyxl()
    from openpyxl import Workbook

    d = project.to_dict() if hasattr(project, "to_dict") else dict(project)
    wb = Workbook()
    wb.remove(wb.active)

    # ---- read me
    ws = wb.create_sheet("Read me")
    for line in [
        ["Containment project workbook"],
        [],
        ["This workbook holds every input one run needs. Fill it in, save it,"],
        ["and load it with:"],
        [],
        ["    containment run project.xlsx"],
        [],
        ["or in the browser app, choose 'Open a project file' on the Start page"],
        ["and pick this file."],
        [],
        ["Fill in the yellow cells. On the key/value sheets (Project, Units,"],
        ["USDW, Threshold, Model, Uncertainty and so on) type your number in the"],
        ["'your value' column: Containment uses it where it is filled and the"],
        ["value beside it where it is blank. When the value beside it is an"],
        ["example value, the run lists the sheets where examples were used."],
        ["On the table sheets (Injection zones, Wells, Faults, Penetrations)"],
        ["edit or replace the rows in place; the yellow rows below them are"],
        ["for the wells or zones you add."],
        [],
        ["Numbers are in the units declared on the Units sheet. Nothing is"],
        ["converted when this file is written or read, so changing a unit on"],
        ["that sheet changes how every number on the others is interpreted."],
        [],
        ["Sheets:"],
        ["  Project               name, operator, permit, start date, CRS"],
        ["  Units                 the units every other sheet is written in"],
        ["  Injection zones       one row per zone; several rows is a stacked"],
        ["                        completion, each with its own confining zone"],
        ["  USDW                  the interval being protected"],
        ["  Offshore              leave blank onshore; offshore (no USDW), give"],
        ["                        water_depth and the USDW sheet is ignored"],
        ["  Relative permeability the two-phase flow functions"],
        ["  Threshold             how the critical pressure is computed"],
        ["  Model                 engine, boundary, grid, horizon"],
        ["  Plume                 the saturation cutoff that counts as plume"],
        ["  Wells                 injectors, extractors and their schedules;"],
        ["                        open_thickness (and open_top_depth or an interval"],
        ["                        name) marks a staged completion into a thin interval"],
        ["  Faults                sealing or partly sealing traces"],
        ["  Penetrations          the artificial penetrations to screen"],
        ["  Uncertainty           tornado and Monte Carlo settings"],
        ["  Input guide           why each input is needed, the range to expect,"],
        ["                        what to use when the application does not say,"],
        ["                        and the sources (ranges are in field units)"],
    ]:
        ws.append(line)
    ws["A1"].font = __import__("openpyxl").styles.Font(bold=True, size=14)
    ws.column_dimensions["A"].width = 74

    # ---- key/value sheets
    label = EXAMPLE_VALUE if template else "value in this project"
    usdw_base = ((d.get("formation") or {}).get("usdw") or {}).get("base_depth")
    feet = str((d.get("units") or {}).get("depth", "ft")).lower() in ("ft", "feet")
    for title, key in _KV_SHEETS.items():
        if isinstance(key, tuple):
            data = d.get(key[0], {}).get(key[1], {})
        else:
            data = d.get(key, {})
        if title == "Offshore":
            _kv_sheet(wb, title, data or {k: None for k in OFFSHORE_KEYS},
                      note=OFFSHORE_NOTE, value_label=label)
            continue
        if title == "Uncertainty" and not data:
            data = dict(UNCERTAINTY_DEFAULTS)
        depths = ({"initial_pressure": float(usdw_base)}
                  if title == "USDW" and usdw_base is not None and feet else None)
        _kv_sheet(wb, title, data or {}, depths=depths, value_label=label)

    # ---- injection zones, one row each
    formation = d.get("formation", {}) or {}
    zones = list(formation.get("injection_zones") or [])
    if not zones and formation.get("injection_zone"):
        z = dict(formation["injection_zone"])
        z.setdefault("name", "injection zone")
        cz = formation.get("confining_zone") or {}
        z["confining_top_depth"] = cz.get("top_depth")
        z["confining_base_depth"] = cz.get("base_depth")
        zones = [z]
    else:
        flat = []
        for z in zones:
            z = dict(z)
            cz = z.pop("confining_zone", None) or formation.get("confining_zone") or {}
            z["confining_top_depth"] = cz.get("top_depth")
            z["confining_base_depth"] = cz.get("base_depth")
            for k, v in (z.pop("relative_permeability", None) or {}).items():
                if k in _RP_KEYS:
                    z[f"rp_{k}"] = v
            flat.append(z)
        zones = flat
    _table_sheet(wb, "Injection zones", zones, _ZONE_COLUMNS)

    # ---- wells
    wells = []
    for w in d.get("wells", []) or []:
        row = dict(w)
        if isinstance(row.get("schedule"), list):
            row["schedule"] = "; ".join(
                f"{s.get('year', s.get('date', ''))}:{s.get('rate', '')}"
                for s in row["schedule"])
        wells.append(row)
    _table_sheet(wb, "Wells", wells, _WELL_COLUMNS)

    # ---- faults
    faults = []
    for f in d.get("faults", []) or []:
        row = {"name": f.get("name"), "multiplier": f.get("multiplier")}
        pts = f.get("latlon") or f.get("points") or []
        row["points"] = "; ".join(f"{a}, {b}" for a, b in pts)
        row["coordinates"] = "latlon" if f.get("latlon") else "xy"
        faults.append(row)
    _table_sheet(wb, "Faults", faults, ["name", "multiplier", "coordinates",
                                        "points"])

    # ---- penetrations, read out of the CSV the project points at
    pen_cfg = d.get("penetrations", {}) or {}
    csv_path = penetrations_csv or pen_cfg.get("csv")
    pen_rows, pen_cols = [], []
    if csv_path and os.path.exists(csv_path):
        with open(csv_path, newline="", encoding="utf-8-sig") as fh:
            rdr = csv.DictReader(fh)
            pen_cols = list(rdr.fieldnames or [])
            pen_rows = [dict(r) for r in rdr]
    if pen_rows:
        _table_sheet(wb, "Penetrations", pen_rows, pen_cols)
        ws = wb["Penetrations"]
        ws.insert_rows(1)
        ws["A1"] = (f"coordinate_unit: {pen_cfg.get('coordinate_unit', 'm')} "
                    f"(source: {csv_path})")
        ws["A1"].font = __import__("openpyxl").styles.Font(italic=True)
    else:
        _table_sheet(wb, "Penetrations", [], ["name", "api", "type", "status",
                                              "latitude", "longitude",
                                              "total_depth", "year_drilled",
                                              "year_abandoned", "plug_depths",
                                              "plug_material", "cased",
                                              "records_complete", "mit_passed",
                                              "notes"])
        ws = wb["Penetrations"]
        ws.insert_rows(1)
        unit = (pen_cfg.get("coordinate_unit")
                or (d.get("units") or {}).get("length") or "m")
        ws["A1"] = (f"coordinate_unit: {unit} (x, y, total_depth and "
                    f"plug_depths; give latitude/longitude or x/y)")
        ws["A1"].font = __import__("openpyxl").styles.Font(italic=True)

    _input_guide_sheet(wb)
    wb.save(path)
    return path


# ==========================================================================
def from_excel(path: str) -> dict:
    """Read a workbook written by :func:`to_excel` back into a project dict."""
    _require_openpyxl()
    from openpyxl import load_workbook

    wb = load_workbook(path, data_only=True)
    d: dict = {}
    notes: list[str] = []

    def blank(v) -> bool:
        return v is None or str(v).strip() == ""

    def kv(title: str) -> dict:
        if title not in wb.sheetnames:
            return {}
        ws = wb[title]
        header = [str(c).strip().lower() if c is not None else ""
                  for c in next(ws.iter_rows(min_row=1, max_row=1, values_only=True), ())]
        # an older workbook has no 'your value' column: key, value, ...
        yours = header.index(YOUR_VALUE) if YOUR_VALUE in header else None
        examples = len(header) > 1 and header[1] == EXAMPLE_VALUE
        rows, shipped = [], 0
        for raw in ws.iter_rows(min_row=2, values_only=True):
            raw = list(raw) + [None] * 3
            key, value = raw[0], raw[1]
            if key is None or str(key).strip().lower() == "note":
                continue
            if yours is not None and not blank(raw[yours]):
                value = raw[yours]
            elif not blank(value):
                shipped += 1
            rows.append((key, value))
        if examples and shipped:
            notes.append(f"workbook sheet '{title}': {shipped} blank 'your value' "
                         f"cell(s) used the example value beside them")
        return _unflatten(rows)

    def rows_of(title: str, header_row: int = 1) -> list[dict]:
        if title not in wb.sheetnames:
            return []
        ws = wb[title]
        data = list(ws.iter_rows(min_row=header_row, values_only=True))
        if not data:
            return []
        header = [str(c) if c is not None else "" for c in data[0]]
        out = []
        for raw in data[1:]:
            row = {h: v for h, v in zip(header, raw, strict=False)
                   if h and v is not None and str(v).strip() != ""}
            if row:
                out.append(row)
        return out

    for title, key in _KV_SHEETS.items():
        data = kv(title)
        if not data:
            continue
        if isinstance(key, tuple):
            d.setdefault(key[0], {})[key[1]] = data
        else:
            d[key] = data

    # ---- injection zones
    zones = []
    for z in rows_of("Injection zones"):
        z = dict(z)
        top = z.pop("confining_top_depth", None)
        base = z.pop("confining_base_depth", None)
        if top is not None or base is not None:
            z["confining_zone"] = {k: v for k, v in
                                   (("top_depth", top), ("base_depth", base))
                                   if v is not None}
        rp = {k: z.pop(f"rp_{k}") for k in _RP_KEYS if f"rp_{k}" in z}
        if rp:
            z["relative_permeability"] = rp
        zones.append(z)
    if zones:
        d.setdefault("formation", {})
        if len(zones) == 1:
            one = dict(zones[0])
            cz = one.pop("confining_zone", None)
            one.pop("name", None)
            d["formation"]["injection_zone"] = one
            if cz:
                d["formation"]["confining_zone"] = cz
        else:
            d["formation"]["injection_zones"] = zones

    # ---- wells
    wells = []
    for w in rows_of("Wells"):
        w = dict(w)
        sched = w.pop("schedule", None)
        if sched:
            steps = []
            for part in str(sched).split(";"):
                if ":" not in part:
                    continue
                when, rate = part.split(":", 1)
                when, rate = when.strip(), rate.strip()
                key = "date" if "-" in when else "year"
                steps.append({key: (when if key == "date" else float(when)),
                              "rate": float(rate)})
            if steps:
                w["schedule"] = steps
        for date_key in ("start_date", "stop_date"):
            if w.get(date_key) is not None:
                w[date_key] = str(w[date_key])[:10]
        wells.append(w)
    if wells:
        d["wells"] = wells

    # ---- faults
    faults = []
    for f in rows_of("Faults"):
        pts = []
        for pair in str(f.get("points", "")).split(";"):
            bits = [b.strip() for b in pair.split(",") if b.strip()]
            if len(bits) == 2:
                pts.append([float(bits[0]), float(bits[1])])
        if not pts:
            continue
        entry = {"name": f.get("name"), "multiplier": f.get("multiplier", 0.0)}
        entry["latlon" if f.get("coordinates", "latlon") == "latlon"
              else "points"] = pts
        faults.append(entry)
    if faults:
        d["faults"] = faults

    # ---- penetrations: written back out as a CSV beside the workbook
    # A sheet written from a CSV carries a "coordinate_unit: ..." line above
    # its header; an empty one, filled in by hand, starts with the header.
    pen_title = (str(wb["Penetrations"]["A1"].value or "")
                 if "Penetrations" in wb.sheetnames else "")
    pens = rows_of("Penetrations",
                   header_row=2 if "coordinate_unit:" in pen_title else 1)
    if pens:
        out_csv = os.path.splitext(path)[0] + "_penetrations.csv"
        cols: list[str] = []
        for row in pens:
            for k in row:
                if k not in cols:
                    cols.append(k)
        with open(out_csv, "w", newline="", encoding="utf-8") as fh:
            wr = csv.DictWriter(fh, fieldnames=cols)
            wr.writeheader()
            for row in pens:
                wr.writerow(row)
        unit = "m"
        header = wb["Penetrations"]["A1"].value or ""
        if "coordinate_unit:" in str(header):
            unit = str(header).split("coordinate_unit:")[1].split("(")[0].strip()
        d["penetrations"] = {"csv": out_csv, "coordinate_unit": unit}

    if notes:
        d["workbook_notes"] = notes
    return d


__all__ = ["to_excel", "from_excel"]
