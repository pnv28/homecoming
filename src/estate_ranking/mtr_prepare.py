"""Attach physical MTR masters to Step 1 layers and evidence tables."""
import json

from .models import Table
from .validate import references, unique


def flatten(row):
    return {(key + "_json" if isinstance(value, (list, dict)) else key):
            json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else value
            for key, value in row.items()}


def attach_masters(exits, railway, files, accounting, policy, report):
    stations = {r["source_geonameid"]: r for r in files["mtr_station_master.json"]}
    accesses = {r["source_geonameid"]: r for r in files["mtr_access_station_map.json"]}
    mobility = {r["source_geonameid"]: r for r in files["mtr_mobility_exit_master.json"]}
    crosswalk, review = [], []
    excluded = set(policy["modes"]["general"]["excluded_access_equipment"])
    for ds, lookup in [(exits, accesses), (railway, stations)]:
        station_ids, statuses, codes, methods = [], [], [], []
        for i in range(len(ds)):
            source_id = ds.value("source_id", i)
            if source_id not in lookup:
                raise ValueError("MTR source point missing from physical master: " + source_id)
            row = lookup[source_id]
            if (ds.value("longitude", i), ds.value("latitude", i)) != (row["longitude"], row["latitude"]):
                raise ValueError("MTR source coordinate differs from master: " + source_id)
            code = row.get("exit_code")
            method = "Exact normalised English/Chinese name to physical iGeoCom station"
            station_ids.append(row["station_id"])
            statuses.append("matched")
            codes.append(code)
            methods.append(method)
            crosswalk.append({"record_id": ds.name + ":" + source_id, "dataset": ds.name,
                              "source_id": source_id, "station_id": row["station_id"],
                              "status": "matched", "evidence": method, "exit_code": code})
            if ds is exits and code is None:
                review.append({"dataset": ds.name, "source_id": source_id, "name": ds.value("name", i),
                               "issue": "exit_code_unspecified", "candidate_station_ids": row["station_id"],
                               "station_id": row["station_id"], "exit_code": None,
                               "evidence": "Physical station and coordinate known; source supplies no exit code"})
        ds.add("station_id", station_ids).add("station_match_status", statuses)
        ds.add("station_match_evidence", methods).add("exit_code", codes)
        ds.metadata["station_identity"] = "Physical MTR-S-<GEONAMEID>; legacy CSV IDs mapped separately"
        report.checks[ds.name + ":station_matches"] = {"matched": len(ds), "ambiguous": 0, "unmatched": 0}
    access_rows = [accesses[exits.value("source_id", i)] for i in range(len(exits))]
    mobile_rows = [mobility.get(exits.value("source_id", i)) for i in range(len(exits))]
    exits.add("access_id", [r["access_id"] for r in access_rows])
    exits.add("has_mobility_evidence", [r["has_mobility_evidence"] for r in access_rows], "bool")
    exits.add("mobility_types_json", [json.dumps(r["mobility_types"] if r else [], ensure_ascii=False) for r in mobile_rows])
    exits.add("access_evidence_json", [json.dumps(r["evidence"] if r else [], ensure_ascii=False) for r in mobile_rows])
    exits.add("access_evidence_difference", [bool(r and r["equipment_evidence_difference"]) for r in mobile_rows], "bool")
    exits.add("general_mode_candidate", [not r or bool(set(r["mobility_types"]) - excluded) for r in mobile_rows], "bool")
    exits.add("wheelchair_mode_candidate", [bool(r) for r in mobile_rows], "bool")
    exits.add("exit_only_evidence", [bool(r and r["exit_only_evidence"]) for r in mobile_rows], "bool")
    exits.metadata["mode_candidates"] = "Evidence/equipment selection only; no network reachability or continuous-route certification"

    facilities = files["mtr_facilities_decoded.json"]
    category_rows = {r["facility_code"]: r["category_record"] for r in facilities}
    exit_references = [dict(record_id=r["facility_record_id"] + ":" + code,
                            facility_record_id=r["facility_record_id"], station_id=r["station_id"],
                            exit_code=code, available=r["available"]) for r in facilities for code in r["exit_codes"]]
    links = [dict(record_id=r["access_id"] + ":" + fid, access_id=r["access_id"],
                  station_id=r["station_id"], facility_record_id=fid)
             for r in access_rows for fid in r["matched_facility_records"]]
    tables = [Table.from_rows("mtr_stations", files["mtr_station_master.json"]),
              Table.from_rows("mtr_legacy_station_id_map", files["mtr_legacy_station_id_map.json"]),
              Table.from_rows("mtr_facility_categories", category_rows.values()),
              Table.from_rows("mtr_facilities", [flatten(r) for r in facilities]),
              Table.from_rows("mtr_station_crosswalk", crosswalk),
              Table.from_rows("mtr_facility_exit_references", exit_references,
                              types={"record_id": "string", "facility_record_id": "string", "station_id": "string", "exit_code": "string", "available": "bool"}),
              Table.from_rows("mtr_access_facility_links", links,
                              types={"record_id": "string", "access_id": "string", "station_id": "string", "facility_record_id": "string"}),
              Table.from_rows("mtr_mobility_access", [flatten(r) for r in files["mtr_mobility_exit_master.json"]])]
    by_name = {t.name: t for t in tables}
    unique(by_name["mtr_stations"], "station_id", report)
    unique(by_name["mtr_facilities"], "facility_record_id", report)
    unique(by_name["mtr_legacy_station_id_map"], "legacy_station_id", report)
    for child in [exits, railway, by_name["mtr_mobility_access"], by_name["mtr_legacy_station_id_map"]]:
        references(child, "station_id", by_name["mtr_stations"], "station_id", report, "error")
    references(by_name["mtr_facilities"], "station_id", by_name["mtr_stations"], "station_id", report, "error")
    references(by_name["mtr_access_facility_links"], "facility_record_id", by_name["mtr_facilities"], "facility_record_id", report, "error")
    references(by_name["mtr_access_facility_links"], "access_id", exits, "access_id", report, "error")
    report.checks["mtr_master"] = accounting
    report.checks["mtr_master_review"] = {k: len(v) for k, v in files["mtr_master_review.json"].items()}
    for key, rows in files["mtr_master_review.json"].items():
        if rows:
            report.warning("mtr_master_review", "mtr", key,
                           details={"records": len(rows), "report": "mtr_master/mtr_master_review.json"})
    return tables, review
