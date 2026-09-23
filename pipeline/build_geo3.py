"""Two polygon layers: dissolved regions for the top tier, ZCTAs for the second.

`geo` holds the 7 region shapes and `zipgeo` the 89 ZCTAs. Both go in the payload because the
map switches between them in place rather than refetching -- the whole file is offline.

Regions are dissolved from the ZCTAs directly, not from the area polygons, so a region's
outline cannot inherit a seam from the intermediate grouping. buffer(0) first: several TIGER
rings self-touch at the coastline and shapely's union turns that into an exception rather than
a polygon.
"""

import json
import sys

from shapely.geometry import mapping, shape
from shapely.ops import unary_union

sys.path.insert(0, "/tmp")
from areas import AREAS, REGIONS, check, check_regions  # noqa: E402

REGION_TOL = 0.0003     # ~33 m: regions are only ever seen at full extent
ZIP_TOL = 0.0002        # ~22 m: ZCTAs are seen zoomed into one region
PRECISION = 5


def rnd(g, nd=PRECISION):
    def walk(c):
        if isinstance(c[0], (int, float)):
            return [round(c[0], nd), round(c[1], nd)]
        return [walk(x) for x in c]
    return {"type": g["type"], "coordinates": walk(g["coordinates"])}


def clean(geoms, tol):
    merged = unary_union([g if g.is_valid else g.buffer(0) for g in geoms])
    merged = merged.simplify(tol, preserve_topology=True)
    if merged.geom_type == "MultiPolygon":
        keep = [p for p in merged.geoms if p.area > 1e-6]      # drop pinholes, keep islands
        if keep:
            merged = unary_union(keep)
    return merged


def main():
    check(); check_regions()
    wa = {f["properties"]["ZCTA5CE10"]: f
          for f in json.load(open("/tmp/wa_zips.json"))["features"]}
    payload = json.load(open("/tmp/map_payload.json"))

    regions = []
    for region, areas in REGIONS.items():
        zips = [z for a in areas for z in AREAS[a]]
        geoms = [shape(wa[z]["geometry"]) for z in zips if z in wa]
        regions.append({"type": "Feature",
                        "properties": {"zip": region, "n_zips": len(geoms)},
                        "geometry": rnd(mapping(clean(geoms, REGION_TOL)))})

    zipgeo = []
    for z, f in wa.items():
        if z not in {zz for aa in AREAS.values() for zz in aa}:
            continue
        zipgeo.append({"type": "Feature", "properties": {"zip": z},
                       "geometry": rnd(mapping(clean([shape(f["geometry"])], ZIP_TOL)))})

    payload["geo"] = {"type": "FeatureCollection", "features": regions}
    payload["zipgeo"] = {"type": "FeatureCollection", "features": zipgeo}
    json.dump(payload, open("/tmp/map_payload.json", "w"), separators=(",", ":"))
    print(f"regions: {len(regions)} shapes, "
          f"{len(json.dumps(payload['geo']))/1024:.0f} kB")
    print(f"zips   : {len(zipgeo)} shapes, "
          f"{len(json.dumps(payload['zipgeo']))/1024:.0f} kB")
    assert {f["properties"]["zip"] for f in regions} == set(REGIONS)
    have = {f["properties"]["zip"] for f in zipgeo}
    want = {z for aa in AREAS.values() for z in aa}
    assert have == want, sorted(want ^ have)
    print("every region and every ZIP has a polygon")


if __name__ == "__main__":
    main()
