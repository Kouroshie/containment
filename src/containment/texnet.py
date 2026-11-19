"""Live TexNet data near an AoR: earthquakes, injection wells and seismic areas.

TexNet (the Texas Seismological Network at the Bureau of Economic Geology)
publishes, with no login:

* the earthquake catalog, ``catalog.texnet.beg.utexas.edu/api/earthquake/events``,
  the same call the catalog's own map makes. It ignores location filters, so
  the statewide list since 2017 (~16,000 events, ~4 MB) is fetched once an hour
  and screened here;
* injection wells that report daily volumes or pressures to TexNet (ArcGIS
  ``injection/Injection`` layers 0 and 2), queried by a box around the AoR;
* seismic investigation regions (SIRs, rings of 2, 4.5, 9, 15 and 25 km around
  earthquake clusters, ``sra/sir`` layers 0 to 4) and seismic response areas
  (``sra/sra`` layers 8 to 10 and 12). The SIR and SRA boundaries are stored as
  LINES, so a plain "intersects" query misses an AoR that sits wholly inside a
  ring; the rings are fetched for a wider box and closed into areas here.

Each part is fetched on its own and fails on its own: a part that cannot be
reached says so (``status`` "unavailable" with the error), and the
earthquakes fall back to the snapshot that ships in ``app/layers``. Nothing
here is a model input. It is screening context for a reviewer, like the
mapped faults in :mod:`containment.fault_layers`.
"""

from __future__ import annotations

import datetime as _dt
import json
import ssl
import threading
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

from . import units as U

CATALOG = "https://catalog.texnet.beg.utexas.edu/api/earthquake/events"
CATALOG_PAGE = "https://catalog.texnet.beg.utexas.edu"
MAPS = "https://maps.texnet.beg.utexas.edu/arcgis/rest/services"
INJECTION = MAPS + "/injection/Injection/MapServer"
SIR_LAYERS = {0: "2 km", 1: "4.5 km", 2: "9 km", 3: "15 km", 4: "25 km"}
SRA_LAYERS = {8: "Stanton operator-led SRA, inner area",
              9: "Stanton operator-led SRA, intermediate area",
              10: "Stanton operator-led SRA, outer area",
              12: "Seismic response area (SRA)"}
CATALOG_START = "2017-01-01"
CACHE_SECONDS = 3600
UA = {"User-Agent": "containment (open-source Class VI AoR toolkit)"}


# --------------------------------------------------------------------------
# fetching
# --------------------------------------------------------------------------
def _ssl_context():
    """Certificates from certifi when installed: the catalog's issuer (InCommon /
    emSign) is missing from some system stores, notably Windows in Nov 2026."""
    try:
        import certifi
    except ImportError:
        return ssl.create_default_context()
    return ssl.create_default_context(cafile=certifi.where())


_SSL = _ssl_context()


def get_json(url: str, timeout: float = 20.0):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout, context=_SSL) as r:
        return json.loads(r.read())


_cache: dict = {}
_lock = threading.Lock()


def _cached(key, fn, seconds: float = CACHE_SECONDS):
    now = time.time()
    with _lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < seconds:
            return hit[1]
    val = fn()
    with _lock:
        _cache[key] = (now, val)
    return val


def cached_get_json(url: str, timeout: float = 20.0):
    """:func:`get_json` remembered for an hour, so moving around the app does not refetch."""
    return _cached(("url", url), lambda: get_json(url, timeout=timeout))


def clear_cache() -> None:
    with _lock:
        _cache.clear()


# --------------------------------------------------------------------------
# geometry helpers
# --------------------------------------------------------------------------
def _local_tm(aor_lonlat):
    """Forward transform lon/lat -> metres in a transverse Mercator centred on the AoR."""
    import pyproj

    c = aor_lonlat.centroid
    return pyproj.Transformer.from_crs(
        4326, pyproj.CRS.from_proj4(f"+proj=tmerc +lat_0={c.y} +lon_0={c.x} +k=1 +x_0=0 "
                                    "+y_0=0 +ellps=GRS80 +units=m"), always_xy=True).transform


def _box(aor_lonlat, pad_mi: float) -> tuple[float, float, float, float]:
    """A lon/lat box around the AoR, padded by at least ``pad_mi``."""
    import math

    x0, y0, x1, y1 = aor_lonlat.bounds
    dlat = pad_mi / 69.0
    dlon = pad_mi / (69.0 * max(math.cos(math.radians(0.5 * (y0 + y1))), 0.2))
    return (x0 - dlon, y0 - dlat, x1 + dlon, y1 + dlat)


def _ms_date(v) -> str:
    """ArcGIS epoch milliseconds -> ISO date ('' when missing)."""
    if v in (None, ""):
        return ""
    try:
        return _dt.datetime.fromtimestamp(float(v) / 1000.0, _dt.UTC).date().isoformat()
    except (TypeError, ValueError, OverflowError, OSError):
        return ""


def _arcgis_query(url: str, bbox, out_fields: str, fetch=get_json, page: int = 2000) -> list:
    """GeoJSON features of one ArcGIS layer inside a lon/lat box, all pages."""
    feats, off = [], 0
    while True:
        q = urllib.parse.urlencode({
            "where": "1=1", "geometry": ",".join(f"{v:.6f}" for v in bbox),
            "geometryType": "esriGeometryEnvelope", "inSR": 4326, "outSR": 4326,
            "spatialRel": "esriSpatialRelIntersects", "outFields": out_fields,
            "returnGeometry": "true", "f": "geojson",
            "resultOffset": off, "resultRecordCount": page})
        d = fetch(url + "/query?" + q)
        if isinstance(d, dict) and d.get("error"):
            raise RuntimeError(f"TexNet map service error: {d['error'].get('message', d['error'])}")
        fs = (d or {}).get("features") or []
        feats += fs
        off += len(fs)
        if len(fs) < page:
            return feats


# --------------------------------------------------------------------------
# results
# --------------------------------------------------------------------------
@dataclass
class Part:
    """One kind of TexNet data near the AoR."""
    status: str = "unavailable"        # live | snapshot | unavailable
    rows: list = field(default_factory=list)
    features: list = field(default_factory=list)   # GeoJSON for the map
    error: str = ""
    source: str = ""
    fetched: str = ""


@dataclass
class TexNetNear:
    distance_mi: float
    earthquakes: Part
    wells: Part
    areas: Part

    def summary(self) -> dict:
        eq = self.earthquakes.rows
        mags = [r["magnitude"] for r in eq if r.get("magnitude") is not None]
        inside = [a for a in self.areas.rows if a["relation"] != "outside"]
        return {
            "distance_mi": self.distance_mi,
            "earthquakes": len(eq), "largest_magnitude": max(mags) if mags else None,
            "earthquakes_status": self.earthquakes.status,
            "injection_wells": len(self.wells.rows),
            "injection_wells_in_aor": sum(r["in the AoR"] == "yes" for r in self.wells.rows),
            "wells_status": self.wells.status,
            "seismic_areas_touching_aor": len(inside),
            "areas_status": self.areas.status,
        }


# --------------------------------------------------------------------------
# earthquakes
# --------------------------------------------------------------------------
def _catalog_rows(payload: dict) -> list[dict]:
    """The catalog's compact JSON (fields + lon + lat + one value list per field)
    as one dict per event."""
    fields, cols = payload["fields"], payload["values"]
    lon, lat = payload["lon"], payload["lat"]
    out = []
    for i in range(len(lon)):
        r = {f: cols[k][i] for k, f in enumerate(fields)}
        r["lon"], r["lat"] = lon[i], lat[i]
        out.append(r)
    return out


def statewide_earthquakes(min_magnitude: float = 2.0, fetch=get_json,
                          timeout: float = 30.0) -> list[dict]:
    """Every TexNet event since 2017 at or above ``min_magnitude`` (cached an hour)."""
    def go():
        end = (_dt.datetime.now(_dt.UTC) + _dt.timedelta(days=1)).strftime("%Y-%m-%dT00:00:00Z")
        q = urllib.parse.urlencode({"start": CATALOG_START + "T00:00:00Z", "end": end,
                                    "minmag": min_magnitude, "maxmag": 10,
                                    "mindepth": 0, "maxdepth": 999})
        try:
            d = fetch(f"{CATALOG}?{q}", timeout=timeout)
        except TypeError:                       # a test fetch without a timeout
            d = fetch(f"{CATALOG}?{q}")
        return _catalog_rows(d)
    if fetch is not get_json:
        return go()
    return _cached(("eq", min_magnitude), go)


def earthquakes_near(aor_lonlat, distance_mi: float = 5.0, min_magnitude: float = 2.0,
                     fetch=get_json) -> Part:
    """TexNet earthquakes within ``distance_mi`` of the AoR, nearest first.

    Live from the catalog; if that fails, the bundled snapshot (status
    'snapshot'); if neither, status 'unavailable'."""
    from shapely.geometry import Point
    from shapely.ops import transform

    part = Part(source=CATALOG_PAGE)
    if aor_lonlat is None or aor_lonlat.is_empty:
        part.error = "the project is not georeferenced"
        return part
    tm = _local_tm(aor_lonlat)
    aor_m = transform(tm, aor_lonlat)
    reach = U.length(distance_mi, "mi")
    bx = _box(aor_lonlat, distance_mi + 1)
    try:
        events = statewide_earthquakes(min_magnitude, fetch=fetch)
        part.status = "live"
        part.fetched = _dt.datetime.now(_dt.UTC).strftime("%Y-%m-%d %H:%M UTC")
    except Exception as e:  # noqa: BLE001  network, TLS, JSON: fall back to the snapshot
        part.error = f"{type(e).__name__}: {e}"
        events = _snapshot_events()
        if events is None:
            return part
        part.status = "snapshot"
        part.source = "bundled snapshot of the TexNet catalog"
    for r in events:
        lon, lat = r.get("lon"), r.get("lat")
        if lon is None or lat is None or not (bx[0] <= lon <= bx[2] and bx[1] <= lat <= bx[3]):
            continue
        mag = r.get("magnitude")
        if mag is None or float(mag) < min_magnitude:
            continue
        d = aor_m.distance(Point(*tm(lon, lat)))
        if d > reach:
            continue
        when = str(r.get("time") or "")[:10]
        depth = r.get("depth")
        row = {"event": r.get("id", ""), "date": when, "magnitude": round(float(mag), 1),
               "depth (km)": round(float(depth), 1) if depth not in (None, "") else None,
               "in the AoR": "yes" if d == 0 else "no",
               "distance from the AoR (mi)": round(U.length_out(d, "mi"), 2),
               "review status": r.get("evaluationStatus", ""),
               "county": r.get("countyName", "")}
        part.rows.append(row)
        part.features.append({"type": "Feature",
                              "geometry": {"type": "Point", "coordinates": [lon, lat]},
                              "properties": row})
    part.rows.sort(key=lambda x: (x["distance from the AoR (mi)"], x["date"]))
    return part


def _snapshot_events():
    """The bundled earthquake layer in the catalog's row shape, or None."""
    try:
        from . import fault_layers as FL

        if not any(m["id"] == "texnet_earthquakes" for m in FL.manifest()):
            return None
        geoms, props = FL._load("texnet_earthquakes")
    except Exception:  # noqa: BLE001
        return None
    out = []
    for g, p in zip(geoms, props, strict=True):
        try:
            depth = float(p.get("depth_km")) if p.get("depth_km") not in (None, "") else None
        except (TypeError, ValueError):
            depth = None
        out.append({"id": p.get("id", ""), "time": p.get("date", ""), "magnitude": p.get("mag"),
                    "depth": depth, "lon": g.x, "lat": g.y,
                    "evaluationStatus": "", "countyName": ""})
    return out


# --------------------------------------------------------------------------
# injection wells
# --------------------------------------------------------------------------
_WELL_FIELDS = ("UICNumber,APINumber,LeaseName,WellNumber,FormationName,FieldName,CountyName,"
                "InjectionTopInterval,InjectionBottomInterval,MSIP,TotalBPDMax,"
                "FirstInjection,LastInjection,InjectionCount")


def injection_wells_near(aor_lonlat, distance_mi: float = 5.0, fetch=get_json) -> Part:
    """Injection wells that report to TexNet within ``distance_mi`` of the AoR."""
    from shapely.geometry import Point
    from shapely.ops import transform

    part = Part(source=INJECTION)
    if aor_lonlat is None or aor_lonlat.is_empty:
        part.error = "the project is not georeferenced"
        return part
    tm = _local_tm(aor_lonlat)
    aor_m = transform(tm, aor_lonlat)
    reach = U.length(distance_mi, "mi")
    bx = _box(aor_lonlat, distance_mi + 0.5)
    try:
        wells = _arcgis_query(INJECTION + "/0", bx, _WELL_FIELDS, fetch)
        try:
            pres = _arcgis_query(INJECTION + "/2", bx,
                                 "UICNumber,FirstInjectionPressure,LastInjectionPressure", fetch)
        except Exception:  # noqa: BLE001  pressure is extra; the volumes still stand
            pres = []
    except Exception as e:  # noqa: BLE001
        part.error = f"{type(e).__name__}: {e}"
        return part
    part.status = "live"
    part.fetched = _dt.datetime.now(_dt.UTC).strftime("%Y-%m-%d %H:%M UTC")
    pmap = {(f.get("properties") or {}).get("UICNumber"): f.get("properties") or {} for f in pres}
    for f in wells:
        g, p = f.get("geometry"), f.get("properties") or {}
        if not g or g.get("type") != "Point":
            continue
        lon, lat = g["coordinates"][:2]
        d = aor_m.distance(Point(*tm(lon, lat)))
        if d > reach:
            continue
        pp = pmap.get(p.get("UICNumber"), {})

        def num(v):
            try:
                return round(float(v)) if v not in (None, "") else None
            except (TypeError, ValueError):
                return None
        def txt(v):
            return str(v).strip() if v not in (None, "") else ""
        row = {"UIC number": txt(p.get("UICNumber")), "API": txt(p.get("APINumber")),
               "lease": txt(p.get("LeaseName")), "well": txt(p.get("WellNumber")),
               "formation": txt(p.get("FormationName")),
               "top (ft)": num(p.get("InjectionTopInterval")),
               "bottom (ft)": num(p.get("InjectionBottomInterval")),
               "max pressure (psi)": num(p.get("MSIP")),
               "max rate (bbl/d)": num(p.get("TotalBPDMax")),
               "first injection report": _ms_date(p.get("FirstInjection")),
               "last injection report": _ms_date(p.get("LastInjection")),
               "pressure reports": "yes" if pp else "no",
               "last pressure report": _ms_date(pp.get("LastInjectionPressure")),
               "in the AoR": "yes" if d == 0 else "no",
               "distance from the AoR (mi)": round(U.length_out(d, "mi"), 2)}
        part.rows.append(row)
        part.features.append({"type": "Feature",
                              "geometry": {"type": "Point", "coordinates": [lon, lat]},
                              "properties": row})
    part.rows.sort(key=lambda r: r["distance from the AoR (mi)"])
    return part


# --------------------------------------------------------------------------
# seismic investigation regions and response areas
# --------------------------------------------------------------------------
def _as_area(geom):
    """A polygon from a SIR/SRA ring (lines are closed into areas)."""
    from shapely.geometry import shape
    from shapely.ops import polygonize, unary_union

    g = shape(geom)
    if g.geom_type in ("Polygon", "MultiPolygon"):
        return g if g.is_valid else g.buffer(0)
    polys = list(polygonize(unary_union(g)))
    if not polys:                       # an unclosed trace: close each part
        from shapely.geometry import Polygon

        parts = list(getattr(g, "geoms", [g]))
        polys = [Polygon(list(p.coords)) for p in parts if len(p.coords) >= 3]
    return unary_union([p if p.is_valid else p.buffer(0) for p in polys]) if polys else None


def seismic_areas_near(aor_lonlat, distance_mi: float = 5.0, fetch=get_json) -> Part:
    """SIRs and SRAs that contain, overlap or lie within ``distance_mi`` of the AoR."""
    from shapely.geometry import mapping
    from shapely.ops import transform

    part = Part(source=MAPS + "/sra")
    if aor_lonlat is None or aor_lonlat.is_empty:
        part.error = "the project is not georeferenced"
        return part
    tm = _local_tm(aor_lonlat)
    aor_m = transform(tm, aor_lonlat)
    reach = U.length(distance_mi, "mi")
    # a 25 km ring can hold the AoR without crossing it: look 35 km (~22 mi) out
    bx = _box(aor_lonlat, max(distance_mi, 0) + 22)
    errors, got_any = [], False
    jobs = ([(f"{MAPS}/sra/sir/MapServer/{k}", f"{v} seismic investigation region (SIR)")
             for k, v in SIR_LAYERS.items()]
            + [(f"{MAPS}/sra/sra/MapServer/{k}", v) for k, v in SRA_LAYERS.items()])
    from concurrent.futures import ThreadPoolExecutor

    def one(job):
        try:
            return job, _arcgis_query(job[0], bx, "*", fetch), None
        except Exception as e:  # noqa: BLE001
            return job, None, e

    # the layers answer independently; one slow layer should not hold up the rest
    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        answers = list(pool.map(one, jobs))
    for (_url, kind), feats, err in answers:
        if err is not None:
            errors.append(f"{kind}: {type(err).__name__}: {err}")
            continue
        got_any = True
        for f in feats:
            p = f.get("properties") or {}
            if not f.get("geometry"):
                continue
            area = _as_area(f["geometry"])
            if area is None or area.is_empty:
                continue
            am = transform(tm, area)
            if am.contains(aor_m):
                rel = "AoR inside"
            elif am.intersects(aor_m):
                rel = "overlaps the AoR"
            elif am.distance(aor_m) <= reach:
                rel = "nearby"
            else:
                continue
            name = p.get("fault_type") or p.get("Name") or p.get("comment") or ""
            row = {"area": kind, "name": str(name).strip(), "relation": rel,
                   "distance from the AoR (mi)": round(U.length_out(am.distance(aor_m), "mi"), 2),
                   "share of the AoR inside (%)": round(100 * am.intersection(aor_m).area
                                                        / aor_m.area, 1) if aor_m.area else 0.0}
            part.rows.append(row)
            part.features.append({"type": "Feature", "geometry": mapping(area),
                                  "properties": row})
    if got_any:
        part.status = "live"
        part.fetched = _dt.datetime.now(_dt.UTC).strftime("%Y-%m-%d %H:%M UTC")
    part.error = "; ".join(errors)
    order = {"AoR inside": 0, "overlaps the AoR": 1, "nearby": 2}
    part.rows.sort(key=lambda r: (order[r["relation"]], r["distance from the AoR (mi)"]))
    return part


# --------------------------------------------------------------------------
def near(aor_lonlat, distance_mi: float = 5.0, min_magnitude: float = 2.0,
         fetch=None) -> TexNetNear:
    """Everything TexNet publishes near the AoR, each part fetched on its own.

    With the default ``fetch`` the earthquake list and every map query are
    remembered for an hour; pass a function to fetch (or fake) them yourself."""
    eq_fetch = get_json if fetch is None else fetch
    map_fetch = cached_get_json if fetch is None else fetch
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=3) as pool:
        eq = pool.submit(earthquakes_near, aor_lonlat, distance_mi, min_magnitude, eq_fetch)
        wells = pool.submit(injection_wells_near, aor_lonlat, distance_mi, map_fetch)
        areas = pool.submit(seismic_areas_near, aor_lonlat, distance_mi, map_fetch)
        return TexNetNear(distance_mi=distance_mi, earthquakes=eq.result(),
                          wells=wells.result(), areas=areas.result())


__all__ = ["near", "earthquakes_near", "injection_wells_near", "seismic_areas_near",
           "statewide_earthquakes", "TexNetNear", "Part", "clear_cache", "get_json", "cached_get_json"]
