"""Public Texas fault and seismicity layers, and the faults near an AoR.

The layers are built by ``scripts/build_fault_layers.py`` into ``app/layers``
(GeoJSON in WGS84 plus a manifest, layers.json, with each layer's source,
citation, licence, scale and kind) and ship with the app, so nothing is fetched
at run time: computers on locked-down networks may not reach the web services.

Mapped faults are context for a reviewer, not a model input. Most are surface
traces or regional trends, not fault planes at injection depth; the
application's own fault interpretation, entered as sealing faults, is what the
model uses. :func:`near_aor` lists every mapped fault that crosses the AoR or
lies within a chosen distance of it, so a reviewer can ask whether the
application accounts for it.
"""

from __future__ import annotations

import json
import os
import sys
from functools import lru_cache

import numpy as np

from . import units as U


def layers_dir() -> str | None:
    """Where app/layers is, in a source checkout or an installed build."""
    here = os.path.dirname(os.path.abspath(__file__))
    cands = [os.environ.get("CONTAINMENT_LAYERS", ""),
             os.path.join(here, "..", "..", "app", "layers"),          # source checkout
             os.path.join(os.path.dirname(sys.executable), "app", "layers"),   # Windows build
             os.path.join(getattr(sys, "_MEIPASS", ""), "..", "app", "layers"),
             os.path.join(os.getcwd(), "app", "layers")]
    for c in cands:
        if c and os.path.exists(os.path.join(c, "layers.json")):
            return os.path.abspath(c)
    return None


@lru_cache(maxsize=1)
def manifest() -> tuple:
    d = layers_dir()
    if not d:
        return ()
    with open(os.path.join(d, "layers.json"), encoding="utf-8") as fh:
        return tuple(json.load(fh))


@lru_cache(maxsize=8)
def _load(layer_id: str) -> tuple:
    """(geometries, properties) of one layer, in lon/lat."""
    from shapely.geometry import shape

    d = layers_dir()
    with open(os.path.join(d, layer_id + ".geojson"), encoding="utf-8") as fh:
        fc = json.load(fh)
    geoms, props = [], []
    for f in fc["features"]:
        try:
            geoms.append(shape(f["geometry"]))
            props.append(f.get("properties") or {})
        except Exception:                       # a malformed feature is skipped
            continue
    return tuple(geoms), tuple(props)


def clip(layer_id: str, bounds_lonlat: tuple[float, float, float, float]) -> dict:
    """A layer's features inside a lon/lat box, as a GeoJSON FeatureCollection."""
    from shapely.geometry import box, mapping

    win = box(*bounds_lonlat)
    geoms, props = _load(layer_id)
    feats = [{"type": "Feature", "geometry": mapping(g), "properties": p}
             for g, p in zip(geoms, props, strict=True) if g.intersects(win)]
    return {"type": "FeatureCollection", "features": feats}


def _label(layer: dict, p: dict) -> str:
    bits = [p.get("name") or p.get("fault_name") or p.get("zone") or "",
            p.get("type") or p.get("fault_type") or "",
            p.get("set") if layer["id"] == "permian_basement_faults" else ""]
    return ", ".join(b for b in bits if b) or "unnamed"


def near_aor(aor_lonlat, distance_mi: float = 1.0, layer_ids=None) -> list[dict]:
    """Mapped faults that cross the AoR or lie within ``distance_mi`` of it.

    ``aor_lonlat`` is the AoR polygon in lon/lat. Distances are measured in a
    local transverse Mercator projection centred on the AoR. Earthquakes are
    counted separately (see :func:`earthquakes_near`)."""
    import pyproj
    from shapely.ops import transform

    if aor_lonlat is None or aor_lonlat.is_empty:
        return []
    c = aor_lonlat.centroid
    tm = pyproj.Transformer.from_crs(
        4326, pyproj.CRS.from_proj4(f"+proj=tmerc +lat_0={c.y} +lon_0={c.x} +k=1 +x_0=0 "
                                    "+y_0=0 +ellps=GRS80 +units=m"), always_xy=True).transform
    aor_m = transform(tm, aor_lonlat)
    reach = U.length(distance_mi, "mi")
    pad = (reach / 80000.0) + 0.05                       # degrees, generous
    x0, y0, x1, y1 = aor_lonlat.bounds
    win = (x0 - pad, y0 - pad, x1 + pad, y1 + pad)
    rows = []
    for layer in manifest():
        if layer["kind"] == "seismicity" or (layer_ids and layer["id"] not in layer_ids):
            continue
        for g, p in zip(*_load(layer["id"]), strict=True):
            gx0, gy0, gx1, gy1 = g.bounds
            if gx1 < win[0] or gx0 > win[2] or gy1 < win[1] or gy0 > win[3]:
                continue
            gm = transform(tm, g)
            if gm.is_empty:
                continue
            dist = aor_m.distance(gm)
            if not np.isfinite(dist) or dist > reach:
                continue
            inside = aor_m.intersection(gm).length
            rows.append({
                "layer": layer["title"], "kind": layer["kind"], "fault": _label(layer, p),
                "crosses the AoR": "yes" if inside > 0 else "no",
                "length inside the AoR (ft)": round(U.length_out(inside, "ft")),
                "distance from the AoR (ft)": round(U.length_out(dist, "ft")),
                "confidence": p.get("confidence", ""), "dip": p.get("dip", ""),
            })
    rows.sort(key=lambda r: (r["crosses the AoR"] != "yes", r["distance from the AoR (ft)"]))
    return rows


def earthquakes_near(aor_lonlat, distance_mi: float = 5.0) -> dict:
    """Count and largest magnitude of TexNet earthquakes within a distance of the AoR."""
    import pyproj
    from shapely.ops import transform

    if aor_lonlat is None or aor_lonlat.is_empty or not any(
            m["id"] == "texnet_earthquakes" for m in manifest()):
        return {}
    c = aor_lonlat.centroid
    tm = pyproj.Transformer.from_crs(
        4326, pyproj.CRS.from_proj4(f"+proj=tmerc +lat_0={c.y} +lon_0={c.x} +k=1 +ellps=GRS80 "
                                    "+units=m"), always_xy=True).transform
    zone = transform(tm, aor_lonlat).buffer(U.length(distance_mi, "mi"))
    mags = []
    for g, p in zip(*_load("texnet_earthquakes"), strict=True):
        if abs(g.x - c.x) > 1.5 or abs(g.y - c.y) > 1.5:
            continue
        x, y = tm(g.x, g.y)
        if zone.contains(__import__("shapely.geometry", fromlist=["Point"]).Point(x, y)):
            mags.append(float(p.get("mag") or 0))
    return {"count": len(mags), "max_magnitude": max(mags) if mags else None,
            "distance_mi": distance_mi}


__all__ = ["layers_dir", "manifest", "clip", "near_aor", "earthquakes_near", "as_model_faults"]


def as_model_faults(aor_lonlat, distance_mi: float = 1.0, multiplier: float = 0.0,
                    layer_ids=None) -> list[dict]:
    """Mapped faults near the AoR as project ``faults:`` entries (lat/lon traces).

    For a sensitivity test only: a mapped trace is not the fault at injection
    depth, and whether it seals is a property of the fault, not of the map.
    ``multiplier`` is the transmissibility multiplier across it (0 sealing,
    1 open)."""
    if aor_lonlat is None or aor_lonlat.is_empty:
        return []
    near = {(r["layer"], r["fault"]) for r in near_aor(aor_lonlat, distance_mi, layer_ids)}
    pad = distance_mi / 60.0 + 0.05
    x0, y0, x1, y1 = aor_lonlat.bounds
    out = []
    for layer in manifest():
        if layer["kind"] == "seismicity" or (layer_ids and layer["id"] not in layer_ids):
            continue
        for g, p in zip(*_load(layer["id"]), strict=True):
            if (layer["title"], _label(layer, p)) not in near:
                continue
            gx0, gy0, gx1, gy1 = g.bounds
            if gx1 < x0 - pad or gx0 > x1 + pad or gy1 < y0 - pad or gy0 > y1 + pad:
                continue
            for part in (g.geoms if hasattr(g, "geoms") else [g]):
                coords = list(part.coords)
                if len(coords) >= 2:
                    out.append({"name": f"{_label(layer, p)} [{layer['id']}]",
                                "multiplier": float(multiplier),
                                "latlon": [[round(lat, 6), round(lon, 6)] for lon, lat in coords]})
    return out
