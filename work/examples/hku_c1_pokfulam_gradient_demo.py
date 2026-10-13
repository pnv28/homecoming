"""Five road-side endpoint samples near HKU C1, oriented toward Queen Mary.

A local endpoint graph orders samples only; this is not the production routing
or a wheelchair-accessibility certificate. Original provider angles are kept.
"""
from collections import defaultdict
import csv
import heapq
import json
from pathlib import Path
import sys

import numpy as np
import pyogrio.raw
import shapely
from pyproj import Transformer

WORK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORK / "src"))
from estate_ranking.ingest import sha256


def main():
    def read(name):
        return json.loads((WORK / "data" / name).read_text(encoding="utf-8-sig"))
    exit_feature = next(f for f in read("mtr_access_points.geojson")["features"]
                        if f["properties"]["GEONAMEID"] == 559800)
    hospital = next(r for r in read("facility-hosp.json")
                    if r["institution_eng"] == "Queen Mary Hospital")
    to_grid = Transformer.from_crs(4326, 2326, always_xy=True)
    to_lonlat = Transformer.from_crs(2326, 4326, always_xy=True)
    cx, cy = to_grid.transform(*exit_feature["geometry"]["coordinates"])
    qx, qy = to_grid.transform(hospital["longitude"], hospital["latitude"])
    archive = WORK / "data/3D_Pedestrian_Network_FGDB.zip"
    # This cache was extracted from the selected source archive by Step 1.
    digest = sha256(archive)
    cache = WORK / "cache" / ("network_" + digest[:16])
    extraction = json.loads((cache / "extraction_manifest.json").read_text())
    assert extraction["archive_sha256"] == digest
    gdb = cache / extraction["gdb"]
    fields = ["PedestrianRouteID", "FeatureType", "WheelchairBarrier", "Gradient",
              "StreetNameEN", "AliasNameEN", "Enabled", "Shape_Length"]
    meta, _, wkb, arrays = pyogrio.raw.read(
        gdb, layer="PedestrianRoute", columns=fields,
        bbox=(min(cx, qx)-600, min(cy, qy)-400, max(cx, qx)+650, max(cy, qy)+350))
    geometries = shapely.from_wkb(wkb)
    data = dict(zip(meta["fields"], arrays))
    adjacency = defaultdict(list)
    def key(coords):
        # Source grid/height values have four decimal places; rounding avoids
        # floating representation differences at matching source endpoints.
        return tuple(round(float(v), 4) for v in coords)
    for i, geometry in enumerate(geometries):
        if data["FeatureType"][i] in {8, 12, 13, 16, 20, 21} or data["Enabled"][i] != 1:
            continue
        if shapely.get_num_geometries(geometry) != 1:
            raise ValueError("Multipart local link requires explicit handling")
        coords = shapely.get_coordinates(geometry, include_z=True)
        start, end = key(coords[0]), key(coords[-1])
        length = float(data["Shape_Length"][i])
        adjacency[start].append((end, length, i))
        adjacency[end].append((start, length, i))
    start = min(adjacency, key=lambda p: (p[0]-cx)**2 + (p[1]-cy)**2)
    target = min(adjacency, key=lambda p: (p[0]-qx)**2 + (p[1]-qy)**2)
    queue, distances, previous = [(0.0, start)], {start: 0.0}, {}
    while queue:
        distance, node = heapq.heappop(queue)
        if distance != distances[node]:
            continue
        if node == target:
            break
        for neighbour, length, index in adjacency[node]:
            candidate = distance + length
            if candidate < distances.get(neighbour, float("inf")):
                distances[neighbour] = candidate
                previous[neighbour] = (node, index)
                heapq.heappush(queue, (candidate, neighbour))
    if target not in distances:
        raise ValueError("Cannot establish local ordering toward the hospital map point")
    ordered, current = [], target
    while current != start:
        prior, index = previous[current]
        ordered.append((prior, current, index))
        current = prior
    ordered.reverse()
    first_road = next(j for j, (_, _, i) in enumerate(ordered)
                      if str(data["StreetNameEN"][i]).casefold() == "pok fu lam road")
    sample = ordered[first_road:first_road+4]
    assert len(sample) == 4 and all(a[1] == b[0] for a, b in zip(sample, sample[1:]))
    coordinates = [sample[0][0]] + [end for _, end, _ in sample]
    points = []
    for number, (x, y, z) in enumerate(coordinates, 1):
        longitude, latitude = to_lonlat.transform(x, y)
        points.append(dict(point="P"+str(number), longitude=longitude, latitude=latitude,
                           easting=x, northing=y, height_hkpd_m=z))
    segments = []
    for j, (a, b, i) in enumerate(sample, 1):
        delta = round(b[2]-a[2], 4)
        angle = float(data["Gradient"][i])
        classification = "uphill" if delta > 0 else "downhill" if delta < 0 else "level"
        signed = angle if delta > 0 else -angle if delta < 0 else None
        segments.append(dict(from_point="P"+str(j), to_point="P"+str(j+1),
                             pedestrian_route_id=int(data["PedestrianRouteID"][i]),
                             height_change_m=delta, classification=classification,
                             supplied_gradient_rad=angle, signed_gradient_rad=signed,
                             horizontal_length_m=float(data["Shape_Length"][i]),
                             feature_type=int(data["FeatureType"][i]),
                             wheelchair_barrier=int(data["WheelchairBarrier"][i]),
                             street_name=data["StreetNameEN"][i], alias=data["AliasNameEN"][i]))
    result = dict(description="First five road-side endpoint points near HKU C1 along a local candidate directed toward Queen Mary; five points give four intervals",
        sources={name: {"path": "work/data/"+name, "sha256": sha256(WORK/"data"/name)} for name in [
            "mtr_access_points.geojson", "facility-hosp.json", "3D_Pedestrian_Network_FGDB.zip", "3DPN_DataDictionary_v2.2.pdf", "data_dictionary_v5.pdf"]},
        network_layer="PedestrianRoute", exit_geonameid=559800,
        exit_coordinates=exit_feature["geometry"]["coordinates"], hospital_coordinates=[hospital["longitude"], hospital["latitude"]],
        first_sample_distance_from_exit_map_point_m=float(np.hypot(coordinates[0][0]-cx,coordinates[0][1]-cy)),
        policy="Raw gradient magnitude unchanged; sign from endpoint height change; equal endpoint heights classified level with sign unassigned; positive source gradient is not overwritten",
        limitations=["Samples are just outside C1, not an invented height for the 2D exit point",
                     "This checks stored slope signs, not wheelchair route usability; barrier flags remain visible",
                     "Very small height changes are not precise physical slope evidence; provider vertical accuracy is +/-2 metres",
                     "Intermediate vertices are preserved in the source; this table compares consecutive source-link endpoints"],
        points=points, segments=segments)
    output = WORK / "precomputed/docs"
    output.mkdir(parents=True, exist_ok=True)
    (output/"hku_c1_pokfulam_gradient_sample.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    for name, rows in [("points",points),("segments",segments)]:
        with (output/("hku_c1_pokfulam_gradient_"+name+".csv")).open("w",newline="",encoding="utf-8") as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__ == "__main__":
    main()
