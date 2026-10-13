"""Check physical-station identities and limits of exit-level facility evidence."""
from pathlib import Path
import unittest

from estate_ranking.ingest import read_csv, read_json
from estate_ranking.mtr_master import build_masters, decode_dictionary, facility_exit_codes


def point(source_id, english, chinese, feature_type, subcategory=None):
    properties = {"GEONAMEID": source_id, "ENGLISHNAME": english, "CHINESENAME": chinese,
                  "TYPE": feature_type}
    if feature_type == "MTA":
        properties["SUBCAT"] = subcategory
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [114.15, 22.3]},
            "properties": properties}


def station_row(old_id):
    return {"Station ID": old_id, "English Name": "Example", "Chinese Name": "例子"}


def category(code, description, group="AJ"):
    return {"Item_Code": code, "Category_Id": group, "Category_En": "Access",
            "Category_Zh": "進出", "Facility_En": description, "Facility_Zh": "設施"}


def facility(old_id, code, value="Y", description="Exit A"):
    return {"Station_No": old_id, "Key": code, "Value": value, "AJTextEn": description,
            "AJTextZh": "", "Exit_Coordinate_X_Y": "unused coordinate field"}


class MasterFixtureTests(unittest.TestCase):
    def setUp(self):
        self.stations = [point("100", "Mass Transit Railway Example Station", "香港鐵路例子站", "RSN")]

    def access(self, source_id="200", code="A", subcategory=None):
        suffix = "-" + code + " Access" if code else " Access"
        zh_suffix = "-" + code + "進出口" if code else "進出口"
        return point(source_id, "MTR Example Station" + suffix, "港鐵例子站" + zh_suffix, "MTA", subcategory)

    def test_multiple_line_ids_share_one_physical_station(self):
        files, counts = build_masters(self.stations, [self.access(subcategory="MTRLIF")],
                                     [station_row("39"), station_row("44")], [], [])
        self.assertEqual(counts["physical_stations"], 1)
        self.assertEqual({r["station_id"] for r in files["mtr_legacy_station_id_map.json"]}, {"MTR-S-100"})
        self.assertEqual(files["mtr_mobility_exit_master.json"][0]["station_id"], "MTR-S-100")
        self.assertNotIn("Station ID", files["mtr_station_master.json"][0])

    def test_station_without_legacy_csv_record_and_unnamed_lift_are_retained(self):
        files, _ = build_masters(self.stations, [self.access(code=None, subcategory="MTRLIF")], [], [], [])
        row = files["mtr_mobility_exit_master.json"][0]
        self.assertIsNone(row["exit_code"])
        self.assertEqual(row["station_id"], "MTR-S-100")
        self.assertEqual(len(files["mtr_master_review.json"]["access_points_without_exit_codes"]), 1)

    def test_only_positive_external_named_exit_evidence_creates_mobility_link(self):
        categories = [category("AJ3", "Lift (unpaid area)"), category("AJ8", "Lift (paid area)"),
                      category("MJ1", "Wide gate", "MJ")]
        facilities = [facility("1", "AJ3", description="Exit A"),
                      facility("2", "AJ3", "N", "Exit B"), facility("1", "AJ8", description="Exit B"),
                      facility("1", "MJ1", description="Exit B")]
        files, _ = build_masters(self.stations, [self.access(code="A"), self.access("201", "B")],
                                [station_row("1"), station_row("2")], categories, facilities)
        self.assertEqual([r["exit_code"] for r in files["mtr_mobility_exit_master.json"]], ["A"])
        self.assertEqual(len(files["mtr_master_review.json"]["access_points_without_mobility_evidence"]), 1)
        self.assertFalse(files["mtr_facilities_decoded.json"][1]["available"])
        self.assertIn("named_exit", files["mtr_mobility_exit_master.json"][0]["evidence"][0]["scope"])

    def test_partially_located_multiple_exit_description_reports_missing_exit(self):
        files, _ = build_masters(self.stations, [self.access()], [station_row("1")],
                                [category("AJ1", "Same level")],
                                [facility("1", "AJ1", description="Exits A & B")])
        review = files["mtr_master_review.json"]["positive_named_facilities_without_coordinate_match"]
        self.assertEqual(review[0]["exit_codes"], ["B"])

    def test_missing_facility_station_identity_never_guessed_from_equipment(self):
        files, counts = build_masters(self.stations, [self.access()], [station_row("1")],
                                     [category("AJ5", "Stair lift")],
                                     [facility("70", "AJ5", description="Middle Bridge")])
        self.assertEqual(counts["unmapped_facility_rows"], 1)
        self.assertIsNone(files["mtr_facilities_decoded.json"][0]["station_id"])
        self.assertEqual(files["mtr_master_review.json"]["unmapped_legacy_station_ids"], {"70": 1})
        self.assertEqual(files["mtr_mobility_exit_master.json"], [])

    def test_distinct_colocated_points_keep_distinct_ids_and_evidence(self):
        files, _ = build_masters(self.stations, [self.access(subcategory="MTRLIF"),
                                                self.access("201", subcategory="MTRRAM")], [], [], [])
        self.assertEqual({r["access_id"] for r in files["mtr_mobility_exit_master.json"]},
                         {"MTR-A-200", "MTR-A-201"})

    def test_duplicate_coordinate_reference_id_and_invalid_availability_stop_build(self):
        with self.assertRaisesRegex(ValueError, "duplicate station"):
            build_masters(self.stations * 2, [], [], [], [])
        with self.assertRaisesRegex(ValueError, "Y/N"):
            build_masters(self.stations, [], [station_row("1")], [category("AJ3", "Lift (unpaid area)")],
                          [facility("1", "AJ3", "unknown")])

    def test_exit_notes_do_not_become_invented_exit_codes(self):
        for text, expected in [("Exit A & Exit D", ["A", "D"]),
                               ("Exits A & E, ITCI Drop Off", ["A", "E"]),
                               ("Exit E through Maritime Square", ["E"]),
                               ("Middle Bridge", []), ("Arrival Hall Departure Hall", [])]:
            with self.subTest(text=text):
                self.assertEqual(facility_exit_codes(text), expected)


class SuppliedMasterSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.inputs = [read_json(cls.root / "original_data/railway_stations.geojson")["features"],
                      read_json(cls.root / "original_data/mtr_access_points.geojson")["features"],
                      read_csv(cls.root / "original_data/reference/mtr_lines_and_stations.csv"),
                      read_csv(cls.root / "original_data/reference/barrier_free_facility_category.csv"),
                      read_csv(cls.root / "original_data/reference/barrier_free_facilities.csv")]
        cls.files, cls.counts = build_masters(*cls.inputs)

    def test_supplied_dictionary_definitions_are_found(self):
        decoded = decode_dictionary(self.root / "original_data/mtr DataDictionary.zip")
        self.assertEqual(len(decoded["members"]), 3)
        self.assertEqual(decoded["definitions"]["Value"], {"Y": True, "N": False})
        self.assertIn("not in use", decoded["definitions"]["Exit_Coordinate_X_Y"])

    def test_all_coordinates_and_station_references_preserved_without_line_fields(self):
        stations = {r["station_id"]: r for r in self.files["mtr_station_master.json"]}
        access = {r["source_geonameid"]: r for r in self.files["mtr_access_station_map.json"]}
        self.assertEqual(len(stations), len(self.inputs[0]))
        self.assertEqual(len(access), len(self.inputs[1]))
        for feature in self.inputs[1]:
            row = access[str(feature["properties"]["GEONAMEID"])]
            self.assertIn(row["station_id"], stations)
            self.assertEqual([row["longitude"], row["latitude"]], feature["geometry"]["coordinates"])
        for feature in self.inputs[0]:
            row = stations["MTR-S-" + str(feature["properties"]["GEONAMEID"])]
            self.assertEqual([row["longitude"], row["latitude"]], feature["geometry"]["coordinates"])
            self.assertFalse(any("line" in key or "route" in key for key in row))
        self.assertEqual(self.counts["source_access_points"],
                         self.counts["mobility_access_records"] + self.counts["access_points_without_mobility_evidence"])
        self.assertEqual(len(self.files["mtr_facilities_decoded.json"]), len(self.inputs[4]))
        for decoded, raw in zip(self.files["mtr_facilities_decoded.json"], self.inputs[4]):
            self.assertEqual(decoded["original_record"], raw)
            self.assertEqual(decoded["available"], raw["Value"] == "Y")

    def test_hong_kong_duplicate_ids_and_racecourse_are_resolved_without_guesses(self):
        legacy = {r["legacy_station_id"]: r["station_id"] for r in self.files["mtr_legacy_station_id_map.json"]}
        self.assertEqual(legacy["39"], legacy["44"])
        self.assertEqual(legacy["40"], legacy["45"])
        self.assertEqual(legacy["42"], legacy["46"])
        racecourse = next(r for r in self.files["mtr_station_master.json"] if r["station_name_en"] == "Racecourse")
        self.assertTrue(any(r["station_id"] == racecourse["station_id"] for r in self.files["mtr_access_station_map.json"]))
        review = self.files["mtr_master_review.json"]
        self.assertEqual(set(review["unmapped_legacy_station_ids"]), {"70", "888"})
        self.assertTrue(all(r["station_id"] is None for r in self.files["mtr_facilities_decoded.json"]
                            if r["legacy_station_id"] in {"70", "888"}))

    def test_master_ids_remain_stable_under_source_row_reordering(self):
        reversed_files, _ = build_masters(*(list(reversed(rows)) for rows in self.inputs))
        for name in ["mtr_station_master.json", "mtr_legacy_station_id_map.json"]:
            self.assertEqual(self.files[name], reversed_files[name])
        def identities(rows):
            return {r["source_geonameid"]: (r["access_id"], r["station_id"], r["exit_code"],
                                           r["latitude"], r["longitude"], r["mobility_types"]) for r in rows}
        self.assertEqual(identities(self.files["mtr_mobility_exit_master.json"]),
                         identities(reversed_files["mtr_mobility_exit_master.json"]))


if __name__ == "__main__":
    unittest.main()
