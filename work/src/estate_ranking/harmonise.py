"""Point preparation, identities, coordinates and documented category joins."""
from collections import Counter, defaultdict
import html
import json
import re
import uuid

import numpy as np
import shapely
from pyproj import CRS, Transformer

from .ingest import read_csv, read_json
from .models import SpatialDataset, Table, identifier
from .validate import require


def display(value):
    if value is None:
        return None
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<br\s*/?>", " / ", str(value), flags=re.I))).strip() or None


class IdentityRegistry:
    """Stable IDs plus explicit aliases; changes remain in memory until publish."""

    def __init__(self, entries=None):
        self.entries = dict(entries or {})
        # Same ID is permitted only for explicitly recorded aliases.
        identities = {}
        for key, entry in self.entries.items():
            if not isinstance(entry, dict) or not entry.get("id"):
                raise ValueError("Malformed identity registry entry: " + key)
            if entry.get("alias_of"):
                target = self.entries.get(entry["alias_of"])
                if not target or target.get("alias_of") or target["id"] != entry["id"]:
                    raise ValueError("Invalid identity alias: " + key)
            elif entry["id"] in identities:
                raise ValueError("Identity registry collision: " + key)
            else:
                identities[entry["id"]] = key

    def get(self, namespace, key):
        if not key:
            raise ValueError("Missing identity key: " + namespace)
        full = namespace + ":" + key
        if full not in self.entries:
            value = namespace + ":" + uuid.uuid5(uuid.NAMESPACE_URL, full).hex
            if any(e["id"] == value for e in self.entries.values()):
                raise ValueError("Generated identity collision")
            self.entries[full] = {"id": value}
        return self.entries[full]["id"]

    def alias(self, namespace, new_key, old_key):
        full, old = namespace + ":" + new_key, namespace + ":" + old_key
        if full in self.entries or old not in self.entries or self.entries[old].get("alias_of"):
            raise ValueError("Alias must target an existing primary identity and use a new key")
        self.entries[full] = {"id": self.entries[old]["id"], "alias_of": old}


def spatial_rows(name, rows, source, geometry=None, types=None, metadata=None):
    md = dict(metadata or {}, source=source, source_count=len(rows))
    table = Table.from_rows(name, rows, types=types, metadata=md)
    ds = SpatialDataset(table.name, table.columns, table.types, table.masks, table.metadata)
    ds.crs = "EPSG:4326"
    if geometry is not None:
        ds.geometry = shapely.from_geojson(np.asarray([json.dumps(g) for g in geometry], dtype=object))
    else:
        ds.geometry = shapely.points(ds.columns["longitude"], ds.columns["latitude"])
    ds.check_contract()
    return ds


def to_common_crs(dataset, spec, config, report, target="EPSG:2326"):
    if not spec.get("crs") or not (spec.get("crs_evidence") or spec.get("crs_assumption")):
        raise ValueError("CRS lacks explicit evidence or assumption: " + dataset.name)
    source = spec["crs"]
    if not CRS(source).equals(CRS(dataset.crs)):
        raise ValueError("Configured CRS differs from source geometry representation")
    trans = Transformer.from_crs(source, target, always_xy=True)
    xs, ys = trans.transform(dataset.columns["longitude"].tolist(), dataset.columns["latitude"].tolist())
    xs, ys = np.asarray(xs), np.asarray(ys)
    dataset.geometry = shapely.points(xs, ys)
    dataset.crs = target
    dataset.add("easting", xs, "float64").add("northing", ys, "float64")
    reverse = Transformer.from_crs(target, source, always_xy=True)
    lon, lat = reverse.transform(xs.tolist(), ys.tolist())
    error = np.maximum(np.abs(lon - dataset.columns["longitude"]),
                       np.abs(lat - dataset.columns["latitude"]))
    for i in np.flatnonzero(error > config["validation"]["coordinate_roundtrip_deg"]):
        report.error("coordinate_roundtrip", dataset.name, "Conversion did not round-trip",
                     dataset.value("id", int(i)), {"error_deg": float(error[i])})
    report.checks[dataset.name + ":coordinate_roundtrip_max_deg"] = float(np.nanmax(error))
    dataset.metadata.update(source_crs=source, crs_evidence=spec.get("crs_evidence"),
                            crs_assumption=spec.get("crs_assumption"),
                            coordinate_fields_evidence=spec.get("coordinate_fields_evidence"),
                            location_height="unknown; Z not assigned")
    if "source_grid_easting" in dataset.columns:
        dx = xs - dataset.columns["source_grid_easting"]
        dy = ys - dataset.columns["source_grid_northing"]
        residual = np.hypot(dx, dy)
        dataset.add("source_grid_residual_m", residual, "float64")
        for i in np.flatnonzero(residual > config["validation"]["igeocom_residual_review_m"]):
            report.warning("coordinate_residual", dataset.name, "iGeoCom coordinate disagreement exceeds threshold",
                           dataset.value("id", int(i)), {"residual_m": float(residual[i])})
        report.checks[dataset.name + ":grid_residual_m"] = {
            "min": float(np.nanmin(residual)), "max": float(np.nanmax(residual)),
            "threshold": config["validation"]["igeocom_residual_review_m"]}
    return dataset


def load_estates(path, registry):
    raw = read_json(path)
    rows = []
    for i, r in enumerate(raw):
        require(r, ["Estate Name", "District Name", "Region Name", "Estate Map Latitude",
                    "Estate Map Longitude"], "estates row " + str(i))
        name = r["Estate Name"]
        require(name, ["en"], "estate name")
        rows.append(dict(id=registry.get("estate", name["en"]), source_id=None,
                         name=display(name["en"] or name.get("zh-Hant")), name_en=display(name["en"]),
                         name_zh_hant=display(name.get("zh-Hant")), name_zh_hans=display(name.get("zh-Hans")),
                         entity_type="estate", location_role="estate_map_point", entrance_evidence="unknown",
                         source_identity_name=name["en"], source_administrative_district=r["District Name"].get("en"),
                         source_region=r["Region Name"].get("en"), latitude=r["Estate Map Latitude"],
                         longitude=r["Estate Map Longitude"], block_count_raw=r.get("No. of Blocks"),
                         block_names_json=json.dumps(r.get("Name of Block(s)"), ensure_ascii=False),
                         raw_json=json.dumps(r, ensure_ascii=False), source_record=i,
                         provenance="estates:JSON array index {} (zero-based)".format(i)))
    return spatial_rows("estates", rows, "estates", types={"latitude": "float64", "longitude": "float64"})


def load_hospitals(path, registry, report):
    raw, rows = read_json(path), []
    for i, r in enumerate(raw):
        require(r, ["institution_eng", "latitude", "longitude", "with_AE_service_eng"], "hospital row " + str(i))
        ae = {"Yes": True, "No": False}.get(r["with_AE_service_eng"])
        if ae is None:
            report.warning("ae_value", "hospitals", "Unknown A&E value retained as null", r["institution_eng"])
        rows.append(dict(id=registry.get("hospital", r["institution_eng"]), source_id=None,
                         name=display(r["institution_eng"]), name_en=display(r["institution_eng"]),
                         name_zh_hant=display(r.get("institution_tc")), name_zh_hans=display(r.get("institution_sc")),
                         entity_type="hospital", location_role="institution_map_point", entrance_evidence="unknown",
                         cluster=r.get("cluster_eng"), address=display(r.get("address_eng")), has_ae=ae,
                         latitude=r["latitude"], longitude=r["longitude"],
                         raw_json=json.dumps(r, ensure_ascii=False), source_record=i,
                         provenance="hospitals:JSON array index {} (zero-based)".format(i)))
    return spatial_rows("hospitals", rows, "hospitals", types={"has_ae": "bool", "latitude": "float64", "longitude": "float64"})


def load_mtr_exits(path, name="mtr_exits"):
    collection = read_json(path)
    require(collection, ["type", "features"], name)
    if collection["type"] != "FeatureCollection":
        raise ValueError("Expected GeoJSON FeatureCollection")
    rows, geometries = [], []
    for i, feature in enumerate(collection["features"]):
        require(feature, ["properties", "geometry"], name + " row " + str(i))
        p, geom = feature["properties"], feature["geometry"]
        require(p, ["GEONAMEID", "ENGLISHNAME", "CHINESENAME", "EASTING", "NORTHING", "TYPE", "SUBCAT"], name)
        if geom["type"] != "Point" or len(geom["coordinates"]) != 2:
            raise ValueError("Expected 2D iGeoCom point")
        if p["TYPE"] != ("MTA" if name == "mtr_exits" else "RSN"):
            raise ValueError("Unexpected iGeoCom record type")
        row = dict(p)
        # SQLite/GeoPackage field names are case-insensitive. Separate source
        # grid attributes from normalised easting/northing rather than letting
        # EASTING and easting collide; raw_json retains original names exactly.
        row["source_grid_easting"] = row.pop("EASTING")
        row["source_grid_northing"] = row.pop("NORTHING")
        sid = identifier(p["GEONAMEID"])
        row.update(id="igeocom:" + sid, source_id=sid, name=display(p["ENGLISHNAME"] or p["CHINESENAME"]),
                   name_en=display(p["ENGLISHNAME"]), name_zh_hant=display(p["CHINESENAME"]), name_zh_hans=None,
                   entity_type="mtr_access" if name == "mtr_exits" else "railway_station",
                   location_role="access_record" if name == "mtr_exits" else "station_reference_point",
                   latitude=geom["coordinates"][1], longitude=geom["coordinates"][0],
                   raw_json=json.dumps(feature, ensure_ascii=False), provenance=name + ":GEONAMEID=" + sid)
        rows.append(row)
        geometries.append(geom)
    return spatial_rows(name, rows, name, geometries,
                        types={"source_grid_easting": "float64", "source_grid_northing": "float64", "latitude": "float64", "longitude": "float64"},
                        metadata={"source_field_names": {"source_grid_easting": "EASTING", "source_grid_northing": "NORTHING"}})


def load_bus_stops(path):
    rows = []
    for i, r in enumerate(read_json(path)):
        require(r, ["stop_id", "bus_stop", "bus_stop_zh", "latitude", "longitude", "operators", "GMB", "KMB", "CTB"], "bus_stops")
        if not isinstance(r["operators"], list) or not all(isinstance(op, str) for op in r["operators"]):
            raise ValueError("Malformed bus operator list")
        if any(type(r[k]) is not bool for k in ["GMB", "KMB", "CTB"]):
            raise ValueError("Bus operator flags must be true/false")
        sid = identifier(r["stop_id"])
        rows.append(dict(id="td_stop:" + sid, source_id=sid, name=display(r["bus_stop"] or r["bus_stop_zh"]),
                         name_en=display(r["bus_stop"]), name_zh_hant=display(r["bus_stop_zh"]), name_zh_hans=None,
                         entity_type="bus_stop", location_role="stop_map_point", boarding_accessibility="unknown",
                         latitude=r["latitude"], longitude=r["longitude"],
                         operators_json=json.dumps(r["operators"], ensure_ascii=False),
                         GMB=r["GMB"], KMB=r["KMB"], CTB=r["CTB"],
                         raw_json=json.dumps(r, ensure_ascii=False), provenance="bus_stops:stop_id=" + sid))
    return spatial_rows("bus_stops", rows, "bus_stops", types={
        "latitude": "float64", "longitude": "float64", "GMB": "bool", "KMB": "bool", "CTB": "bool"})


def assign_housing_districts(estates, path, config, report):
    raw = read_csv(path)
    lookup = defaultdict(list)
    for r in raw:
        require(r, ["estate_name", "housing_district", "source_administrative_district", "latitude", "longitude"], "housing_crosswalk")
        lookup[r["estate_name"]].append(r)
    categories, residuals = [], []
    transformer = Transformer.from_crs(4326, 2326, always_xy=True)
    permitted = {"Urban", "Extended Urban", "New Territories", "Islands"}
    for i in range(len(estates)):
        key = estates.value("source_identity_name", i)
        matches = lookup.get(key, [])
        if len(matches) != 1 or matches[0]["housing_district"] not in permitted:
            report.error("housing_district", "estates", "Missing/ambiguous allocation category", estates.value("id", i))
            categories.append(None)
            residuals.append(None)
            continue
        r = matches[0]
        x, y = transformer.transform(float(r["longitude"]), float(r["latitude"]))
        residual = float(np.hypot(x - estates.columns["easting"][i], y - estates.columns["northing"][i]))
        if residual > config["validation"]["crosswalk_coordinate_tolerance_m"]:
            report.error("crosswalk_coordinates", "estates", "Crosswalk coordinates differ from selected estate input",
                         estates.value("id", i), {"residual_m": residual})
        if r["source_administrative_district"] != estates.value("source_administrative_district", i):
            report.error("crosswalk_district", "estates", "Administrative district differs between source and crosswalk",
                         estates.value("id", i))
        categories.append(r["housing_district"])
        residuals.append(residual)
    estates.add("housing_district", categories).add("crosswalk_residual_m", residuals, "float64")
    estates.add("housing_district_provenance", ["housing_crosswalk:estate_name; see housing_documentation"] * len(estates))
    unused = set(lookup) - set(estates.columns["source_identity_name"])
    if unused:
        report.warning("crosswalk_unused", "housing_crosswalk", "Crosswalk has estates absent from current input", details=sorted(unused))
    counts = dict(Counter(categories))
    report.checks["housing_district_counts"] = counts
    if counts != config["validation"].get("expected_housing_counts", counts):
        report.warning("snapshot_counts", "estates", "Allocation counts differ from configured snapshot baseline", details=counts)
    report.warning("housing_boundary_proxies", "estates", "Town-area boundaries are geographic proxies, not HA-issued allocation polygons; assignments retain crosswalk provenance.")
    return Table.from_rows("housing_crosswalk", raw)


DOMAIN_FIELDS = {
    "Location": "dPedLocation", "FeatureType": "dPedFeatureType", "CrossingFeature": "dPedCrossingFeature",
    "WeatherProof": "dPedCover", "WheelchairBarrier": "dPedWheelchairBarrier", "WheelchairAccess": "dPedWheelchairAccess",
    "ObstaclesType": "dObstaclesType", "Direction": "dDirection", "PositionCertainty": "dPedPositionCertainty",
    "Enabled": "dPedEnabled", "DataSource": "dPedDataSource", "LevelSource": "dPedLevelSource"}


def decode_network(network, domains, report):
    for field, domain_name in DOMAIN_FIELDS.items():
        values = domains[domain_name]["values"]
        observed = set(network.columns[field][~network.masks[field]].tolist())
        unknown = [identifier(v) for v in observed if identifier(v) not in values]
        if unknown:
            report.warning("domain_code", "network", "Unknown codes retained for " + field, details=sorted(unknown))
        network.add(field + "_label", [None if missing else values.get(identifier(v))
                    for v, missing in zip(network.columns[field], network.masks[field])])
    for field in ["WheelchairBarrier", "WheelchairAccess", "Enabled", "PositionCertainty"]:
        codes = network.columns[field]
        true_code, false_code = (1, 0) if field == "PositionCertainty" else (1, 2)
        unknown = network.masks[field] | ~np.isin(codes, [true_code, false_code])
        network.add(field + "_bool", codes == true_code, "bool", unknown)
    report.warning("gradient_direction_and_aggregation", "network",
                   "Provider confirms Gradient in radians and Shape_Length as horizontal metres. Gradient sign convention and within-path aggregation are not explicitly documented; derive directional slope from ordered Z coordinates or confirm a policy before directed route costs.")


def reconcile_bus(stops, bus_path, gmb_path, report):
    grouped, route_rows = {}, []
    for source, path in [("raw_bus", bus_path), ("raw_gmb", gmb_path)]:
        raw = read_json(path)
        require(raw, ["features"], source)
        for index, feature in enumerate(raw["features"]):
            p, geom = feature["properties"], feature["geometry"]
            require(p, ["stopId", "companyCode", "stopPickDrop", "routeId", "routeSeq", "stopSeq", "serviceMode", "lastUpdateDate"], source)
            if geom["type"] != "Point" or len(geom["coordinates"]) != 2:
                raise ValueError("Unexpected raw stop geometry")
            sid = identifier(p["stopId"])
            coords = tuple(geom["coordinates"])
            entry = grouped.setdefault(sid, {"coordinates": set(), "operators": set(), "names_en": set(), "names_zh": set()})
            entry["coordinates"].add(coords)
            entry["operators"].update(p["companyCode"].split("+"))
            entry["names_en"].add(p.get("stopNameE", ""))
            entry["names_zh"].add(p.get("stopNameC", ""))
            # Original properties/geometry are lossless and exact service codes remain uninterpreted.
            row = {k: p[k] for k in ["stopPickDrop", "routeId", "routeSeq", "stopSeq", "serviceMode", "lastUpdateDate", "companyCode"]}
            row.update(stop_id=sid, source=source, source_record=index,
                       raw_json=json.dumps(feature, ensure_ascii=False))
            route_rows.append(row)
    listed = set(stops.columns["source_id"])
    for sid in sorted(listed ^ set(grouped)):
        report.error("bus_ids", "bus_stops", "Stop ID missing from raw union or prepared list", sid)
    variants = []
    for i in range(len(stops)):
        sid = stops.value("source_id", i)
        if sid not in grouped:
            continue
        raw = grouped[sid]
        if len(raw["coordinates"]) != 1 or (stops.value("longitude", i), stops.value("latitude", i)) not in raw["coordinates"]:
            report.error("bus_coordinates", "bus_stops", "Conflicting raw/prepared stop coordinates", sid,
                         {"raw_coordinates": sorted(raw["coordinates"])})
        if set(json.loads(stops.value("operators_json", i))) != raw["operators"]:
            report.error("bus_operators", "bus_stops", "Operator memberships differ from raw union", sid)
        for op in ["GMB", "KMB", "CTB"]:
            if stops.value(op, i) != (op in raw["operators"]):
                report.error("bus_flag", "bus_stops", "Operator flag differs from raw union: " + op, sid)
        if len(raw["names_en"]) > 1 or len(raw["names_zh"]) > 1:
            variants.append({"stop_id": sid, "names_en_json": json.dumps(sorted(raw["names_en"]), ensure_ascii=False),
                             "names_zh_json": json.dumps(sorted(raw["names_zh"]), ensure_ascii=False)})
    report.checks["bus_reconciliation"] = {"raw_route_records": len(route_rows), "distinct_raw_stop_ids": len(grouped),
                                           "prepared_stop_ids": len(listed), "naming_variant_stops": len(variants)}
    report.warning("bus_boarding", "bus_stops", "Operator flags do not establish wheelchair boarding access; pickup/drop-off codes are retained without undocumented interpretation.")
    return [Table.from_rows("bus_route_stop_records", route_rows),
            Table.from_rows("bus_name_variants", variants, types={"stop_id": "string", "names_en_json": "string", "names_zh_json": "string"})]
