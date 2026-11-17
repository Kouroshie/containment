"""Offshore mode: the critical pressure measured against the mud line.

In the Texas Offshore a USDW may not be present, so the tool bases
the critical pressure on the deepest depth needed to prevent any discharge to
the seafloor: the mud line, or the base of the first permeable stratum below
it [16 TAC 4.101; 16 TAC 5.206(b)(2)].
"""

from __future__ import annotations

import copy
import os

import pytest
import yaml

from containment import config, threshold, workflow
from containment import units as U

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXAMPLE = os.path.join(ROOT, "examples", "offshore_state_waters.yaml")


@pytest.fixture
def raw() -> dict:
    """The shipped example, pinned to the mud line alone."""
    with open(EXAMPLE, encoding="utf-8") as fh:
        d = yaml.safe_load(fh)
    d["offshore"].pop("first_permeable_base")
    d["offshore"]["reference"] = "mud_line"
    return d


def test_the_shipped_example_compares_both_references():
    p = config.Project.from_yaml(EXAMPLE)
    assert p.offshore["choice"] == "most_protective"
    rows = workflow.choose_offshore_reference(p).offshore["comparison"]
    assert {r["reference"] for r in rows} == set(config.OFFSHORE_REFERENCES.values())


def test_the_mud_line_replaces_the_usdw(raw):
    p = config.Project.from_dict(raw)
    assert p.reference_label == "mud line (seafloor)"
    assert U.length_out(p.usdw.base_depth, "ft") == pytest.approx(60.0)
    # one atmosphere plus 60 ft of seawater at 0.445 psi/ft
    assert U.pressure_out(p.usdw.initial_pressure, "psi") == pytest.approx(
        14.696 + 60 * 0.4455, abs=0.3)
    assert p.usdw.salinity == pytest.approx(0.035, rel=0.01)
    s = p.summary()
    assert s["usdw_base_ft"] is None
    assert s["critical_pressure_reference"] == "mud line (seafloor)"
    assert s["offshore"]["water_depth_ft"] == pytest.approx(60.0)
    assert "5.206(b)(2)" in s["offshore"]["basis"]
    assert not any("USDW" in w for w in p.warnings)


def test_the_first_permeable_stratum_is_the_other_reference(raw):
    raw["offshore"].update(reference="first_permeable", first_permeable_base=450)
    p = config.Project.from_dict(raw)
    assert p.reference_label.startswith("base of the first permeable stratum")
    assert U.length_out(p.usdw.base_depth, "ft") == pytest.approx(450.0)
    assert U.pressure_out(p.usdw.initial_pressure, "psi") == pytest.approx(
        14.696 + 450 * 0.4455, abs=1.0)


@pytest.mark.parametrize("change, message", [
    ({"water_depth": None, "reference": "mud_line"}, None),        # blank = onshore
    ({"reference": "first_permeable"}, "first_permeable_base"),
    ({"reference": "first_permeable", "first_permeable_base": 40}, "below the mud line"),
    ({"reference": "seabed"}, "offshore.reference"),
])
def test_offshore_inputs_are_checked(raw, change, message):
    raw["offshore"].update(change)
    if change.get("water_depth", 0) is None:
        raw["offshore"] = {k: None for k in raw["offshore"]}
        raw["formation"]["usdw"] = {"base_depth": 1000, "initial_pressure": 450}
        p = config.Project.from_dict(raw)
        assert not p.offshore and p.reference_label == "lowermost USDW"
        return
    with pytest.raises(ValueError, match=message):
        config.Project.from_dict(raw)


def test_a_usdw_given_as_well_is_set_aside_with_a_warning(raw):
    raw["formation"]["usdw"] = {"base_depth": 900, "initial_pressure": 400}
    p = config.Project.from_dict(raw)
    assert p.reference_label == "mud line (seafloor)"
    assert any("offshore and usdw are both given" in w for w in p.warnings)


def test_every_threshold_method_is_measured_against_the_mud_line(raw):
    p = config.Project.from_dict(raw)
    results = threshold.compare_methods(
        p_usdw=p.usdw.initial_pressure, p_inj=p.injection_zone.initial_pressure,
        depth_usdw=p.usdw.base_depth, depth_inj=p.threshold_depth,
        temperature_inj=p.injection_zone.temperature,
        temperature_usdw=p.usdw.temperature, salinity_inj=p.injection_zone.salinity,
        salinity_usdw=p.usdw.salinity)
    workflow.offshore_wording(results, p.reference_label)
    m1 = results[0]
    assert "p_reference_psi" in m1.inputs and "p_usdw_psi" not in m1.inputs
    assert m1.inputs["depth_reference_ft"] == pytest.approx(60.0)
    assert "16 TAC" in m1.citation
    assert not any("USDW" in w for r in results for w in r.warnings)
    # under-pressured sand: Method 1 applies, measured over 6,580 ft of brine
    assert m1.applicable and 150 < m1.delta_p_psi < 300


@pytest.mark.slow
def test_the_offshore_example_runs_and_reports_the_mud_line(raw):
    from containment import report

    p = config.Project.from_dict(raw)
    res = workflow.run(p, run_uncertainty=False)
    assert 2000 < res.aor.area_acres < 50000
    page = report.build_html(res, include_figures=False)
    assert "mud line (seafloor)" in page and "No USDW is assumed" in page


def test_the_offshore_section_round_trips_through_the_workbook(raw, tmp_path):
    from containment.io import workbook

    book = workbook.to_excel(copy.deepcopy(raw), str(tmp_path / "offshore.xlsx"))
    back = workbook.from_excel(book)
    assert back["offshore"]["water_depth"] == 60
    assert config.Project.from_dict(back).reference_label == "mud line (seafloor)"


def test_an_onshore_workbook_lists_the_offshore_keys_blank(tmp_path):
    from openpyxl import load_workbook

    from containment.io import workbook

    with open(os.path.join(ROOT, "examples", "gulf_coast_hub.yaml"),
              encoding="utf-8") as fh:
        d = yaml.safe_load(fh)
    d.pop("penetrations")
    book = workbook.to_excel(d, str(tmp_path / "onshore.xlsx"))
    keys = [r[0] for r in load_workbook(book)["Offshore"].iter_rows(values_only=True)]
    assert "water_depth" in keys and "first_permeable_base" in keys
    back = workbook.from_excel(book)
    assert config.Project.from_dict(back).reference_label == "lowermost USDW"


@pytest.mark.parametrize("fp_pressure, expected", [
    (150.0, "first_permeable"),     # below seawater hydrostatic: lower threshold
    (260.0, "mud_line"),            # above it: the mud line is more protective
])
def test_most_protective_keeps_the_lower_critical_pressure(raw, fp_pressure, expected):
    raw["offshore"].pop("reference")
    raw["offshore"].update(first_permeable_base=450, first_permeable_pressure=fp_pressure)
    p = config.Project.from_dict(raw)
    assert p.offshore["choice"] == "most_protective"
    chosen = workflow.choose_offshore_reference(p)
    rows = chosen.offshore["comparison"]
    assert len(rows) == 2 and sum(r["used"] for r in rows) == 1
    used = next(r for r in rows if r["used"])
    other = next(r for r in rows if not r["used"])
    assert used["threshold_psi"] <= other["threshold_psi"]
    assert chosen.offshore["reference"] == expected
    assert chosen.reference_label == config.OFFSHORE_REFERENCES[expected]
    assert "alternatives" not in chosen.offshore
    assert chosen.summary()["offshore"]["compared"] == rows


def test_a_single_named_reference_is_not_compared(raw):
    p = config.Project.from_dict(raw)              # reference: mud_line
    assert workflow.choose_offshore_reference(p) is p
