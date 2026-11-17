"""Input guide: every input explains itself, carries a sourced range, and the
templates that show it still load back unchanged."""

import os

import pytest
import yaml

from containment import inputs_guide as ig
from containment.config import Project
from containment.io import templates, workbook

EXAMPLES = os.path.join(os.path.dirname(os.path.dirname(__file__)), "examples")


def test_every_input_says_what_it_is_and_why():
    assert len(ig.INPUTS) >= 30
    for info in ig.INPUTS.values():
        assert info.what and info.why, info.key
        assert info.sources, f"{info.key} has no source"
        assert info.if_missing, f"{info.key} says nothing about a missing value"
        if info.typical:
            lo, hi = info.typical
            assert lo < hi
            if info.plausible:
                assert info.plausible[0] <= lo and hi <= info.plausible[1], info.key


def test_gradient_ranges_become_values_at_depth():
    assert ig.range_text("iz_p", 6000) == ("typical 2,598 to 2,820 psi at 6,000 ft "
                                           "(0.433 to 0.47 psi/ft)")
    assert "per 100 ft" in ig.range_text("iz_t")
    assert ig.range_text("iz_phi") == "typical 0.15 to 0.32"


def test_out_of_range_inputs_are_flagged_as_likely_unit_slips():
    d = yaml.safe_load(open(os.path.join(EXAMPLES, "gulf_coast_hub.yaml"), encoding="utf-8"))
    assert not [w for w in Project.from_dict(d).warnings if "plausible range" in w]
    d["formation"]["injection_zone"]["porosity"] = 24          # percent, not fraction
    w = [x for x in Project.from_dict(d).warnings if "plausible range" in x]
    assert any("Porosity" in x for x in w)


def test_workbook_carries_the_guide_and_still_reads_back(tmp_path):
    d = yaml.safe_load(open(os.path.join(EXAMPLES, "gulf_coast_hub.yaml"), encoding="utf-8"))
    path = tmp_path / "p.xlsx"
    path.write_bytes(templates.project_xlsx_template(d))
    import openpyxl
    wb = openpyxl.load_workbook(path)
    assert "Input guide" in wb.sheetnames
    assert wb["USDW"]["C1"].value == "your value"
    assert wb["USDW"]["D1"].value == "typical range"
    assert wb["Injection zones"]["D1"].comment is not None
    back = workbook.from_excel(str(path))
    assert back["formation"]["usdw"] == d["formation"]["usdw"]
    assert back["relative_permeability"]["sgr"] == pytest.approx(
        d["relative_permeability"]["sgr"])


def test_yaml_template_comments_do_not_change_the_values():
    d = yaml.safe_load(open(os.path.join(EXAMPLES, "gulf_coast_hub.yaml"), encoding="utf-8"))
    text = templates.project_yaml_template(d)
    assert "porosity: 0.24   # typical 0.15 to 0.32" in text
    back = yaml.safe_load(text)
    assert back["formation"] == d["formation"]
    assert back["wells"] == d["wells"]
