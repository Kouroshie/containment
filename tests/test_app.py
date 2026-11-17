"""The browser app renders, and its controls carry the help text they claim to.

The app script is not importable in the usual sense: it runs top to bottom on
every rerun and talks to a live Streamlit session.  Streamlit's own AppTest
harness runs it the way the server does, which is the only way to catch the
class of bug where a widget looks like every other widget but rejects an
argument.  That is not hypothetical: ``st.data_editor`` takes no ``help``,
unlike every other input on the page, and this test is why that was found
before it reached the deployed app rather than after.

The app is a set of pages behind sidebar buttons (keys ``nav_<page>``), with
Run in the sidebar (key ``run``); the helpers below drive it the way a user
does.
"""

from __future__ import annotations

import os

import pytest

pytest.importorskip("streamlit")
pytest.importorskip("plotly")
from streamlit.testing.v1 import AppTest  # noqa: E402

APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "app", "streamlit_app.py")


def _at(timeout=600):
    return AppTest.from_file(APP, default_timeout=timeout).run()


def _go(at, page):
    at.button(key=f"nav_{page}").click().run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def _run(at):
    at.button(key="run").click().run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def test_app_renders_without_running_a_model():
    at = _at(120)
    assert not at.exception, [e.value for e in at.exception]
    keys = [b.key for b in at.button]
    assert "run" in keys
    nav = [k for k in keys if (k or "").startswith("nav_")]
    assert nav == ["nav_start", "nav_site", "nav_wells", "nav_model", "nav_summary",
                   "nav_maps", "nav_corrective", "nav_threshold", "nav_pisc",
                   "nav_uncertainty", "nav_export", "nav_help"]
    # result pages wait for a run
    assert at.button(key="nav_summary").disabled and not at.button(key="nav_help").disabled


def test_upload_project_offers_both_templates():
    at = _at(120)
    at.radio(key="source").set_value("Upload project").run()
    assert not at.exception, [e.value for e in at.exception]
    labels = [b.proto.label for b in at.get("download_button")]
    assert "Project template (Excel, recommended)" in labels
    assert "Project template (YAML)" in labels


def test_every_form_control_explains_itself():
    """The form is the whole model, so no knob may be unlabelled."""
    at = _at(120)
    for page in ("site", "model"):
        _go(at, page)
        bare = [w.label for group in (at.number_input, at.slider, at.selectbox, at.radio,
                                      at.checkbox)
                for w in group if not (w.help or "").strip()]
        assert not bare, f"controls with no help text on {page}: {bare}"


def test_form_values_survive_moving_between_pages():
    at = _go(_at(120), "site")
    at.number_input(key="iz_k").set_value(321.0).run()
    _go(at, "model")
    _go(at, "site")
    assert at.number_input(key="iz_k").value == 321.0
    _go(at, "wells")
    assert len(at.session_state["wells_rows"]) == 2


@pytest.mark.slow
def test_a_full_run_fills_every_panel():
    at = _run(_at())
    assert at.session_state["page"] == "summary"
    labels = [m.label for m in at.metric]
    assert labels == ["AoR area", "Threshold dP"]
    assert "ct-flag" in " ".join(m.value for m in at.markdown)   # review flags

    _go(at, "maps")
    assert at.radio(key="map_view").options == [
        "Plan view", "GIS map and faults", "Over time"]      # no Zones for one zone
    _go(at, "corrective")
    downloads = [b.proto.label for b in at.get("download_button")]
    assert "Penetration template (Excel)" in downloads
    assert "Penetration template (CSV)" in downloads
    _go(at, "threshold")
    assert any("Positive or negative threshold" in e.label for e in at.expander)
    assert "aor-lead" in " ".join(m.value for m in at.markdown)   # orientation note
    for p in ("pisc", "uncertainty", "export", "help"):
        _go(at, p)
    assert "Glossary" in " ".join(m.value for m in at.markdown)   # the Help page


@pytest.mark.slow
def test_maps_can_show_any_model_year():
    at = _go(_run(_at()), "maps")
    at.select_slider(key="yr_aor").set_value(3).run()
    assert not at.exception, [e.value for e in at.exception]
    caps = " ".join(c.value for c in at.caption)
    assert "AoR" in caps and "(final" in caps
    at.radio(key="map_view").set_value("GIS map and faults").run()
    assert not at.exception, [e.value for e in at.exception]
    assert [s for s in at.select_slider if s.key == "yr_gis"]


@pytest.mark.slow
def test_ticking_stacked_completion_adds_a_zones_view():
    """The stacked path has its own widgets, its own view and its own figures,
    none of which the single-zone run exercises."""
    at = _go(_at(900), "site")
    box = [c for c in at.checkbox if "more than one formation" in c.label]
    assert box, [c.label for c in at.checkbox]
    box[0].check().run()
    assert not at.exception, [e.value for e in at.exception]

    _go(_run(at), "maps")
    views = at.radio(key="map_view").options
    assert "Zones" in views and "Over time" in views
    at.radio(key="map_view").set_value("Zones").run()
    assert not at.exception, [e.value for e in at.exception]
    assert "union" in " ".join(m.value for m in at.markdown).lower()

    # PISC: every zone in a table, and a picker for each zone's curves
    _go(at, "pisc")
    assert "Every injection zone" in " ".join(m.value for m in at.markdown)
    pick = at.selectbox(key="pisc_zone")
    assert len(pick.options) == 2
    assert sum("governs PISC" in o for o in pick.options) == 1
    assert "largest AoR" in pick.help       # the ? says how the zone is picked
    pick.select_index(1).run()
    assert not at.exception, [e.value for e in at.exception]


@pytest.mark.slow
def test_a_result_from_an_older_version_still_renders():
    """A session outlives a deployment.

    The result object lives in session state, so after an update the page can
    still be holding one built by the previous version of the code, without
    the attributes added since. That is not hypothetical: it took the live app
    down with an AttributeError the first time a stacked-zone build shipped.
    """
    at = _run(_at())
    stale = at.session_state["result"]
    for added_later in ("zones", "series"):
        assert hasattr(stale, added_later)
        delattr(stale, added_later)          # what an older object looks like

    at.run()
    assert not at.exception, [e.value for e in at.exception]
    _go(at, "maps")
    at.radio(key="map_view").set_value("Over time").run()
    assert not at.exception, [e.value for e in at.exception]


class _Upload:
    """Stands in for Streamlit's UploadedFile."""

    def __init__(self, name: str, data: bytes):
        self.name, self.size, self.file_id = name, len(data), f"test-{name}"
        self._data = data

    def getvalue(self) -> bytes:
        return self._data


def test_uploaded_wells_reach_the_gis_map_coloured_by_action(monkeypatch):
    """A well list uploaded on the Corrective action page is screened before any
    page is drawn, so the maps show it too, also after leaving the page."""
    import streamlit as st

    csv = (b"name,api,type,status,latitude,longitude,total_depth\n"
           b"OLD-1,42-000-00001,dry hole,abandoned,31.9690,-99.9015,7000\n"
           b"NEW-1,42-000-00002,permitted location,\"permitted, not drilled\","
           b"31.9680,-99.9020,7000\n")
    real = st.file_uploader

    def fake(label, *a, key=None, **k):
        if key == "pens":
            st.session_state["pens"] = _Upload("wells.csv", csv)
            return st.session_state["pens"]
        return real(label, *a, key=key, **k)

    monkeypatch.setattr(st, "file_uploader", fake)
    at = _go(_run(_at()), "corrective")
    at.run()                                  # the upload is seen from this rerun on
    assert not at.exception, [e.value for e in at.exception]
    plan = at.session_state["result"].corrective
    actions = {w.name: w.action for w in plan.inside}
    assert actions["NEW-1"] == "track" and actions["OLD-1"] != "no action"
    assert any("also on the GIS map" in c.value for c in at.caption)
    _go(at, "maps")
    at.radio(key="map_view").set_value("GIS map and faults").run()
    assert not at.exception, [e.value for e in at.exception]
    assert not any("To show wells here" in c.value for c in at.caption)


@pytest.mark.slow
def test_the_offshore_box_switches_the_form_to_the_mud_line():
    at = _go(_at(), "site")
    box = next(c for c in at.checkbox if c.label == "offshore project (no USDW)")
    box.check().run()
    keys = [n.key for n in at.number_input]
    assert "off_wd" in keys and "us_d" not in keys        # water depth, no USDW base
    bare = [w.label for group in (at.number_input, at.selectbox)
            for w in group if not (w.help or "").strip()]
    assert not bare
    _run(at)
    assert any("Offshore project" in i.value and "mud line" in i.value for i in at.info)


@pytest.mark.slow
def test_gis_map_reruns_with_the_mapped_faults_near_the_aor():
    at = _go(_run(_at(900)), "maps")
    at.radio(key="map_view").set_value("GIS map and faults").run()
    assert not at.exception, [e.value for e in at.exception]
    at.number_input(key="fault_reach").set_value(25.0).run()
    at.button(key="fault_run").click().run()
    assert not at.exception, [e.value for e in at.exception]
    runs = [r for df in at.dataframe for r in (df.value["run"].tolist()
                                              if "run" in getattr(df.value, "columns", []) else [])]
    assert any("mapped fault trace" in r for r in runs)


@pytest.mark.slow
def test_threshold_page_explains_every_method():
    at = _go(_run(_at()), "threshold")
    text = " ".join(m.value for m in at.markdown)
    for phrase in ("How the methods work", "Pressure regime of this site",
                   "Method 1 and Method 2: the difference", "Which one this AoR uses",
                   "Method 3 shows n/a"):
        assert phrase in text, phrase
    labels = [e.label for e in at.expander]
    assert any(x.startswith("Method 2b") for x in labels)
    assert any(x.startswith("Method 3") for x in labels)


def test_pisc_page_explains_each_curve():
    at = _go(_run(_at()), "pisc")
    text = " ".join(m.value for m in at.markdown)
    for phrase in ("**Area.**", "**Plume migration rate.**", "**Pressure decline.**",
                   "end of injection"):
        assert phrase in text, phrase


def test_an_example_with_uncertainty_ticks_the_run_option():
    at = _at(120)
    at.radio(key="source").set_value("Shipped example").run()
    at.selectbox(key="example_pick").set_value("showcase_full.yaml").run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state["unc"] is True
    assert at.session_state["n_real"] == 120
    # an example without it leaves the option off
    at.selectbox(key="example_pick").set_value("stacked_zones.yaml").run()
    assert at.session_state["unc"] is False
