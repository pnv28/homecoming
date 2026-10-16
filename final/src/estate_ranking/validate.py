"""Consequential integrity checks and readable, record-level diagnostics."""
from collections import Counter
from dataclasses import dataclass, field
import json

import numpy as np
import shapely
from pyproj import CRS, Transformer


@dataclass
class ValidationReport:
    issues: list = field(default_factory=list)
    checks: dict = field(default_factory=dict)

    def issue(self, severity, check, source, message, record=None, details=None):
        self.issues.append(dict(severity=severity, check=check, source=source,
                                record_id=record, message=message, details=details))

    def error(self, check, source, message, record=None, details=None):
        self.issue("error", check, source, message, record, details)

    def warning(self, check, source, message, record=None, details=None):
        self.issue("warning", check, source, message, record, details)

    @property
    def errors(self):
        return [i for i in self.issues if i["severity"] == "error"]

    def as_dict(self):
        return dict(status="failed" if self.errors else "passed_with_warnings" if
                    self.issues else "passed", errors=len(self.errors),
                    warnings=sum(i["severity"] == "warning" for i in self.issues),
                    checks=self.checks, issues=self.issues)


def require(row, fields, source):
    missing = [k for k in fields if k not in row]
    if missing:
        raise ValueError("{}: missing required fields {}".format(source, missing))


def unique(table, field, report):
    values = [table.value(field, i) for i in range(len(table))]
    counts = Counter(values)
    for value, count in counts.items():
        if value is None or count > 1:
            report.error("unique_id", table.name, "Missing or duplicate primary ID",
                         value, {"count": count, "field": field})


def references(child, child_field, parent, parent_field, report, severity="warning"):
    known = set(parent.columns[parent_field][~parent.masks[parent_field]].tolist())
    missing = Counter(child.columns[child_field][~child.masks[child_field]].tolist())
    absent = {str(k): n for k, n in missing.items() if k not in known}
    if absent:
        report.issue(severity, "reference", child.name,
                     "Unresolved {} references to {}.{}".format(
                         child_field, parent.name, parent_field),
                     details={"unresolved": absent, "affected_rows": sum(absent.values())})
    report.checks["reference:{}:{}".format(child.name, child_field)] = {
        "parent": parent.name, "unresolved_ids": len(absent),
        "affected_rows": sum(absent.values())}


def validate(datasets, tables, config, report):
    bounds = config["validation"]["wgs84_bounds"]
    for ds in datasets:
        ds.check_contract()
        if not CRS(ds.crs).equals(CRS("EPSG:2326")):
            report.error("crs", ds.name, "Working horizontal CRS must be EPSG:2326")
        unique(ds, "id", report)
        empty = shapely.is_missing(ds.geometry) | shapely.is_empty(ds.geometry)
        expected = 5 if ds.geometry_type == "MultiLineString Z" else 0
        wrong = shapely.get_type_id(ds.geometry) != expected
        for i in np.flatnonzero(empty | wrong):
            report.error("geometry", ds.name, "Empty or unexpected geometry type",
                         ds.value("id", int(i)))
        # Check every vertex, including Z for the 3D network; do not reject lifts
        # on the basis of planar length or GEOS's two-dimensional validity rules.
        coords, indices = shapely.get_coordinates(ds.geometry, include_z=True,
                                                   return_index=True)
        finite = np.isfinite(coords[:, :3 if ds.vertical_crs else 2]).all(axis=1)
        for i in np.unique(indices[~finite]):
            report.error("coordinates", ds.name, "Non-finite vertex coordinate",
                         ds.value("id", int(i)))
        if ds.vertical_crs:
            if not shapely.has_z(ds.geometry).all():
                report.error("height", ds.name, "Network records have lost Z coordinates")
            report.checks[ds.name + ":shape"] = {
                "vertices": len(coords), "line_parts": int(shapely.get_num_geometries(ds.geometry).sum()),
                "zero_planar_length": int((shapely.length(ds.geometry) == 0).sum()),
                "z_min": float(np.min(coords[:, 2])), "z_max": float(np.max(coords[:, 2]))}
            lon, lat = Transformer.from_crs(ds.crs, "EPSG:4326", always_xy=True).transform(coords[:, 0], coords[:, 1])
            outside = ((lon < bounds[0]) | (lon > bounds[2]) | (lat < bounds[1]) | (lat > bounds[3]))
            for i in np.unique(indices[outside]):
                report.error("bounds", ds.name, "Network vertex outside configured broad Hong Kong bounds",
                             ds.value("id", int(i)))
            report.checks[ds.name + ":wgs84_extent"] = [float(np.min(lon)), float(np.min(lat)),
                                                         float(np.max(lon)), float(np.max(lat))]
            if ds.metadata.get("gradient_units") == "radians":
                grad = ds.columns["gradient_raw"]
                if ds.masks["gradient_raw"].any() or not np.isfinite(grad).all():
                    report.error("gradient_value", ds.name, "Required provider gradient is missing or non-finite")
                difference = np.abs(shapely.length(ds.geometry) - ds.columns["Shape_Length"])
                mismatch = np.flatnonzero(ds.masks["Shape_Length"] | ~np.isfinite(difference) | (difference > 1e-6))
                for i in mismatch:
                    report.warning("source_horizontal_length", ds.name,
                                   "Source horizontal length differs from calculated XY polyline length",
                                   ds.value("id", int(i)))
                report.checks["network:provider_measurements"] = {
                    "gradient_unit": "radians", "gradient_min_rad": float(np.min(grad)),
                    "gradient_max_rad": float(np.max(grad)), "negative_gradient_records": int((grad < 0).sum()),
                    "shape_length_unit": "metres", "shape_length_measurement": "horizontal XY polyline length",
                    "horizontal_length_max_difference_m": float(np.max(difference)),
                    "horizontal_length_records_compared": len(ds),
                    "source_sign_convention": "not explicitly documented",
                    "source_within_path_aggregation": "not explicitly documented"}
        else:
            lon, lat = ds.columns["longitude"], ds.columns["latitude"]
            bad = (~np.isfinite(lon) | ~np.isfinite(lat) | (lon < bounds[0]) |
                   (lon > bounds[2]) | (lat < bounds[1]) | (lat > bounds[3]))
            for i in np.flatnonzero(bad):
                report.error("bounds", ds.name, "Point outside configured broad Hong Kong bounds",
                             ds.value("id", int(i)))
        # Every source record is retained; any error blocks the entire candidate.
        expected_count = ds.metadata["source_count"]
        if len(ds) != expected_count:
            report.error("record_accounting", ds.name, "Source/output count mismatch")
        report.checks[ds.name + ":records"] = {"source": expected_count,
                                               "retained": len(ds), "quarantined": 0}
        if "name" in ds.columns:
            report.checks[ds.name + ":missing_names"] = int(ds.masks["name"].sum())
    by_name = {t.name: t for t in tables}
    for table in tables:
        source_count = table.metadata.get("source_count")
        if source_count is not None:
            if len(table) != source_count:
                report.error("record_accounting", table.name, "Support-table source/output count mismatch")
            report.checks[table.name + ":records"] = {"source": source_count, "retained": len(table)}
        if "record_id" in table.columns:
            unique(table, "record_id", report)
    network = next(ds for ds in datasets if ds.name == "network")
    for table, primary in [("PedRouteRelTerminalPoly", "TerminalID"),
                           ("PedRouteRelFloorPoly", "FloorID"),
                           ("PedRouteRelBldgPoly", "BuildingID"),
                           ("PedRouteRelSitePoly", "SiteID")]:
        # These are source relationship/version tables, not canonical entity
        # tables. Preserve duplicate entity references as separate records.
        ref = by_name[table]
        counts = Counter(ref.columns[primary][~ref.masks[primary]].tolist())
        if ref.masks[primary].any():
            report.error("reference_identity", table, "Missing source entity reference")
        duplicates = {str(k): n for k, n in counts.items() if n > 1}
        if duplicates:
            report.warning("reference_versions", table,
                           "Multiple source records share an entity ID; all versions retained; canonical_site_references records the accepted selection",
                           details={"entity_field": primary, "duplicates": duplicates})
    for field, table in [("TerminalID", "PedRouteRelTerminalPoly"),
                         ("FloorID", "PedRouteRelFloorPoly"), ("SiteID", "PedRouteRelSitePoly")]:
        references(network, field, by_name[table], field, report)
    for field in ["BuildingID_1", "BuildingID_2"]:
        references(network, field, by_name["PedRouteRelBldgPoly"], "BuildingID", report)
    references(by_name["PedRouteRelDistancePost"], "PedestrianRouteID", network,
               "PedestrianRouteID", report)
    report.checks["access_policy"] = {
        "always_open": True, "excluded_tables": ["AccessTime", "AccessTimeDetails"],
        "schedule_references_evaluated": False}
    report.checks["support_tables"] = {t.name: len(t) for t in tables}
    return report


def write_report(directory, report):
    directory.mkdir(parents=True, exist_ok=True)
    data = report.as_dict()
    (directory / "validation_report.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    lines = ["# Step 1 validation report", "", "Status: **{}**. {} errors; {} warnings.".format(
        data["status"], data["errors"], data["warnings"]), "",
        "These checks establish preparation integrity, not route connectivity or accessibility.", "",
        "## Checks", ""]
    for name, value in report.checks.items():
        lines.append("- **{}**: {}".format(name, json.dumps(value, ensure_ascii=False)))
    lines += ["", "## Issues", ""]
    for item in report.issues:
        lines += ["- **{} / {} / {}**{}: {}".format(
            item["severity"], item["source"], item["check"],
            " / " + str(item["record_id"]) if item["record_id"] is not None else "",
            item["message"])]
        if item["details"] is not None:
            lines.append("  Details: " + json.dumps(item["details"], ensure_ascii=False))
    (directory / "validation_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    with (directory / "rejected_records.jsonl").open("w", encoding="utf-8") as f:
        for issue in report.errors:
            f.write(json.dumps(issue, ensure_ascii=False, allow_nan=False) + "\n")
