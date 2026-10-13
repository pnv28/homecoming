"""Lossless staged outputs, full read-back checks, and atomic current-run selection."""
from collections import OrderedDict
import csv
import json
import os
from pathlib import Path
import sqlite3
import uuid

import numpy as np
import pyogrio
import pyogrio.raw
import shapely
from pyproj import CRS

from .models import SpatialDataset


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def quote(name):
    return '"' + name.replace('"', '""') + '"'


SQL_TYPES = {"int16": "INTEGER", "int32": "INTEGER", "int64": "INTEGER",
             "float64": "REAL", "bool": "BOOLEAN"}
DESCRIPTIONS = {
    "id": "Stable entity identifier, unique within this layer",
    "source_id": "Native source identity where available; null for sources lacking native IDs",
    "name": "Display name: English first, then documented Chinese fallback; null if unnamed",
    "name_en": "Readable English source name", "name_zh_hant": "Traditional Chinese source name",
    "name_zh_hans": "Simplified Chinese source name, when supplied",
    "entity_type": "Kind of geographic entity", "provenance": "Source and lossless record lookup",
    "raw_json": "Original input record serialised without loss of fields or values",
    "source_record": "Zero-based source array index", "source_identity_name": "Exact original estate identity name",
    "source_fid": "Native geodatabase record FID, separate from the referenced entity ID",
    "record_id": "Stable source-table record identity from layer and native FID; preserves entity versions",
    "latitude": "Original WGS84 latitude in degrees (see CRS evidence/assumption)",
    "longitude": "Original WGS84 longitude in degrees (see CRS evidence/assumption)",
    "easting": "EPSG:2326 X coordinate in metres", "northing": "EPSG:2326 Y coordinate in metres",
    "housing_district": "Documented Housing Authority allocation category, separate from administrative district",
    "source_administrative_district": "Original administrative district, not an allocation category",
    "housing_district_provenance": "Crosswalk source and proxy-boundary documentation",
    "location_role": "What the point actually represents; no invented gate/entrance positions",
    "entrance_evidence": "Whether the supplied point is a verified entrance (currently unknown)",
    "has_ae": "Source A&E availability: true/false/unknown; does not restrict institution eligibility",
    "Gradient": "Original segment gradient angle in radians (3DPN dictionary v2.2, PDF page 12); sign and aggregation not explicitly documented",
    "gradient_raw": "Preserved original Gradient, in radians; sign and within-path aggregation not explicitly documented",
    "Shape_Length": "Original horizontal XY polyline length in metres (3DPN dictionary v2.2, PDF page 14)",
    "AccessTimeID": "Unused original source attribute; schedules are ignored, all routes always open",
    "operators_json": "JSON array of original service/operator codes, including codes outside named flags",
    "boarding_accessibility": "Unknown unless supported by explicit boarding evidence",
    "access_evidence": "Dictionary-based iGeoCom evidence, not a routing eligibility decision",
    "access_evidence_json": "Per-source entrance evidence; unknowns/differences are retained",
    "access_evidence_difference": "Source evidence differs; neither source is silently overwritten",
    "station_id": "MTR CSV station ID linked by supported crosswalk; null if unresolved",
    "station_match_status": "matched/override/ambiguous/unmatched",
    "station_match_evidence": "Recorded matching rule or override reason",
    "exit_code": "Explicit named exit code; null for equipment records without a resolvable exit name",
    "source_grid_residual_m": "Distance between projected WGS84 geometry and original iGeoCom grid attributes",
    "source_grid_easting": "Original iGeoCom EASTING attribute, renamed to avoid a case-insensitive storage collision",
    "source_grid_northing": "Original iGeoCom NORTHING attribute, renamed to avoid a case-insensitive storage collision",
    "crosswalk_residual_m": "Distance between estate and crosswalk points, in metres",
    "timestamp_policy": "Source date/time strings retained exactly; not used for opening-hours decisions",
}


def schema_for(table, inspection):
    fields = OrderedDict()
    for name, kind in table.types.items():
        meaning = DESCRIPTIONS.get(name)
        if meaning is None:
            meaning = ("Original source field; see source_schema and preserved source record" if
                       name in table.metadata.get("source_schema", {}) else
                       "Source/reference field; see retained records and source manifest")
        if name.endswith("_label"):
            meaning = "Decoded source domain description for " + name[:-6]
        if name.endswith("_bool"):
            meaning = "Explicit decoded boolean for " + name[:-5] + "; unknown codes remain null"
        fields[name] = {"logical_type": kind, "nullable": bool(table.masks[name].any()),
                        "null_count": int(table.masks[name].sum()), "meaning": meaning,
                        "sqlite_storage_type": SQL_TYPES.get(kind, "TEXT")}
    result = {"count": len(table), "fields": fields, "metadata": table.metadata}
    if isinstance(table, SpatialDataset):
        result.update(horizontal_crs=table.crs, vertical_crs=table.vertical_crs,
                      geometry_type=table.geometry_type)
    return result


def write_sqlite(path, tables, report):
    with sqlite3.connect(path) as con:
        for table in tables:
            names = list(table.columns)
            if not names:
                raise ValueError("Table without a declared schema: " + table.name)
            declaration = ", ".join(quote(k) + " " + SQL_TYPES.get(table.types[k], "TEXT") for k in names)
            con.execute("CREATE TABLE {} ({})".format(quote(table.name), declaration))
            statement = "INSERT INTO {} VALUES ({})".format(quote(table.name), ",".join("?" for _ in names))
            con.executemany(statement, (tuple(row[k] for k in names) for row in table.rows()))
    # Every stored value is checked, not only samples or counts.
    with sqlite3.connect(path) as con:
        for table in tables:
            columns = list(table.columns)
            info = con.execute("PRAGMA table_info({})".format(quote(table.name))).fetchall()
            if [r[1] for r in info] != columns or [r[2] for r in info] != [SQL_TYPES.get(table.types[k], "TEXT") for k in columns]:
                report.error("sqlite_schema_roundtrip", table.name, "SQLite columns/types changed")
            cursor = con.execute("SELECT {} FROM {} ORDER BY rowid".format(
                ",".join(map(quote, columns)), quote(table.name)))
            count = 0
            for expected in table.rows():
                actual = cursor.fetchone()
                wanted = tuple(expected[k] for k in columns)
                if actual != wanted:
                    report.error("sqlite_roundtrip", table.name, "Stored row differs from source values", str(count))
                    break
                count += 1
            if count != len(table) or cursor.fetchone() is not None:
                report.error("sqlite_count_roundtrip", table.name, "Stored row count differs")
            report.checks[table.name + ":sqlite_roundtrip"] = {"rows_checked": count, "all_fields": True}


def write_spatial(path, datasets, report, batch_size=50000):
    for ds in datasets:
        fields = list(ds.columns)
        if len({k.casefold() for k in fields}) != len(fields):
            raise ValueError("Case-insensitive field collision in " + ds.name)
        for start in range(0, len(ds), batch_size):
            end = min(start + batch_size, len(ds))
            pyogrio.raw.write(
                path, shapely.to_wkb(ds.geometry[start:end]),
                [ds.columns[k][start:end] for k in fields], fields,
                field_mask=[ds.masks[k][start:end] for k in fields],
                layer=ds.name, driver="GPKG", geometry_type=ds.geometry_type,
                crs=ds.crs, append=start > 0,
                layer_metadata={"preparation_metadata": json.dumps(ds.metadata, ensure_ascii=False),
                                "vertical_crs": ds.vertical_crs or "unknown",
                                "access_policy": "always_open; schedules ignored"})
        info = pyogrio.read_info(path, layer=ds.name)
        if info["features"] != len(ds) or list(info["fields"]) != fields:
            report.error("spatial_schema_roundtrip", ds.name, "Written feature count/field names differ")
        if not CRS(info["crs"]).equals(CRS(ds.crs)) or info["geometry_type"] != ds.geometry_type:
            report.error("spatial_crs_roundtrip", ds.name, "Written CRS/geometry type differs")
        expected_dtypes = {"int16": {"int16", "int32"}, "int32": {"int32"}, "int64": {"int64"},
                           "float64": {"float64"}, "bool": {"bool"}, "string": {"object"},
                           "timestamp_text": {"object"}}
        for field, dtype in zip(info["fields"], info["dtypes"]):
            if dtype not in expected_dtypes.get(ds.types[field], {"object"}):
                report.error("spatial_field_type", ds.name, "Written field type differs: " + field,
                             details={"expected": ds.types[field], "actual": dtype})
        checked = 0
        for start in range(0, len(ds), batch_size):
            end = min(start + batch_size, len(ds))
            meta, _, geometry, values = pyogrio.raw.read(path, layer=ds.name,
                skip_features=start, max_features=end-start, datetime_as_string=True)
            expected_geometry = shapely.to_wkb(ds.geometry[start:end])
            bad_geom = np.flatnonzero(expected_geometry != geometry)
            if len(bad_geom):
                report.error("geometry_roundtrip", ds.name, "WKB changed; vertices, multipart order or Z may differ",
                             ds.value("id", start + int(bad_geom[0])))
            for field, actual in zip(meta["fields"], values):
                expected = ds.columns[field][start:end]
                mask = ds.masks[field][start:end]
                actual_mask = (np.isnan(actual) if actual.dtype.kind == "f" else
                               np.fromiter((v is None for v in actual), bool, count=len(actual)))
                if not np.array_equal(mask, actual_mask):
                    report.error("null_roundtrip", ds.name, "Null positions changed: " + field)
                if not np.array_equal(expected[~mask], actual[~mask]):
                    report.error("attribute_roundtrip", ds.name, "Non-null values changed: " + field)
            checked += len(geometry)
        report.checks[ds.name + ":spatial_roundtrip"] = {
            "rows_checked": checked, "all_fields": True, "wkb_exact": True,
            "timestamp_storage": "text (source strings retained)", "geometry_tolerance_m": 0.0}


def write_outputs(directory, datasets, tables, manifest, inspection, registry, review, report):
    directory.mkdir(parents=True, exist_ok=True)
    schema = {"horizontal_crs": "EPSG:2326", "access_policy": manifest["access_policy"],
              "original_network_compound_crs_wkt": inspection["original_compound_crs_wkt"],
              "coded_domains": inspection["domains"],
              "spatial_layers": {ds.name: schema_for(ds, inspection) for ds in datasets},
              "reference_tables": {t.name: schema_for(t, inspection) for t in tables}}
    write_json(directory / "schema.json", schema)
    write_json(directory / "source_manifest.json", manifest)
    write_json(directory / "entity_ids.json", registry.entries)
    with (directory / "mtr_match_review.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["dataset", "source_id", "name", "issue", "candidate_station_ids", "station_id", "exit_code", "evidence"])
        writer.writeheader()
        writer.writerows(review)
    write_spatial(directory / "harmonised.gpkg", datasets, report)
    write_sqlite(directory / "reference_tables.sqlite", tables, report)


def publish_run(run, current, registry_path):
    """One pointer switch publishes both data and registry snapshot together."""
    run, current, registry_path = Path(run), Path(current), Path(registry_path)
    if current.exists() and not current.is_symlink():
        raise ValueError("Current output must be absent or a managed symlink: " + str(current))
    target = os.path.relpath(current / "entity_ids.json", registry_path.parent)
    if os.path.lexists(registry_path):
        if not registry_path.is_symlink() or os.readlink(registry_path) != target:
            raise ValueError("Registry must be the managed output-snapshot link; preserve existing registry and resolve explicitly")
    else:
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        registry_path.symlink_to(target)
    current.parent.mkdir(parents=True, exist_ok=True)
    temporary = current.with_name("." + current.name + "-" + uuid.uuid4().hex)
    temporary.symlink_to(os.path.relpath(run, current.parent), target_is_directory=True)
    os.replace(temporary, current)


def read_spatial_dataset(directory, layer):
    """Public loader for later graph/snapping stages; restore logical null types."""
    directory = Path(directory)
    schema = json.loads((directory / "schema.json").read_text(encoding="utf-8"))["spatial_layers"][layer]
    meta, _, geometry, values = pyogrio.raw.read(directory / "harmonised.gpkg", layer=layer, datetime_as_string=True)
    ds = SpatialDataset(layer, metadata=schema["metadata"], crs=schema["horizontal_crs"],
                        vertical_crs=schema["vertical_crs"], geometry_type=schema["geometry_type"])
    for field, v in zip(meta["fields"], values):
        ds.add(field, v, schema["fields"][field]["logical_type"])
    ds.geometry = shapely.from_wkb(geometry)
    ds.check_contract()
    return ds
