"""Physical station and mobility access masters, decoded from supplied dictionaries.

No line/route fields enter the masters. Native point IDs make identities stable
under row reordering. Missing facility locations/identities remain review items.
"""
from collections import Counter, defaultdict
from datetime import datetime, timezone
from io import BytesIO
import argparse
import json
import os
from pathlib import Path
import re
import tempfile
import unicodedata
import zipfile

from pypdf import PdfReader

from .export import write_json
from .harmonise import display
from .ingest import read_csv, read_json, sha256
from .models import identifier
from .mtr_links import ACCESS_CODES, normalise_station
from .validate import require


DICTIONARY_MEMBERS = {
    "mtr_lines_and_stations_dataspec.pdf": ["Station ID", "Station Code", "English Name", "UTF-8"],
    "barrier_free_facilities_dataspec.pdf": ["Station_No", "Item_Code", "not in use", "Y - Available"],
    "barrier_free_facility_category_dataspec.pdf": ["Item_Code", "Facility_En", "Facility_Zh"]}


def decode_dictionary(archive):
    """Read the three relevant PDFs directly, without extracting arbitrary ZIP paths."""
    result = {}
    with zipfile.ZipFile(archive) as z:
        for name, phrases in DICTIONARY_MEMBERS.items():
            raw = z.read(name)
            if len(raw) > 10 * 1024 * 1024:
                raise ValueError("Oversized dictionary PDF")
            reader = PdfReader(BytesIO(raw))
            text = "\n".join(page.extract_text(extraction_mode="layout") or "" for page in reader.pages)
            plain = re.sub(r"\s+", " ", text)
            for phrase in phrases:
                if phrase not in plain:
                    raise ValueError("Selected MTR dictionary definition not found: " + phrase)
            result[name] = {"pdf_pages": len(reader.pages), "extracted_text": text}
    return {"members": result, "definitions": {
        "Station_No": "MTR station CSV Station ID (not iGeoCom GEONAMEID)",
        "Key": "Facility category CSV Item_Code", "Value": {"Y": True, "N": False},
        "AJTextEn": "Location/exit description in English", "AJTextZh": "Location/exit description in Chinese",
        "Exit_Coordinate_X_Y": "Longitude/latitude field not in use; do not use it as coordinate evidence",
        "facility_status": "Static provision information, not live service/maintenance status"}}


def normalise(text):
    text = unicodedata.normalize("NFKC", display(text) or "").strip()
    text = re.sub(r"^(?:香港鐵路|港鐵)", "", text)
    return normalise_station(text)


def station_from_name(text, chinese=False):
    text = unicodedata.normalize("NFKC", display(text) or "")
    pattern = (r"^(?:香港鐵路|港鐵)(.*?)站" if chinese else
               r"^(?:Mass Transit Railway|MTR)\s+(.*?)\s+Station\b")
    match = re.search(pattern, text, re.I)
    return display(match[1]) if match else None


def exit_code_from_name(english, chinese=None):
    text = unicodedata.normalize("NFKC", display(english) or "")
    match = re.search(r"\bStation\s*[-–—]\s*([A-Z]\d*)\s+(?:Access|Exit)\b", text, re.I)
    if match:
        return match[1].upper()
    text = unicodedata.normalize("NFKC", display(chinese) or "")
    match = re.search(r"站\s*[-–—]\s*([A-Z]\d*)\s*(?:進出口|出口)", text, re.I)
    return match[1].upper() if match else None


def facility_exit_codes(text):
    """Parse an explicit initial exit list; keep notes without inventing codes.

    'Exits A & B through a mall' -> A,B; 'Exit A & Exit D' -> A,D;
    'Exits A & E, ITCI Drop Off' -> A,E, never I/T/C/I.
    """
    text = unicodedata.normalize("NFKC", display(text) or "")
    first = re.match(r"^Exits?\s+", text, re.I)
    if not first:
        return []
    remaining = text[first.end():]
    codes = []
    while True:
        token = re.match(r"(?:Exits?\s+)?([A-Z]\d*)(?![A-Za-z0-9])", remaining, re.I)
        if not token:
            break
        codes.append(token[1].upper())
        remaining = remaining[token.end():]
        separator = re.match(r"\s*(?:,|&|\band\b)\s*", remaining, re.I)
        if not separator:
            break
        remaining = remaining[separator.end():]
    return list(dict.fromkeys(codes))


def mobility_kind(category):
    """Decode the category description, keeping paid-area equipment internal."""
    if category.get("Category_Id") != "AJ":
        return None
    description = (display(category.get("Facility_En")) or "").casefold()
    if "paid area" in description and "unpaid area" not in description:
        return None
    if "same level" in description:
        return "same_level"
    if "stair lift" in description:
        return "stair_lift"
    if "wheelchair aid" in description:
        return "wheelchair_aid"
    if "vertical lifting platform" in description:
        return "vertical_lifting_platform"
    if "ramp" in description:
        return "ramp"
    if "lift" in description:
        return "lift"
    return None


def point_coordinates(feature):
    geometry = feature.get("geometry")
    if not geometry or geometry["type"] != "Point" or len(geometry["coordinates"]) != 2:
        raise ValueError("Expected an original 2D iGeoCom point")
    longitude, latitude = geometry["coordinates"]
    if not (113.7 <= longitude <= 114.5 and 22.1 <= latitude <= 22.6):
        raise ValueError("Point outside configured Hong Kong sanity bounds")
    return float(latitude), float(longitude)


def build_masters(railway_features, access_features, station_rows, category_rows, facility_rows):
    stations, station_index = [], defaultdict(set)
    station_point_ids = set()
    for f in railway_features:
        p = f["properties"]
        require(p, ["GEONAMEID", "ENGLISHNAME", "CHINESENAME", "TYPE"], "railway_stations")
        if p["TYPE"] != "RSN":
            raise ValueError("Unexpected railway reference type")
        source_id = identifier(p["GEONAMEID"])
        if not source_id or source_id in station_point_ids:
            raise ValueError("Missing/duplicate station GEONAMEID")
        station_point_ids.add(source_id)
        name_en = station_from_name(p["ENGLISHNAME"])
        name_zh = station_from_name(p["CHINESENAME"], chinese=True)
        if not name_en or not name_zh:
            raise ValueError("Station reference name needs explicit review: " + source_id)
        sid = "MTR-S-" + source_id
        lat, lon = point_coordinates(f)
        stations.append({"station_id": sid, "station_name_en": name_en, "station_name_zh": name_zh,
                         "latitude": lat, "longitude": lon, "source_geonameid": source_id})
        for name in [name_en, name_zh]:
            station_index[normalise(name)].add(sid)
    # Multiple line IDs are expected; multiple RSN points claiming the same
    # physical name need review instead of choosing one arbitrary coordinate.
    if any(len(ids) > 1 for ids in station_index.values()):
        raise ValueError("Duplicate physical station names in coordinate references")
    station_by_id = {r["station_id"]: r for r in stations}

    def match_names(names):
        candidates = set()
        for name in names:
            candidates.update(station_index.get(normalise(name), set()))
        return next(iter(candidates)) if len(candidates) == 1 else None, sorted(candidates)

    legacy = {}
    line_rows = 0
    blank_rows = 0
    for r in station_rows:
        if not any(r.values()):
            blank_rows += 1
            continue
        line_rows += 1
        require(r, ["Station ID", "English Name", "Chinese Name"], "mtr station CSV")
        source_id = r["Station ID"]
        sid, candidates = match_names([r["English Name"], r["Chinese Name"]])
        if sid is None:
            raise ValueError("Unresolved legacy station identity: " + source_id + " " + str(candidates))
        entry = {"legacy_station_id": source_id, "station_id": sid,
                 "source_station_name_en": display(r["English Name"]),
                 "source_station_name_zh": display(r["Chinese Name"]),
                 "evidence": "Exact physical-station name using English/Chinese evidence after documented normalisation"}
        if source_id in legacy and legacy[source_id] != entry:
            raise ValueError("Conflicting legacy station ID: " + source_id)
        legacy[source_id] = entry

    categories = {}
    for r in category_rows:
        require(r, ["Item_Code", "Category_Id", "Category_En", "Category_Zh", "Facility_En", "Facility_Zh"], "facility categories")
        if r["Item_Code"] in categories:
            raise ValueError("Duplicate category ID")
        categories[r["Item_Code"]] = r
    facilities, facility_index = [], defaultdict(list)
    missing_legacy = Counter()
    unlocated = []
    keys = set()
    for index, r in enumerate(facility_rows):
        require(r, ["Station_No", "Key", "Value", "AJTextEn", "AJTextZh", "Exit_Coordinate_X_Y"], "facilities")
        key = r["Station_No"] + ":" + r["Key"]
        if key in keys:
            raise ValueError("Duplicate facility station/key")
        keys.add(key)
        category = categories.get(r["Key"])
        if category is None or r["Value"] not in {"Y", "N"}:
            raise ValueError("Unknown facility key or Y/N code: " + key)
        sid = legacy.get(r["Station_No"], {}).get("station_id")
        if sid is None:
            missing_legacy[r["Station_No"]] += 1
        kind = mobility_kind(category)
        codes = facility_exit_codes(r["AJTextEn"])
        row = {"facility_record_id": key, "station_id": sid, "legacy_station_id": r["Station_No"],
               "facility_code": r["Key"], "available": r["Value"] == "Y",
               "category_en": display(category["Category_En"]), "category_zh": display(category["Category_Zh"]),
               "facility_en": display(category["Facility_En"]), "facility_zh": display(category["Facility_Zh"]),
               "mobility_type": kind, "location_en": display(r["AJTextEn"]), "location_zh": display(r["AJTextZh"]),
               "exit_codes": codes, "source_row": index, "original_record": r,
               "category_record": category}
        facilities.append(row)
        if row["available"] and kind:
            if sid and codes:
                for code in codes:
                    facility_index[(sid, code)].append(row)
            else:
                unlocated.append({"facility_record_id": key, "station_id": sid,
                                  "legacy_station_id": r["Station_No"], "mobility_type": kind,
                                  "location_en": row["location_en"], "location_zh": row["location_zh"],
                                  "reason": "station_identity_missing" if not sid else
                                            "no_unambiguous_named_exit_in_description"})

    mobility, all_links, unknown, unnamed, differences = [], [], [], [], []
    access_ids = set()
    linked_facility_exits = set()
    raw_subcats = Counter()
    for f in access_features:
        p = f["properties"]
        require(p, ["GEONAMEID", "ENGLISHNAME", "CHINESENAME", "TYPE", "SUBCAT"], "access points")
        if p["TYPE"] != "MTA":
            raise ValueError("Unexpected access feature type")
        source_id = identifier(p["GEONAMEID"])
        if not source_id or source_id in access_ids:
            raise ValueError("Missing/duplicate access GEONAMEID")
        access_ids.add(source_id)
        names = [station_from_name(p["ENGLISHNAME"]), station_from_name(p["CHINESENAME"], chinese=True),
                 p.get("E_SITENAME"), p.get("C_SITENAME")]
        sid, candidates = match_names(names)
        if sid is None:
            raise ValueError("Unresolved access station: " + source_id + " " + str(candidates))
        code = exit_code_from_name(p["ENGLISHNAME"], p["CHINESENAME"])
        if code is None:
            unnamed.append({"access_id": "MTR-A-" + source_id, "station_id": sid,
                            "access_name_en": display(p["ENGLISHNAME"]),
                            "reason": "Source identifies station/access point, but supplies no named exit code"})
        subcat = p["SUBCAT"]
        raw_subcats[subcat or "unspecified"] += 1
        if subcat and subcat not in ACCESS_CODES:
            raise ValueError("Unrecognised source access subcategory: " + subcat)
        source_type = ACCESS_CODES.get(subcat)
        linked = facility_index.get((sid, code), []) if code else []
        linked_facility_exits.update((r["facility_record_id"], code) for r in linked)
        csv_types = sorted({r["mobility_type"] for r in linked})
        types = sorted(set(csv_types + ([source_type] if source_type else [])))
        access_id = "MTR-A-" + source_id
        lat, lon = point_coordinates(f)
        basic = {"access_id": access_id, "station_id": sid, "exit_code": code,
                 "access_name_en": display(p["ENGLISHNAME"]), "access_name_zh": display(p["CHINESENAME"]),
                 "latitude": lat, "longitude": lon, "source_geonameid": source_id}
        all_links.append(dict(basic, has_mobility_evidence=bool(types), igeocom_subcategory=subcat,
                              matched_facility_records=[r["facility_record_id"] for r in linked]))
        if not types:
            unknown.append(dict(basic, reason="No explicit iGeoCom mobility type or positive named-exit facility evidence"))
            continue
        difference = bool(source_type and csv_types and source_type not in csv_types)
        if difference:
            differences.append({"access_id": access_id, "station_id": sid, "exit_code": code,
                                "igeocom_type": source_type, "csv_types": csv_types,
                                "reason": "Different equipment descriptions retained; they may coexist"})
        evidence = []
        if source_type:
            evidence.append({"source": "mtr_access_points.geojson", "source_geonameid": source_id,
                             "subcategory": subcat, "mobility_type": source_type, "scope": "source_access_point"})
        for r in linked:
            evidence.append({"source": "barrier_free_facilities.csv", "facility_record_id": r["facility_record_id"],
                             "facility_code": r["facility_code"], "mobility_type": r["mobility_type"],
                             "available": True, "location_en": r["location_en"], "location_zh": r["location_zh"],
                             "scope": "named_exit; equipment location within the exit is not established"})
        mobility.append(dict(basic, mobility_types=types,
                             assistance_related=bool(set(types) & {"stair_lift", "wheelchair_aid"}),
                             exit_only_evidence=any("for exit only" in (r["location_en"] or "").casefold()
                                                    or "只供出口" in (r["location_zh"] or "") for r in linked),
                             equipment_evidence_difference=difference, evidence=evidence))
    not_located = []
    for r in facilities:
        missing_codes = [code for code in r["exit_codes"]
                         if (r["facility_record_id"], code) not in linked_facility_exits]
        if r["available"] and r["mobility_type"] and r["station_id"] and missing_codes:
            not_located.append({"facility_record_id": r["facility_record_id"], "station_id": r["station_id"],
                                "exit_codes": missing_codes, "location_en": r["location_en"],
                                "reason": "Named facility exit has no matching coordinate record"})
    coverage = Counter(r["station_id"] for r in mobility)
    no_mobility = [{"station_id": r["station_id"], "station_name_en": r["station_name_en"]}
                   for r in stations if r["station_id"] not in coverage]
    review = {"unmapped_legacy_station_ids": dict(sorted(missing_legacy.items())),
              "access_points_without_mobility_evidence": unknown,
              "access_points_without_exit_codes": unnamed,
              "positive_facilities_without_named_station_exit": unlocated,
              "positive_named_facilities_without_coordinate_match": not_located,
              "equipment_evidence_differences": differences,
              "stations_without_mapped_mobility_access": no_mobility}
    accounting = {"source_station_points": len(railway_features), "physical_stations": len(stations),
                  "source_station_line_rows": len(station_rows), "blank_rows_ignored": blank_rows,
                  "line_rows_used_for_identity_only": line_rows, "legacy_station_ids_mapped": len(legacy),
                  "source_access_points": len(access_features), "access_points_station_matched": len(all_links),
                  "mobility_access_records": len(mobility), "access_points_without_mobility_evidence": len(unknown),
                  "access_points_without_exit_codes": len(unnamed),
                  "source_facilities": len(facility_rows), "facilities_decoded": len(facilities),
                  "unmapped_facility_rows": sum(missing_legacy.values()), "source_access_subcategories": dict(raw_subcats),
                  "stations_with_mobility_access": len(coverage), "equipment_evidence_differences": len(differences)}
    if (len(stations) != len(station_by_id)
            or not len(all_links) == len(mobility) + len(unknown) == len(access_features)
            or len({r["access_id"] for r in mobility}) != len(mobility)
            or any(r["station_id"] not in station_by_id for r in all_links)):
        raise ValueError("Master identity, record accounting, or station-reference validation failed")
    return {"mtr_station_master.json": sorted(stations, key=lambda r: r["station_name_en"].casefold()),
            "mtr_mobility_exit_master.json": sorted(mobility, key=lambda r: (
                station_by_id[r["station_id"]]["station_name_en"].casefold(), r["exit_code"] or "", r["access_id"])),
            "mtr_legacy_station_id_map.json": sorted(legacy.values(), key=lambda r: r["legacy_station_id"]),
            "mtr_facilities_decoded.json": facilities, "mtr_access_station_map.json": all_links,
            "mtr_master_review.json": review}, accounting


def input_paths(root):
    root = Path(root).resolve()
    return {"dictionary_zip": root / "original_data/mtr DataDictionary.zip",
              "railway_stations": root / "original_data/railway_stations.geojson",
              "access_points": root / "original_data/mtr_access_points.geojson",
              "station_csv": root / "original_data/reference/mtr_lines_and_stations.csv",
              "category_csv": root / "original_data/reference/barrier_free_facility_category.csv",
              "facility_csv": root / "original_data/reference/barrier_free_facilities.csv",
              "igeocom_dictionary": root / "original_data/data_dictionary_v5.pdf"}


def prepare(root, inputs=None):
    """Build validated records for either standalone or Step 1 publication."""
    root = Path(root).resolve()
    inputs = inputs or input_paths(root)
    decoded_dictionary = decode_dictionary(inputs["dictionary_zip"])
    files, accounting = build_masters(
        read_json(inputs["railway_stations"])["features"], read_json(inputs["access_points"])["features"],
        read_csv(inputs["station_csv"]), read_csv(inputs["category_csv"]), read_csv(inputs["facility_csv"]))
    files["mtr_dictionary_decoded.json"] = decoded_dictionary
    files["mtr_master_manifest.json"] = {
        "created_utc": datetime.now(timezone.utc).isoformat(), "status": "validated_with_review_items",
        "sources": {k: {"path": str(p.relative_to(root)), "sha256": sha256(p)} for k, p in inputs.items()},
        "accounting": accounting, "crs": "EPSG:4326 longitude/latitude",
        "identity_policy": "MTR-S- plus native railway-station GEONAMEID; MTR-A- plus access-point GEONAMEID; independent of row order and line/route fields",
        "coordinate_policy": "Original iGeoCom station/access geometry; never station-centre coordinates substituted for exits",
        "exit_selection": "Explicit source mobility subcategory, or positive facility evidence tied to the same physical station and named exit",
        "limits": ["Masters contain no lines or routes; legacy ID relations are stored separately",
                   "Source access records are not automatically unique physical equipment/exits; do not merge distinct IDs by coordinates alone",
                   "Unnamed access codes remain null, while their real coordinates are retained",
                   "Paid-area/station-level facilities do not manufacture external entrance coordinates",
                   "Facility descriptions linked to an exit do not locate each piece of equipment or certify every point at that exit",
                   "Assisted-access types and source differences are retained; routing eligibility is not decided by this file",
                   "Facility records are static provision evidence; schedules ignored under the accepted always-open policy"]}
    return files, accounting


def write_checked(directory, files):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for filename, value in files.items():
        write_json(directory / filename, value)
        if read_json(directory / filename) != value:
            raise ValueError("Master JSON did not round-trip: " + filename)


def build(root):
    root = Path(root).resolve()
    files, accounting = prepare(root)
    cache = root / "cache/mtr_master_staging"
    cache.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix="run-", dir=str(cache)))
    write_checked(stage, files)
    runs = root / "precomputed/outputs/mtr_master_runs"
    runs.mkdir(parents=True, exist_ok=True)
    run_name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + stage.name
    published = runs / run_name
    os.replace(stage, published)
    current = root / "precomputed/outputs/mtr_master"
    if current.exists() and not current.is_symlink():
        raise ValueError("Existing master output is not a managed link")
    temporary = current.with_name(".mtr_master-" + stage.name)
    temporary.symlink_to(os.path.relpath(published, current.parent), target_is_directory=True)
    os.replace(temporary, current)
    print(json.dumps(accounting, ensure_ascii=False, indent=2))
    print("Masters written to " + str(current))
    return accounting


def main():
    parser = argparse.ArgumentParser(description="Create physical MTR station and mobility-access masters")
    parser.add_argument("--work-root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    build(args.work_root)


if __name__ == "__main__":
    main()
