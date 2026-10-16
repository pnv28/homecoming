"""Evidence-preserving MTR joins; ambiguous names never become guessed IDs."""
from collections import Counter, defaultdict
import json
import re
import unicodedata

from .harmonise import display
from .ingest import read_csv
from .models import Table
from .validate import require


ACCESS_CODES = {"MTRLIF": "lift", "MTRRAM": "ramp", "MTRSLV": "same_level",
                "MTRSTL": "stair_lift", "MTRWCA": "wheelchair_aid"}
FACILITY_ACCESS = {"AJ1": "same_level", "AJ2": "ramp", "AJ3": "lift", "AJ4": "lift",
                   "AJ5": "stair_lift", "AJ6": "wheelchair_aid", "AJ7": "stair_lift"}


def normalise_station(text):
    text = unicodedata.normalize("NFKC", display(text) or "").casefold()
    text = re.sub(r"^(?:mass transit railway|mtr)\s+", "", text)
    text = re.sub(r"^香港鐵路", "", text)
    text = re.sub(r"(?:\s+station|站)$", "", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_exit_description(text):
    """Accept only a complete, explicitly named list: 'Exits A1, B & C'."""
    text = display(text) or ""
    match = re.fullmatch(r"Exits?\s+([A-Z]\d*(?:\s*(?:,|&|and)\s*[A-Z]\d*)*)", text, re.I)
    if not match:
        return []
    return re.findall(r"[A-Z]\d*", match[1].upper())


def access_exit_code(name):
    # Strict suffix extraction avoids treating an equipment description as a named exit.
    match = re.search(r"Station\s*-\s*([A-Z]\d*)\s+Access$", name or "", re.I)
    return match[1].upper() if match else None


def read_overrides(path, keys, required):
    entries = {}
    for row in read_csv(path):
        require(row, required, str(path))
        if not any(v for v in row.values()):
            continue
        if any(not row[k] for k in required):
            raise ValueError("Override fields must be nonempty: " + str(path))
        key = tuple(row[k] for k in keys)
        if key in entries:
            raise ValueError("Duplicate override: " + str(key))
        entries[key] = row
    return entries


def link_mtr_tables(exits, railway, station_path, facilities_path, categories_path,
                    station_override_path, exit_override_path, report):
    raw_stations = read_csv(station_path)
    blank = sum(not any(r.values()) for r in raw_stations)
    lines = [r for r in raw_stations if any(r.values())]
    stations = {}
    for r in lines:
        require(r, ["Station ID", "Station Code", "English Name", "Chinese Name", "Line Code", "Direction", "Sequence"], "mtr_station_csv")
        sid = r["Station ID"]
        if not sid:
            raise ValueError("MTR line row lacks station ID")
        row = {"station_id": sid, "station_code": r["Station Code"], "name_en": r["English Name"], "name_zh_hant": r["Chinese Name"]}
        if sid in stations and row != stations[sid]:
            report.error("station_identity", "mtr_station_csv", "Inconsistent station identity across line rows", sid)
        stations[sid] = row
    name_index = defaultdict(set)
    for sid, r in stations.items():
        for key in ["name_en", "name_zh_hant"]:
            normal = normalise_station(r[key])
            if normal:
                name_index[normal].add(sid)
    categories = {}
    for r in read_csv(categories_path):
        require(r, ["Item_Code", "Facility_En", "Facility_Zh"], "mtr_categories")
        if r["Item_Code"] in categories:
            report.error("category_id", "mtr_categories", "Duplicate category code", r["Item_Code"])
        categories[r["Item_Code"]] = r
    facilities, facility_exits, seen = [], [], set()
    for r in read_csv(facilities_path):
        require(r, ["Station_No", "Key", "Value", "AJTextEn", "AJTextZh"], "mtr_facilities")
        pair = (r["Station_No"], r["Key"])
        if pair in seen:
            report.error("facility_key", "mtr_facilities", "Duplicate station/facility key", ":".join(pair))
        seen.add(pair)
        category = categories.get(r["Key"])
        if category is None:
            report.warning("category_reference", "mtr_facilities", "Facility category missing", ":".join(pair))
        if r["Station_No"] not in stations:
            report.warning("station_reference", "mtr_facilities", "Facility station ID missing from station CSV", ":".join(pair))
        availability = {"Y": True, "N": False}.get(r["Value"])
        if availability is None:
            report.warning("facility_value", "mtr_facilities", "Unknown Y/N value retained as null", ":".join(pair))
        entry = dict(r, facility_id=":".join(pair), available=availability,
                     facility_en=category.get("Facility_En") if category else None,
                     facility_zh=category.get("Facility_Zh") if category else None)
        facilities.append(entry)
        codes = parse_exit_description(r["AJTextEn"])
        # Only entrance-related AJ1..AJ7 equipment gets exit links. Paid-area
        # lifts/toilets/wide gates are not evidence for an entrance's suitability.
        if r["Key"] in FACILITY_ACCESS:
            for code in codes:
                facility_exits.append({"facility_id": entry["facility_id"], "station_id": r["Station_No"],
                                       "exit_code": code, "facility_key": r["Key"], "available": availability,
                                       "access_evidence": FACILITY_ACCESS[r["Key"]],
                                       "raw_description": r["AJTextEn"], "scope": "explicit_named_exit"})
    station_overrides = read_overrides(station_override_path, ["dataset", "source_id"],
                                       ["dataset", "source_id", "station_id", "reason"])
    exit_overrides = read_overrides(exit_override_path, ["access_id"],
                                   ["access_id", "station_id", "exit_code", "reason"])
    allowed_station_keys = {(ds.name, str(sid)) for ds in [exits, railway] for sid in ds.columns["source_id"]}
    for key, r in station_overrides.items():
        if key not in allowed_station_keys or r["station_id"] not in stations:
            raise ValueError("Invalid station override reference: " + str(key))
    for key, r in exit_overrides.items():
        if key[0] not in set(exits.columns["source_id"]) or r["station_id"] not in stations or not re.fullmatch(r"[A-Z]\d*", r["exit_code"]):
            raise ValueError("Invalid exit override reference: " + str(key))
    review, match_rows, entrance_links = [], [], []
    facility_index = defaultdict(list)
    for r in facility_exits:
        facility_index[(r["station_id"], r["exit_code"])].append(r)
    for ds in [exits, railway]:
        station_ids, statuses, exit_codes, methods, access_types, evidence_json, conflicts = [], [], [], [], [], [], []
        for i in range(len(ds)):
            sid = ds.value("source_id", i)
            candidate_names = [ds.value(k, i) for k in ["E_SITENAME", "C_SITENAME"]]
            if ds is railway:
                candidate_names += [ds.value("ENGLISHNAME", i), ds.value("CHINESENAME", i)]
            candidates = set()
            for name in candidate_names:
                candidates.update(name_index.get(normalise_station(name), set()))
            override = station_overrides.get((ds.name, sid))
            status = "matched" if len(candidates) == 1 else "ambiguous" if candidates else "unmatched"
            station_id = next(iter(candidates)) if len(candidates) == 1 else None
            reason = "Exact name comparison after documented prefix, suffix, Unicode and whitespace normalisation"
            if override:
                station_id, status, reason = override["station_id"], "override", override["reason"]
            code = access_exit_code(ds.value("ENGLISHNAME", i)) if ds is exits else None
            ex_override = exit_overrides.get((sid,)) if ds is exits else None
            if ex_override:
                if override and override["station_id"] != ex_override["station_id"]:
                    raise ValueError("Station and exit overrides disagree: " + sid)
                station_id, code, status, reason = ex_override["station_id"], ex_override["exit_code"], "override", ex_override["reason"]
            station_ids.append(station_id)
            statuses.append(status)
            methods.append(reason)
            exit_codes.append(code)
            match_rows.append({"dataset": ds.name, "source_id": sid, "station_id": station_id,
                               "status": status, "evidence": reason, "exit_code": code,
                               "candidate_station_ids_json": json.dumps(sorted(candidates))})
            if status in {"ambiguous", "unmatched"} or (ds is exits and code is None):
                review.append({"dataset": ds.name, "source_id": sid, "name": ds.value("name", i),
                               "issue": status if status in {"ambiguous", "unmatched"} else "exit_code_unspecified",
                               "candidate_station_ids": ";".join(sorted(candidates)), "station_id": station_id,
                               "exit_code": code, "evidence": reason})
            if ds is exits:
                subcat = ds.value("SUBCAT", i)
                access = ACCESS_CODES.get(subcat, "unknown")
                if subcat and subcat not in ACCESS_CODES:
                    report.warning("access_code", "mtr_exits", "Unrecognised access subcategory retained", sid, {"code": subcat})
                linked = facility_index.get((station_id, code), []) if station_id and code else []
                evidence = [{"source": "igeocom_dictionary", "subcategory": subcat, "evidence": access}]
                positive = []
                for r in linked:
                    evidence.append({"source": "mtr_facilities", "facility_id": r["facility_id"],
                                     "available": r["available"], "evidence": r["access_evidence"]})
                    entrance_links.append(dict(r, access_id=sid))
                    if r["available"]:
                        positive.append(r["access_evidence"])
                conflict = access != "unknown" and bool(positive) and access not in positive
                if conflict:
                    report.warning("access_evidence_difference", "mtr_exits", "Source access categories differ; retained without overwriting", sid,
                                   {"igeocom": access, "csv_positive_evidence": positive})
                access_types.append(access)
                evidence_json.append(json.dumps(evidence, ensure_ascii=False))
                conflicts.append(conflict)
        ds.add("station_id", station_ids).add("station_match_status", statuses)
        ds.add("station_match_evidence", methods).add("exit_code", exit_codes)
        if ds is exits:
            ds.add("access_evidence", access_types).add("access_evidence_json", evidence_json)
            ds.add("access_evidence_difference", conflicts, "bool")
            report.checks["mtr_access_categories"] = dict(Counter(access_types))
        summary = dict(Counter(statuses))
        report.checks[ds.name + ":station_matches"] = summary
        if summary.get("unmatched") or summary.get("ambiguous"):
            report.warning("station_matches", ds.name, "Unresolved station matches remain flagged in output", details=summary)
    report.warning("mtr_access_limits", "mtr_exits", "Blank access categories remain unknown; source labels do not certify street-to-platform access or current equipment operation.")
    report.checks["mtr_csv"] = {"blank_rows_removed": blank, "stations": len(stations), "line_memberships": len(lines),
                                "facilities": len(facilities), "categories": len(categories), "review_records": len(review)}
    tables = [Table.from_rows("mtr_stations", stations.values()),
              Table.from_rows("mtr_line_memberships", lines),
              Table.from_rows("mtr_facility_categories", categories.values()),
              Table.from_rows("mtr_facilities", facilities, types={"available": "bool"}),
              Table.from_rows("mtr_station_crosswalk", match_rows),
              Table.from_rows("mtr_facility_exit_references", facility_exits, types={"station_id": "string", "exit_code": "string", "available": "bool"}),
              Table.from_rows("mtr_access_facility_links", entrance_links, types={"access_id": "string", "facility_id": "string", "available": "bool"})]
    return tables, review
