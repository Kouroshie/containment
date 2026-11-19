"""Download the public Texas fault and seismicity layers and write them for the app.

    py scripts/build_fault_layers.py [download_folder]

Writes app/layers/<name>.geojson (WGS84 lon/lat, simplified about 30 m, 5
decimals) and app/layers/layers.json, the manifest the GIS map and the
fault screen read: title, source, citation, licence, scale, kind (surface or
subsurface) and drawing style. Every dataset is public domain or CC0. Run it
when a source publishes a new version, then rebuild the app.
"""

from __future__ import annotations

import csv
import io
import json
import os
import ssl
import sys
import urllib.parse
import urllib.request
import zipfile

import pyproj
import shapefile
from shapely.geometry import mapping, shape
from shapely.ops import transform

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "app", "layers")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124"}
TOL = 0.0003            # degrees, about 30 m: well under the 1:250,000 map accuracy
TEXAS = (-107.0, 25.5, -93.4, 36.6)

F250 = ("https://feature.geographic.texas.gov/arcgis/rest/services/Geologic_Database/"
        "GeologicDatabaseofTexas_250k/MapServer/3")
F250_TYPES = {1: "Unspecified fault", 2: "Normal fault", 3: "Inferred normal fault",
              4: "Concealed normal fault", 5: "Thrust fault", 6: "Transverse fault",
              7: "Transverse fault"}                   # 8 and up are fold axes, not faults
QFAULTS = "https://earthquake.usgs.gov/arcgis/rest/services/haz/Qfaults/MapServer/15"
SCIENCEBASE = {"gcfaultsg": "60abc3f9d34ea221ce51e45f", "gcfltzoneg": "60abc40ed34ea221ce51e46d"}
DATAVERSE = "https://dataverse.tdl.org/api/access/datafile/"
PERMIAN = {"Delaware Basin and Central Basin Platform (Horne et al. 2022, v4)": 253771,
           "Midland Basin (Horne et al. 2023, v1)": 296118,
           "Greater Permian Basin regional (Horne 2023, v1.0)": 296116}
TEXNET = ("https://catalog.texnet.beg.utexas.edu/api/earthquake/DownloadCsv?"
          "minMagnitude=2&start=2017-01-01&end={end}")


def _ssl_context():
    """Verify certificates against certifi's bundle when it is installed.

    The Windows certificate store can lag behind a server's new issuer (TexNet's
    catalog moved to an InCommon / emSign chain in Nov 2026 and failed with
    CERTIFICATE_VERIFY_FAILED); certifi carries current roots. Verification
    stays on either way.
    """
    try:
        import certifi
    except ImportError:
        return ssl.create_default_context()
    return ssl.create_default_context(cafile=certifi.where())


_SSL = _ssl_context()


def _get(url, timeout=180):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout,
                                  context=_SSL).read()


def _rest_geojson(base, extra):
    feats, off = [], 0
    while True:
        q = urllib.parse.urlencode({"where": "1=1", "outFields": "*", "outSR": 4326, "f": "geojson",
                                    "resultOffset": off, "resultRecordCount": 2000, **extra})
        fs = json.loads(_get(base + "/query?" + q)).get("features", [])
        feats += fs
        off += len(fs)
        if len(fs) < 2000:
            return feats


def _clean(geom):
    g = geom.simplify(TOL, preserve_topology=False)
    return json.loads(json.dumps(mapping(g)), parse_float=lambda v: round(float(v), 5))


def _write(name, features):
    path = os.path.join(OUT, name + ".geojson")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"type": "FeatureCollection", "features": features}, fh, separators=(",", ":"))
    return os.path.getsize(path)


def _shp_features(reader, to_wgs, props_of):
    out = []
    for sr in reader.iterShapeRecords():
        if not sr.shape.points:
            continue
        g = shape(sr.shape.__geo_interface__)
        if to_wgs is not None:
            g = transform(to_wgs, g)
        out.append({"type": "Feature", "geometry": _clean(g),
                    "properties": props_of(sr.record.as_dict())})
    return out


def _layer_tx_faults_250k(raw):
    """Geologic Database of Texas, faults."""
    feats = []
    for f in _rest_geojson(F250, {"orderByFields": "OBJECTID"}):
        code = int(f["properties"].get("fault_cd") or 0)
        if code in F250_TYPES and f.get("geometry"):
            feats.append({"type": "Feature", "geometry": _clean(shape(f["geometry"])),
                          "properties": {"type": F250_TYPES[code],
                                         "sheet": f["properties"].get("beg_origin_cd")}})
    size = _write("tx_faults_250k", feats)
    return {
        "id": "tx_faults_250k", "title": "Texas surface faults (Geologic Database of Texas, 1:250,000)",
        "kind": "surface", "count": len(feats), "bytes": size, "colour": "#d62728", "weight": 1.6,
        "dash": None, "show": True,
        "source": "USGS, TxGIO (TNRIS), BEG and TWDB (2007). Geologic Database of Texas, Fault250K "
                  "layer, from the BEG Geologic Atlas of Texas sheets",
        "url": F250, "licence": "CC0",
        "note": "Faults mapped at the ground surface at 1:250,000 (locations good to about 100 to "
                "250 m). A surface trace says where a fault reaches the surface, not where it is "
                "at injection depth."}


def _layer_gulf_coast_faults(raw):
    """USGS Gulf Coast faults and fault zones."""
    gc = []
    for name, item in SCIENCEBASE.items():
        d = json.loads(_get(f"https://www.sciencebase.gov/catalog/item/{item}?format=json&fields=facets"))
        for fac in d["facets"]:
            for f in fac["files"]:
                if f["name"].rsplit(".", 1)[-1].lower() in ("shp", "shx", "dbf", "prj"):
                    with open(os.path.join(raw, f["name"]), "wb") as fh:
                        fh.write(_get(f["downloadUri"]))
        r = shapefile.Reader(os.path.join(raw, name))
        gc += _shp_features(r, None, lambda rec, n=name: {
            "type": rec.get("NEWFIELD1") or "", "zone": rec.get("FAULT_ZONE") or "",
            "set": "fault zones" if n == "gcfltzoneg" else "faults"})
    gc = [f for f in gc if shape(f["geometry"]).intersects(
        shape({"type": "Polygon", "coordinates": [[(TEXAS[0], TEXAS[1]), (TEXAS[2], TEXAS[1]),
                                                     (TEXAS[2], TEXAS[3]), (TEXAS[0], TEXAS[3]),
                                                     (TEXAS[0], TEXAS[1])]]}))]
    size = _write("gulf_coast_faults", gc)
    return {
        "id": "gulf_coast_faults", "title": "Gulf Coast regional faults and fault zones (USGS, after Ewing and Lopez 1991)",
        "kind": "subsurface", "count": len(gc), "bytes": size, "colour": "#9467bd", "weight": 2.0,
        "dash": "8 4", "show": True,
        "source": "USGS (2004). Faults in the Gulf Coast [gcfaultsg] and Fault Zones in the Gulf "
                  "Coast [gcfltzoneg], digitised from Ewing, T.E. and Lopez, R.F. (1991), "
                  "Principal structural features, Gulf of Mexico basin, GSA DNAG Plate 2",
        "url": "https://www.sciencebase.gov/catalog/item/" + SCIENCEBASE["gcfaultsg"],
        "licence": "public domain (USGS; no use constraints)",
        "note": "Regional, schematic trends of growth faults and fault zones at depth (Balcones, "
                "Luling, Mexia, Talco, Frio, Vicksburg, Yegua, Miocene). A trend line, not a "
                "located fault plane at a given depth."}


def _layer_permian_basement_faults(raw):
    """BEG Permian basement-rooted faults."""
    perm = []
    for label, fid in PERMIAN.items():
        data = _get(DATAVERSE + str(fid))
        if not zipfile.is_zipfile(io.BytesIO(data)):
            raise RuntimeError(f"Texas Data Repository file {fid} came back as a web page, not a "
                               "zip (the site is blocking scripted downloads or the file moved)")
        z = zipfile.ZipFile(io.BytesIO(data))
        shp = [n for n in z.namelist() if n.lower().endswith(".shp")][0]
        folder = os.path.join(raw, str(fid))
        z.extractall(folder)
        base = os.path.join(folder, shp[:-4])
        crs = pyproj.CRS.from_wkt(open(base + ".prj", encoding="utf-8", errors="replace").read())
        fwd = pyproj.Transformer.from_crs(crs, 4326, always_xy=True).transform
        # file names like "Horne et al.2022_..." confuse the reader's path logic
        r = shapefile.Reader(shp=open(base + ".shp", "rb"), shx=open(base + ".shx", "rb"),
                             dbf=open(base + ".dbf", "rb"), encoding="latin-1")

        def props(rec, label=label):
            keep = {}
            for k in ("Name", "Confidence", "dip", "Fault_Type", "Horizon", "Source"):
                v = rec.get(k)
                if v not in (None, "") and str(v).strip():
                    keep[k.lower()] = round(v, 1) if isinstance(v, float) else str(v)
            keep["set"] = label
            return keep
        perm += _shp_features(r, fwd, props)
    size = _write("permian_basement_faults", perm)
    return {
        "id": "permian_basement_faults", "title": "Permian Basin basement-rooted faults (BEG, Horne et al.)",
        "kind": "subsurface", "count": len(perm), "bytes": size, "colour": "#ff7f0e", "weight": 2.0,
        "dash": None, "show": True,
        "source": "Horne, E.A. et al. (2021, 2022) Basement-rooted faults of the Delaware Basin and "
                  "Central Basin Platform, v4, doi:10.18738/T8/UHOUX8; Horne et al. (2023) Midland "
                  "Basin faults and Greater Permian Basin regional v1.0, doi:10.18738/T8/ZTBOGP. "
                  "Bureau of Economic Geology / TexNet, Texas Data Repository",
        "url": "https://doi.org/10.18738/T8/UHOUX8", "licence": "CC0",
        "note": "Faults interpreted from 3-D and 2-D seismic and well data at basement and "
                "Ellenburger level, with confidence and dip where given. The most relevant public "
                "map for deep Permian injection; still an interpretation at regional scale."}


def _layer_quaternary_faults(raw):
    """USGS Quaternary faults (Texas)."""
    q = _rest_geojson(QFAULTS, {"geometry": ",".join(map(str, TEXAS)),
                                "geometryType": "esriGeometryEnvelope", "inSR": 4326,
                                "spatialRel": "esriSpatialRelIntersects"})
    qf = [{"type": "Feature", "geometry": _clean(shape(f["geometry"])),
           "properties": {k: f["properties"].get(k) for k in
                          ("fault_name", "section_name", "age", "slip_rate", "slip_sense")
                          if f["properties"].get(k)}}
          for f in q if f.get("geometry")]
    size = _write("quaternary_faults", qf)
    return {
        "id": "quaternary_faults", "title": "Quaternary (young) faults (USGS Quaternary Fault and Fold Database)",
        "kind": "surface", "count": len(qf), "bytes": size, "colour": "#8c564b", "weight": 2.2,
        "dash": None, "show": False,
        "source": "U.S. Geological Survey and Texas Bureau of Economic Geology, Quaternary fault "
                  "and fold database of the United States",
        "url": QFAULTS, "licence": "public domain (USGS)",
        "note": "Faults with evidence of movement in the last 1.6 million years. In Texas these "
                "are in the Trans-Pecos only."}


def _layer_texnet_earthquakes(raw):
    """TexNet earthquakes (context)."""
    import datetime as _dt
    rows = list(csv.DictReader(io.StringIO(_get(TEXNET.format(end=_dt.date.today().isoformat()))
                                           .decode("utf-8", "replace"))))
    eq = []
    for r in rows:
        try:
            lat, lon = float(r["Latitude (WGS84)"]), float(r["Longitude (WGS84)"])
            mag = float(r["Local Magnitude"] or r["Moment Magnitude"] or 0)
        except (KeyError, ValueError):
            continue
        eq.append({"type": "Feature", "geometry": {"type": "Point",
                                                   "coordinates": [round(lon, 4), round(lat, 4)]},
                   "properties": {"id": r.get("EventID"), "date": r.get("Origin Date"), "mag": mag,
                                  "depth_km": r.get("Depth of Hypocenter (Km. Rel to Ground Surface)")}})
    size = _write("texnet_earthquakes", eq)
    return {
        "id": "texnet_earthquakes", "title": "TexNet earthquakes, magnitude 2 and above, 2017 on",
        "kind": "seismicity", "count": len(eq), "bytes": size, "colour": "#17becf", "weight": 1,
        "dash": None, "show": False,
        "snapshot": _dt.date.today().isoformat(),
        "source": "TexNet Seismic Monitoring Program, Bureau of Economic Geology, earthquake catalog",
        "url": "https://catalog.texnet.beg.utexas.edu", "licence": "public catalog; cite TexNet",
        "note": "A snapshot taken when this build was made. Earthquakes can mark active faults "
                "that no map shows."}


LAYERS = (_layer_tx_faults_250k, _layer_gulf_coast_faults, _layer_permian_basement_faults,
          _layer_quaternary_faults, _layer_texnet_earthquakes)


def main(raw):
    """Rebuild every layer; a source that fails keeps its previous file and manifest entry."""
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(raw, exist_ok=True)
    try:
        with open(os.path.join(OUT, "layers.json"), encoding="utf-8") as fh:
            old = {m["id"]: m for m in json.load(fh)}
    except (OSError, ValueError):
        old = {}
    manifest, failed = [], []
    for build in LAYERS:
        lid = build.__name__[len("_layer_"):]
        try:
            manifest.append(build(raw))
        except Exception as e:  # noqa: BLE001  any download or parse failure
            if lid not in old or not os.path.exists(os.path.join(OUT, lid + ".geojson")):
                raise
            failed.append(lid)
            manifest.append(old[lid])
            print(f"WARNING {lid}: {type(e).__name__}: {e}. Kept the previous copy "
                  f"(snapshot {old[lid].get('snapshot', 'earlier build')}).")

    with open(os.path.join(OUT, "layers.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=1)
    for m in manifest:
        print(f"{m['id']:26s} {m['count']:6d} features {m['bytes'] / 1e6:6.2f} MB"
              + ("  (kept previous copy)" if m['id'] in failed else ""))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(REPO, ".fault_downloads"))
