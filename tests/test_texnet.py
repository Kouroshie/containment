"""Live TexNet screening, tested offline against a fake TexNet."""

import math

import pytest
from shapely.geometry import box

from containment import texnet as TX

# a 0.1 x 0.1 degree AoR at the Texas-centre placeholder used by the examples
LON0, LAT0 = -99.9018, 31.9686
AOR = box(LON0 - 0.05, LAT0 - 0.05, LON0 + 0.05, LAT0 + 0.05)


def _ring(lon, lat, r_deg, n=72):
    return [[lon + r_deg * math.cos(2 * math.pi * k / n) / math.cos(math.radians(lat)),
             lat + r_deg * math.sin(2 * math.pi * k / n)] for k in range(n + 1)]


def _catalog():
    rows = [  # id, time, mag, lon, lat, status
        ("in", "2024-03-01T01:02:03Z", 2.6, LON0, LAT0, "final"),
        ("near", "2025-05-05T00:00:00Z", 3.1, LON0 + 0.08, LAT0, "final"),   # ~2 mi east
        ("far", "2025-06-06T00:00:00Z", 4.0, LON0 + 1.5, LAT0, "final"),     # ~85 mi
        ("small", "2025-07-07T00:00:00Z", 1.5, LON0, LAT0, "automatic"),
    ]
    fields = ["id", "time", "magnitude", "magType", "depth", "evaluationStatus",
              "evaluationMode", "place", "countyName"]
    vals = {f: [] for f in fields}
    for i, t, m, _x, _y, s in rows:
        for f, v in zip(fields, [i, t, m, "ML", 7.5, s, "manual", "Texas", "TEST"], strict=True):
            vals[f].append(v)
    return {"format": "compact", "fields": fields, "lon": [r[3] for r in rows],
            "lat": [r[4] for r in rows], "values": [vals[f] for f in fields]}


def _wells():
    def w(uic, lon, lat, last):
        return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {"UICNumber": uic, "APINumber": "42000", "LeaseName": "TEST ",
                               "WellNumber": "  1D ", "InjectionTopInterval": 4750.0,
                               "InjectionBottomInterval": 5600.0, "FirstInjection": 1577836800000,
                               "LastInjection": last}}
    return {"features": [w("000000001", LON0 + 0.01, LAT0, 1793422800000),
                         w("000000002", LON0 + 0.09, LAT0, None),       # ~2.5 mi out
                         w("000000003", LON0 + 2.0, LAT0, None)]}       # far


def _sir(layer):
    if layer == 4:   # a 25 km ring that holds the whole AoR without crossing it
        return {"features": [{"type": "Feature", "properties": {"fault_type": "25 KM TEST"},
                              "geometry": {"type": "LineString",
                                           "coordinates": _ring(LON0, LAT0, 0.22)}}]}
    if layer == 0:   # a 2 km ring centred on the AoR's east edge: overlaps it
        return {"features": [{"type": "Feature", "properties": {"fault_type": "2 KM TEST"},
                              "geometry": {"type": "LineString",
                                           "coordinates": _ring(LON0 + 0.05, LAT0, 0.018)}}]}
    return {"features": []}


def fake(url, timeout=None):
    if url.startswith(TX.CATALOG):
        return _catalog()
    if "/injection/Injection/MapServer/0/" in url:
        return _wells()
    if "/injection/Injection/MapServer/2/" in url:
        return {"features": [{"type": "Feature", "geometry": None,
                              "properties": {"UICNumber": "000000001",
                                             "LastInjectionPressure": 1793422800000}}]}
    if "/sra/sir/MapServer/" in url:
        return _sir(int(url.split("/MapServer/")[1].split("/")[0]))
    if "/sra/sra/MapServer/" in url:
        return {"features": []}
    raise AssertionError(f"unexpected url {url}")


def down(url, timeout=None):
    raise OSError("network unreachable")


def test_catalog_compact_json_becomes_rows():
    rows = TX._catalog_rows(_catalog())
    assert len(rows) == 4
    assert rows[0]["id"] == "in" and rows[0]["lon"] == LON0 and rows[0]["magnitude"] == 2.6


def test_earthquakes_within_reach_and_above_magnitude_nearest_first():
    part = TX.earthquakes_near(AOR, 5.0, fetch=fake)
    assert part.status == "live"
    assert [r["event"] for r in part.rows] == ["in", "near"]
    assert part.rows[0]["in the AoR"] == "yes" and part.rows[0]["date"] == "2024-03-01"
    assert 1.0 < part.rows[1]["distance from the AoR (mi)"] < 3.0
    assert len(part.features) == 2


def test_earthquakes_fall_back_to_the_bundled_snapshot():
    from containment import fault_layers as FL

    part = TX.earthquakes_near(AOR, 5.0, fetch=down)
    if FL.layers_dir() is None:
        assert part.status == "unavailable"
    else:
        assert part.status == "snapshot"
    assert "network unreachable" in part.error


def test_injection_wells_join_pressure_and_convert_dates():
    part = TX.injection_wells_near(AOR, 5.0, fetch=fake)
    assert part.status == "live"
    assert [r["UIC number"] for r in part.rows] == ["000000001", "000000002"]
    first = part.rows[0]
    assert first["in the AoR"] == "yes" and first["well"] == "1D" and first["lease"] == "TEST"
    assert first["top (ft)"] == 4750 and first["last injection report"] == "2026-10-31"
    assert first["first injection report"] == "2020-01-01"
    assert first["pressure reports"] == "yes"
    assert part.rows[1]["pressure reports"] == "no" and part.rows[1]["in the AoR"] == "no"


def test_a_ring_that_holds_the_aor_is_found_although_it_never_crosses_it():
    part = TX.seismic_areas_near(AOR, 5.0, fetch=fake)
    assert part.status == "live"
    rel = {r["name"]: r for r in part.rows}
    assert rel["25 KM TEST"]["relation"] == "AoR inside"
    assert rel["25 KM TEST"]["share of the AoR inside (%)"] == pytest.approx(100.0)
    assert rel["2 KM TEST"]["relation"] == "overlaps the AoR"
    assert 0 < rel["2 KM TEST"]["share of the AoR inside (%)"] < 100
    assert part.rows[0]["relation"] == "AoR inside"          # inside first


def test_near_survives_texnet_being_down():
    tx = TX.near(AOR, 5.0, fetch=down)
    assert tx.wells.status == "unavailable" and tx.areas.status == "unavailable"
    assert "network unreachable" in tx.wells.error
    s = tx.summary()
    assert s["injection_wells"] == 0 and s["seismic_areas_touching_aor"] == 0


def test_near_summary():
    s = TX.near(AOR, 5.0, fetch=fake).summary()
    assert s["earthquakes"] == 2 and s["largest_magnitude"] == 3.1
    assert s["injection_wells"] == 2 and s["injection_wells_in_aor"] == 1
    assert s["seismic_areas_touching_aor"] == 2


def test_no_aor_means_nothing_fetched():
    def boom(url, timeout=None):
        raise AssertionError("should not fetch")
    tx = TX.near(None, 5.0, fetch=boom)
    assert tx.earthquakes.status == tx.wells.status == tx.areas.status == "unavailable"


def test_cache_returns_the_same_answer_without_refetching():
    TX.clear_cache()
    calls = []
    a = TX._cached(("t", 1), lambda: calls.append(1) or "x")
    b = TX._cached(("t", 1), lambda: calls.append(1) or "y")
    assert a == b == "x" and len(calls) == 1
    TX.clear_cache()
