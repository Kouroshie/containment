"""Every upload in the app has a template, and every template loads back in.

A template that the reader then rejects is worse than none, so each one is
read back here through exactly the path the app uses for an upload.
"""

from __future__ import annotations

import os

import pytest
import yaml

from containment import corrective
from containment.config import Project
from containment.io import templates, workbook
from containment.io.exporters import LocalCRS

pytest.importorskip("openpyxl")

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXAMPLES = os.path.join(REPO, "examples")
CRS = LocalCRS(origin_lon=-99.9018, origin_lat=31.9686)   # the app's default site


def _gulf_coast() -> dict:
    with open(os.path.join(EXAMPLES, "gulf_coast_hub.yaml"), encoding="utf-8") as fh:
        d = yaml.safe_load(fh)
    d.setdefault("penetrations", {})["csv"] = os.path.join(EXAMPLES,
                                                           "gulf_coast_wells.csv")
    return d


# ------------------------------------------------------------ penetrations
def test_the_csv_template_loads_with_latitude_and_longitude(tmp_path):
    path = tmp_path / "pens.csv"
    path.write_text(templates.penetrations_csv_template(), encoding="utf-8")
    wells = corrective.load_wells_csv(str(path), unit="ft", crs=CRS)

    assert [w.name for w in wells] == ["EXAMPLE-01", "EXAMPLE-02", "EXAMPLE-03"]
    assert wells[0].plug_depths and len(wells[0].plug_depths) == 3
    assert wells[0].cased is True and wells[1].cased is False
    # placed near the origin, not at (0, 0)
    assert 0 < abs(wells[0].x) < 5000 and 0 < abs(wells[0].y) < 5000


def test_the_excel_template_loads_the_same_wells(tmp_path):
    book = tmp_path / "pens.xlsx"
    book.write_bytes(templates.penetrations_xlsx_template())
    out = templates.penetrations_xlsx_to_csv(str(book), str(tmp_path / "pens.csv"))
    from_xlsx = corrective.load_wells_csv(out, unit="ft", crs=CRS)

    csv_path = tmp_path / "direct.csv"
    csv_path.write_text(templates.penetrations_csv_template(), encoding="utf-8")
    from_csv = corrective.load_wells_csv(str(csv_path), unit="ft", crs=CRS)

    for a, b in zip(from_xlsx, from_csv, strict=True):
        assert (a.name, a.api, a.year_drilled, a.plug_depths, a.records_complete) == \
               (b.name, b.api, b.year_drilled, b.plug_depths, b.records_complete)
        assert a.x == pytest.approx(b.x) and a.y == pytest.approx(b.y)


def test_the_excel_template_explains_every_column():
    from io import BytesIO

    from openpyxl import load_workbook

    wb = load_workbook(BytesIO(templates.penetrations_xlsx_template()))
    assert wb.sheetnames == ["Penetrations", "Columns", "Instructions"]
    header = [c.value for c in wb["Penetrations"][1]]
    explained = [r[0] for r in wb["Columns"].iter_rows(min_row=2, values_only=True)
                 if r[0] and not str(r[0]).startswith("*")]
    assert header == explained


def test_a_title_line_above_the_header_is_tolerated(tmp_path):
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["Wells near the Example project, pulled 2026-10-08"])
    ws.append(["name", "x", "y", "total_depth"])
    ws.append(["W-1", 100, 200, 5000])
    ws.append([None, None, None, None])           # a stray blank row
    path = tmp_path / "titled.xlsx"
    wb.save(path)
    out = templates.penetrations_xlsx_to_csv(str(path), str(tmp_path / "o.csv"))
    wells = corrective.load_wells_csv(out, unit="ft")
    assert [w.name for w in wells] == ["W-1"]


# ----------------------------------------------------------------- project
def test_the_excel_project_template_loads_and_carries_the_penetrations(tmp_path):
    book = tmp_path / "project.xlsx"
    book.write_bytes(templates.project_xlsx_template(
        _gulf_coast(), penetrations_csv=_gulf_coast()["penetrations"]["csv"]))
    d = workbook.from_excel(str(book))
    project = Project.from_dict(d)

    assert len(project.wells) == len(Project.from_dict(_gulf_coast()).wells) == 5
    assert d["penetrations"]["coordinate_unit"] == "ft"
    with open(d["penetrations"]["csv"], encoding="utf-8") as fh:
        rows = fh.read().strip().splitlines()
    with open(_gulf_coast()["penetrations"]["csv"], encoding="utf-8") as fh:
        original = fh.read().strip().splitlines()
    assert len(rows) == len(original)


def test_the_yaml_project_template_loads():
    text = templates.project_yaml_template(_gulf_coast())
    assert text.startswith("# Containment project file: template.")
    project = Project.from_dict(yaml.safe_load(text))
    assert len(project.wells) == len(Project.from_dict(_gulf_coast()).wells) == 5
    assert not project.penetrations_csv     # carried by the Excel one only


def test_penetrations_typed_into_an_empty_sheet_are_read(tmp_path):
    """A project written without penetrations, then filled in by hand. The
    first typed row used to be swallowed as the header."""
    d = _gulf_coast()
    d.pop("penetrations")
    path = str(tmp_path / "p.xlsx")
    workbook.to_excel(d, path)

    from openpyxl import load_workbook

    wb = load_workbook(path)
    ws = wb["Penetrations"]
    assert "coordinate_unit: ft" in ws["A1"].value
    header = [c.value for c in ws[2]]
    for name in ("HAND-1", "HAND-2"):
        ws.append({header.index("name") + 1: name,
                   header.index("latitude") + 1: 28.80,
                   header.index("longitude") + 1: -95.75})
    wb.save(path)

    back = workbook.from_excel(path)
    with open(back["penetrations"]["csv"], encoding="utf-8") as fh:
        names = [line.split(",")[0] for line in fh.read().splitlines()[1:]]
    assert names == ["HAND-1", "HAND-2"]
    assert back["penetrations"]["coordinate_unit"] == "ft"
