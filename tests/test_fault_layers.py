"""Bundled Texas fault layers: they load, are sourced, and screen an AoR."""

import pytest
from shapely.geometry import LineString, Polygon, box

from containment import fault_layers as FL

pytestmark = pytest.mark.skipif(FL.layers_dir() is None, reason="app/layers not built")


def test_every_layer_is_sourced_and_licensed():
    man = FL.manifest()
    ids = {m["id"] for m in man}
    assert {"tx_faults_250k", "gulf_coast_faults", "permian_basement_faults"} <= ids
    for m in man:
        assert m["source"] and m["licence"] and m["note"] and m["count"] > 0
        assert m["kind"] in ("surface", "subsurface", "seismicity")


def test_clip_returns_only_features_in_the_window():
    fc = FL.clip("permian_basement_faults", (-102.5, 31.5, -101.5, 32.5))
    win = box(-102.5, 31.5, -101.5, 32.5)
    from shapely.geometry import shape
    assert fc["features"]
    assert all(shape(f["geometry"]).intersects(win) for f in fc["features"])


def test_screen_finds_a_fault_that_crosses_and_measures_distance():
    # a small box across a known Midland Basin basement fault (Midland example area)
    aor = Polygon([(-102.05, 32.02), (-101.93, 32.02), (-101.93, 32.12), (-102.05, 32.12)])
    rows = FL.near_aor(aor, 1.0)
    assert any(r["crosses the AoR"] == "yes" for r in rows)
    assert all(r["distance from the AoR (ft)"] <= 5280 for r in rows)
    assert rows == sorted(rows, key=lambda r: (r["crosses the AoR"] != "yes",
                                              r["distance from the AoR (ft)"]))


def test_mapped_faults_become_model_fault_traces():
    aor = Polygon([(-102.05, 32.02), (-101.93, 32.02), (-101.93, 32.12), (-102.05, 32.12)])
    faults = FL.as_model_faults(aor, 1.0, multiplier=0.1)
    assert faults and all(f["multiplier"] == 0.1 and len(f["latlon"]) >= 2 for f in faults)
    lat, lon = faults[0]["latlon"][0]
    assert 25 < lat < 37 and -107 < lon < -93           # [lat, lon] order, as faults: expects
    assert LineString([(q[1], q[0]) for q in faults[0]["latlon"]]).length > 0


def test_earthquakes_near_counts_events():
    aor = Polygon([(-104.0, 31.4), (-103.6, 31.4), (-103.6, 31.8), (-104.0, 31.8)])   # Delaware Basin
    eq = FL.earthquakes_near(aor, 5.0)
    assert eq["count"] > 0 and eq["max_magnitude"] >= 2.0
