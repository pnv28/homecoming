"""Run Step 1 using only local inputs and installed packages."""
import argparse
from datetime import datetime, timezone
import fcntl
import os
from pathlib import Path
import sys
import traceback
import uuid

from .export import publish_run, verify_geodataframes, write_json, write_outputs
from .harmonise import (IdentityRegistry, assign_housing_districts, decode_network,
                        load_bus_stops, load_estates, load_hospitals, load_mtr_exits,
                        reconcile_bus, to_common_crs)
from .ingest import (confirm_network_definitions, inspect_network, inventory_sources, load_config, load_network,
                     read_csv, read_json, safe_extract_network, sha256)
from .mtr_master import prepare as prepare_mtr, write_checked as write_mtr
from .mtr_prepare import attach_masters
from .policy import add_network_candidates, load_policy
from .validate import ValidationReport, validate, write_report


def progress(message):
    print(message, flush=True)


def load_registry(root, config):
    # The local link is intentionally ignored by Git. A fresh checkout must
    # recover committed aliases from the versioned current output snapshot.
    local = Path(root) / config["registry"]
    published = Path(root) / config["output"] / "entity_ids.json"
    source = local if local.exists() else published
    return IdentityRegistry(read_json(source) if source.exists() else {})


def run(config_path):
    config = load_config(config_path)
    root = Path(config["_root"])
    if not config.get("access_policy", {}).get("always_open"):
        raise ValueError("This Step 1 implementation requires the agreed always-open policy")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    # Failed/staged work stays in cache. Only successful artifacts enter the
    # versioned precomputed directory.
    directory = root / config.get("cache", "cache") / "step_1_staging" / run_id
    directory.mkdir(parents=True)
    report = ValidationReport()
    try:
        progress("1/7 Inventory inputs and verify reference copies")
        paths, manifest = inventory_sources(config, report)
        manifest["run_id"] = run_id
        manifest["access_policy"] = config["access_policy"]
        policy = load_policy(paths["routing_policy"])
        manifest["modelling_policy"] = policy
        manifest["output_interface"] = {
            "storage": "GeoPackage spatial layers and SQLite reference tables",
            "spatial_python_type": "geopandas.GeoDataFrame",
            "loader": "estate_ranking.export.read_outputs or read_geodataframe",
            "nullable_types_restored_from_schema": True,
            "output_root": config["output"]}
        registry_path = root / config["registry"]
        registry = load_registry(root, config)
        write_json(directory / "source_manifest.json", manifest)
        progress("2/7 Extract and inspect network; skip both access-schedule tables")
        gdb, extraction = safe_extract_network(paths["network"], root / config["cache"], manifest["sources"]["network"]["sha256"])
        inspection = inspect_network(gdb)
        inspection["field_definitions"] = confirm_network_definitions(paths["network_dictionary"])
        inspection["excluded_tables"] = ["AccessTime", "AccessTimeDetails"]
        manifest["network_inspection"] = inspection
        manifest["sources"]["network"]["selected_archive_members"] = sorted(extraction["files"])
        progress("3/7 Load paths/support references and prepare geographic points")
        network, tables = load_network(gdb, inspection)
        decode_network(network, inspection["domains"], report)
        add_network_candidates(network, policy, report)
        estates = load_estates(paths["estates"], registry)
        hospitals = load_hospitals(paths["hospitals"], registry, report)
        exits = load_mtr_exits(paths["mtr_exits"])
        railway = load_mtr_exits(paths["railway_stations"], "railway_stations")
        stops = load_bus_stops(paths["bus_stops"])
        datasets = [network, estates, hospitals, exits, railway, stops]
        for ds in datasets[1:]:
            to_common_crs(ds, config["sources"][ds.name], config, report)
        progress("4/7 Assign allocation categories, reconcile MTR and verify raw bus records")
        tables.append(assign_housing_districts(estates, paths["housing_crosswalk"], config, report))
        for key in ["station_overrides", "exit_overrides"]:
            if any(any(row.values()) for row in read_csv(root / config[key])):
                raise ValueError("Legacy MTR overrides need explicit migration to physical station IDs: " + config[key])
        mtr_files, mtr_accounting = prepare_mtr(root, {
            "dictionary_zip": paths["mtr_dictionary"], "railway_stations": paths["railway_stations"],
            "access_points": paths["mtr_exits"], "station_csv": paths["mtr_station_csv"],
            "category_csv": paths["mtr_categories"], "facility_csv": paths["mtr_facilities"],
            "igeocom_dictionary": paths["igeocom_dictionary"]})
        mtr_tables, review = attach_masters(exits, railway, mtr_files, mtr_accounting, policy, report)
        tables.extend(mtr_tables)
        tables.extend(reconcile_bus(stops, paths["raw_bus"], paths["raw_gmb"], report, policy))
        progress("5/7 Validate every record and non-schedule relationship")
        validate(datasets, tables, config, report)
        for ds in datasets:
            baseline = config["validation"]["expected_counts"].get(ds.name)
            if baseline is not None and baseline != len(ds):
                report.warning("snapshot_count", ds.name, "Source count differs from configured snapshot baseline",
                               details={"baseline": baseline, "actual": len(ds)})
        report.checks["estate_hospital_location_policy"] = {
            "user_accepted_map_point_approximation": True, "verified_entrance_collection_required": False,
            "network_connectors_computed": False}
        write_json(directory / "source_manifest.json", manifest)
        if report.errors:
            write_report(directory, report)
            progress("Validation failed; previous output and registry are unchanged. See " + str(directory / "validation_report.md"))
            return 1
        progress("6/7 Write staged outputs and check every geometry/attribute on read-back")
        write_outputs(directory, datasets, tables, manifest, inspection, registry, review, report)
        progress("6/7 Reopen all six outputs as actual GeoDataFrames and verify every value")
        verify_geodataframes(directory, datasets, report)
        write_mtr(directory / "mtr_master", mtr_files)
        write_json(directory / "model_policy.json", policy)
        if read_json(directory / "model_policy.json") != policy:
            raise ValueError("Model-policy snapshot did not round-trip")
        # Prevent a moving input from being published with hashes of a different snapshot.
        for key, path in paths.items():
            if sha256(path) != manifest["sources"][key]["sha256"]:
                report.error("source_changed_during_run", key, "Selected input changed before publication")
        report.checks["source_hashes_rechecked_before_publication"] = len(paths)
        report.checks["mtr_master_json_roundtrip"] = {"files": len(mtr_files), "all_values": True}
        write_report(directory, report)
        if report.errors:
            progress("Read-back checks failed; previous output and registry are unchanged. See " + str(directory / "validation_report.md"))
            return 1
        write_json(directory / "SUCCESS.json", {"run_id": run_id, "validation": report.as_dict()["status"],
                                                "completed_utc": datetime.now(timezone.utc).isoformat()})
        progress("7/7 Select the successful data and ID-registry snapshot together")
        destination = root / config["runs"] / run_id
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.replace(directory, destination)
        directory = destination
        publish_run(directory, root / config["output"], registry_path,
                    config.get("legacy_registry_targets", []))
        progress("Complete: " + str(root / config["output"]))
        progress("{} spatial records; {} errors; {} warnings".format(sum(map(len, datasets)), len(report.errors),
                                                                      len(report.issues) - len(report.errors)))
        return 0
    except Exception as exc:
        report.error("pipeline_exception", "step_1", str(exc), details={"exception_type": type(exc).__name__})
        write_report(directory, report)
        (directory / "failure_traceback.txt").write_text(traceback.format_exc(), encoding="utf-8")
        progress("Step 1 failed; previous successful output was not replaced. Diagnostics: " + str(directory))
        progress(type(exc).__name__ + ": " + str(exc))
        return 1


def main(argv=None):
    parser = argparse.ArgumentParser(description="Prepare Step 1 housing-ranking data; all routes assumed always open")
    parser.add_argument("--config", type=Path, default=Path(__file__).resolve().parents[2] / "config/step_1.json")
    args = parser.parse_args(argv)
    config = load_config(args.config)
    # A process lock prevents two runs from racing on extraction/publishing IDs.
    lock_path = Path(config["_root"]) / "cache/step_1.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.error("Another Step 1 run is already active")
        return run(args.config)


if __name__ == "__main__":
    sys.exit(main())
