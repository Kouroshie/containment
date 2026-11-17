"""Blank-but-worked templates for everything the browser app accepts as an upload.

Each template is built from the same column lists the readers use, so a
template downloaded from the app always loads back into it. The example rows
are synthetic: placeholder coordinates near the centre of Texas and API
numbers in the unused ``42-000`` block.
"""

from __future__ import annotations

import csv
import io
import os
import tempfile

# (column, required, what goes in it). The order is the order on the sheet.
PENETRATION_COLUMNS: list[tuple[str, str, str]] = [
    ("name", "yes", "Well name or lease and well number."),
    ("api", "no", "API number, e.g. 42-000-00001."),
    ("type", "no", "oil, gas, injection, water, dry hole, mine, ..."),
    ("status", "no", "active, shut-in, plugged, abandoned or unknown."),
    ("latitude", "yes*", "Decimal degrees (NAD83/WGS84), e.g. 31.9712."),
    ("longitude", "yes*", "Decimal degrees, negative in Texas, e.g. -99.8954."),
    ("x", "yes*", "Easting in the model frame, in the coordinate unit."),
    ("y", "yes*", "Northing in the model frame, in the coordinate unit."),
    ("total_depth", "no", "Total depth, in the coordinate unit."),
    ("year_drilled", "no", "Four-digit year, e.g. 1953."),
    ("year_abandoned", "no", "Four-digit year; blank if not abandoned. "
                           "Also sets the Texas history note (1967 RRC Rule 14, 1919)."),
    ("plug_depths", "no", "Cement plug tops, separated by semicolons, "
                          "e.g. 420;5750;6300."),
    ("plug_material", "no", "cement, mud, unknown, ..."),
    ("cased", "no", "yes or no. An uncased hole gets a closure note "
                  "(Gulf Coast closes, hard West Texas rock stays open)."),
    ("records_complete", "no", "yes or no: are the completion and plugging "
                               "records on file?"),
    ("mit_passed", "no", "yes or no: most recent mechanical integrity test."),
    ("notes", "no", "Anything a reviewer should know."),
]

PENETRATION_EXAMPLES: list[dict] = [
    {"name": "EXAMPLE-01", "api": "42-000-00001", "type": "oil",
     "status": "plugged", "latitude": 31.9712, "longitude": -99.8954,
     "total_depth": 6420, "year_drilled": 1953, "year_abandoned": 1981,
     "plug_depths": "420;5750;6300", "plug_material": "cement",
     "cased": "yes", "records_complete": "yes",
     "notes": "example row: replace or delete"},
    {"name": "EXAMPLE-02", "api": "42-000-00002", "type": "dry hole",
     "status": "abandoned", "latitude": 31.9651, "longitude": -99.9102,
     "total_depth": 6100, "year_drilled": 1938,
     "plug_material": "unknown", "cased": "no", "records_complete": "no",
     "notes": "example row: records lost, open hole"},
    {"name": "EXAMPLE-03", "api": "42-000-00003", "type": "water",
     "status": "active", "latitude": 31.9733, "longitude": -99.9061,
     "total_depth": 850, "year_drilled": 1996, "cased": "yes",
     "records_complete": "yes", "notes": "example row: shallow water well"},
]

_PEN_INSTRUCTIONS = [
    "Artificial penetrations: template",
    "",
    "One row per well, mine or other man-made penetration near the project.",
    "Fill in the yellow cells of the Penetrations sheet, save, and upload this",
    "file on the 'Corrective action' page of the app. The three EXAMPLE rows are",
    "there to show the format: replace or delete them.",
    "",
    "Location: give latitude and longitude, OR x and y, for every row.",
    "  * latitude/longitude works when the project is georeferenced (its",
    "    injection wells are given in latitude/longitude, or it sets a CRS).",
    "  * x/y are distances from the project origin in the model frame.",
    "",
    "Units: depths, plug depths and x/y are in the 'coordinate and depth unit'",
    "you pick next to the upload box (ft or m).",
    "",
    "Only name and a location are required. Everything else sharpens the",
    "screen; a blank is treated as unknown, which pushes a well toward field",
    "testing rather than toward 'no action'.",
    "",
    "Do not rename the column headers. Extra columns are ignored.",
    "A CSV with the same headers is accepted too.",
]


def _require_openpyxl():
    try:
        import openpyxl  # noqa: F401
    except ImportError as exc:      # pragma: no cover - environment dependent
        raise ImportError("the Excel templates need openpyxl: "
                          "pip install openpyxl") from exc


def _style(ws, ncols: int) -> None:
    from openpyxl.styles import Font, PatternFill

    for c in ws[1][:ncols]:
        c.font = Font(bold=True)
        c.fill = PatternFill("solid", fgColor="DDE6F2")
    ws.freeze_panes = "A2"


def penetrations_csv_template() -> str:
    """The penetration template as CSV text, header plus example rows."""
    buf = io.StringIO()
    wr = csv.DictWriter(buf, fieldnames=[c for c, _, _ in PENETRATION_COLUMNS],
                        lineterminator="\n")
    wr.writeheader()
    for row in PENETRATION_EXAMPLES:
        wr.writerow(row)
    return buf.getvalue()


def penetrations_xlsx_template() -> bytes:
    """The penetration template as an Excel workbook.

    Sheets: Penetrations (header and example rows), Columns (what each column
    takes) and Instructions.
    """
    _require_openpyxl()
    from openpyxl import Workbook
    from openpyxl.styles import Font

    wb = Workbook()
    ws = wb.active
    ws.title = "Penetrations"
    cols = [c for c, _, _ in PENETRATION_COLUMNS]
    ws.append(cols)
    for row in PENETRATION_EXAMPLES:
        ws.append([row.get(c) for c in cols])
    _style(ws, len(cols))
    for i, c in enumerate(cols, start=1):
        ws.column_dimensions[ws.cell(1, i).column_letter].width = max(
            12, len(c) + 2)
    # the cells to fill in: the example rows to overwrite and blank rows below
    from openpyxl.styles import PatternFill

    fill = PatternFill("solid", fgColor="FFF2CC")
    for r in range(2, len(PENETRATION_EXAMPLES) + 2 + 200):
        for i in range(1, len(cols) + 1):
            ws.cell(r, i).fill = fill

    guide = wb.create_sheet("Columns")
    guide.append(["column", "required", "what goes in it"])
    for row in PENETRATION_COLUMNS:
        guide.append(list(row))
    guide.append([])
    guide.append(["* give latitude and longitude, or x and y"])
    _style(guide, 3)
    guide.column_dimensions["A"].width = 18
    guide.column_dimensions["B"].width = 10
    guide.column_dimensions["C"].width = 70

    info = wb.create_sheet("Instructions")
    for line in _PEN_INSTRUCTIONS:
        info.append([line])
    info["A1"].font = Font(bold=True, size=14)
    info.column_dimensions["A"].width = 80

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def penetrations_xlsx_to_csv(xlsx_path: str, csv_path: str) -> str:
    """Write the penetration rows of an uploaded workbook out as CSV.

    Reads the sheet named Penetrations (else the first sheet). The header row
    is the first row whose cells include ``name``, ``api``, ``x`` or
    ``latitude``, so a title line above the header is tolerated. Empty rows
    are skipped.
    """
    _require_openpyxl()
    from openpyxl import load_workbook

    wb = load_workbook(xlsx_path, data_only=True, read_only=True)
    ws = wb["Penetrations"] if "Penetrations" in wb.sheetnames else wb.worksheets[0]
    rows = [list(r) for r in ws.iter_rows(values_only=True)]
    wb.close()
    keys = {"name", "api", "x", "latitude", "lat"}
    start = next((i for i, r in enumerate(rows)
                  if keys & {str(c).strip().lower() for c in r if c is not None}),
                 None)
    if start is None:
        raise ValueError("no header row found: the sheet needs a 'name' column "
                         "and either latitude/longitude or x/y columns")
    header = [str(c).strip() if c is not None else "" for c in rows[start]]
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        wr = csv.writer(fh)
        wr.writerow(header)
        for r in rows[start + 1:]:
            vals = ["" if c is None else
                    (str(int(c)) if isinstance(c, float) and c.is_integer()
                     and h in ("year_drilled", "year_abandoned") else str(c))
                    for h, c in zip(header, r, strict=False)]
            if any(v.strip() for v in vals):
                wr.writerow(vals)
    return csv_path


# --------------------------------------------------------------- project
def project_xlsx_template(project, penetrations_csv: str | None = None) -> bytes:
    """A filled-in project workbook to edit and upload, built from ``project``.

    The Read me sheet explains every sheet; values keep the project's units.
    """
    from . import workbook

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as fh:
        path = fh.name
    try:
        workbook.to_excel(project, path, penetrations_csv=penetrations_csv,
                          template=True)
        with open(path, "rb") as fh:
            return fh.read()
    finally:
        os.unlink(path)


def project_yaml_template(project) -> str:
    """The same project as a YAML file, with a short header on how to use it."""
    import yaml

    d = project.to_dict() if hasattr(project, "to_dict") else dict(project)
    d.pop("penetrations", None)   # a YAML upload cannot carry the CSV with it
    head = ("# Containment project file: template.\n"
            "# Edit the values, keep the keys, then upload it in the app\n"
            "# (Start page, 'Open a project file'). Numbers are in the units\n"
            "# under `units:`. Artificial penetrations are uploaded separately,\n"
            "# on the 'Corrective action' page. The Excel template carries them in\n"
            "# the same file instead.\n"
            "# Each input line ends with its typical range (field units) and why\n"
            "# Containment needs it; sources are on the workbook's Input guide sheet.\n\n")
    return head + annotate_yaml(yaml.safe_dump(d, sort_keys=False))


# dotted path in a project file (list positions dropped) -> inputs_guide key
_YAML_GUIDE = {
    "formation.injection_zone.top_depth": "iz_top",
    "formation.injection_zone.thickness": "iz_h",
    "formation.injection_zone.porosity": "iz_phi",
    "formation.injection_zone.permeability": "iz_k",
    "formation.injection_zone.temperature": "iz_t",
    "formation.injection_zone.salinity_ppm": "iz_s",
    "formation.injection_zone.initial_pressure": "iz_p",
    "formation.injection_zone.rock_compressibility": "iz_cr",
    "formation.injection_zone.dip_degrees": "iz_dip",
    "formation.injection_zone.dip_azimuth": "iz_az",
    "formation.injection_zone.anisotropy_kv_kh": "iz_kvkh",
    "formation.confining_zone.base_depth": "cz",
    "formation.usdw.base_depth": "usdw_base",
    "formation.usdw.initial_pressure": "usdw_p",
    "formation.usdw.temperature": "usdw_t",
    "formation.usdw.salinity_ppm": "usdw_s",
    "offshore.water_depth": "water_depth",
    "offshore.seafloor_temperature": "off_t",
    "relative_permeability.swr": "swr",
    "relative_permeability.sgr": "sgr",
    "relative_permeability.krg0": "krg0",
    "relative_permeability.krw0": "krw0",
    "relative_permeability.m": "corey_w",
    "relative_permeability.n": "corey_g",
    "threshold.override": "threshold",
    "threshold.mud_weight_ppg": "ppg",
    "threshold.gel_strength": "gel",
    "wells.rate": "rate",
    "wells.max_bhp": "max_bhp",
    "wells.radius": "radius",
    "wells.open_thickness": "open_h",
    "model.end_year": "end_year",
    "model.engine": "engine",
    "threshold.method": "method",
    "model.grid.cell_size": "cell",
    "plume.cutoff": "cutoff",
}
for _k in ("top_depth", "thickness", "porosity", "permeability", "temperature",
           "salinity_ppm", "initial_pressure", "rock_compressibility", "dip_degrees",
           "dip_azimuth", "anisotropy_kv_kh"):
    _YAML_GUIDE[f"formation.injection_zones.{_k}"] = \
        _YAML_GUIDE[f"formation.injection_zone.{_k}"]


def annotate_yaml(text: str) -> str:
    """Add the typical range and the reason to each input line of a project YAML.

    The comment is what a reviewer needs when the application is silent: the
    range to expect (field units) and what the number changes. The full
    sources are on the workbook's Input guide sheet and in the app.
    """
    import re

    from .. import inputs_guide as ig

    stack: list[tuple[int, str]] = []
    out = []
    for line in text.splitlines():
        m = re.match(r"^(\s*)(- )?([A-Za-z_][\w]*):(.*)$", line)
        if not m:
            out.append(line)
            continue
        indent = len(m.group(1)) + (2 if m.group(2) else 0)
        while stack and stack[-1][0] >= indent:
            stack.pop()
        stack.append((indent, m.group(3)))
        path = ".".join(k for _, k in stack)
        gkey = _YAML_GUIDE.get(path)
        value = m.group(4).strip()
        if gkey in ig.OPTIONS_SHORT and value and "#" not in value:
            out.append(f"{line}   # options: {ig.OPTIONS_SHORT[gkey]}")
            continue
        if gkey and value and "#" not in value:
            info = ig.INPUTS.get(gkey)
            rng = ig.range_text(gkey)
            why = info.why.split(". ")[0].rstrip(".") if info else ""
            note = "; ".join(x for x in (rng, why) if x)
            if note:
                line = f"{line}   # {note}"
        out.append(line)
    return "\n".join(out) + "\n"


__all__ = ["PENETRATION_COLUMNS", "penetrations_csv_template",
           "penetrations_xlsx_template", "penetrations_xlsx_to_csv",
           "project_xlsx_template", "project_yaml_template", "annotate_yaml"]
