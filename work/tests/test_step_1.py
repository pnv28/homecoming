"""Fixtures for plausible-but-wrong GIS transformations and failed publication."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import numpy as np
import pyogrio.raw
import shapely

from estate_ranking.export import publish_run, read_spatial_dataset, write_json, write_spatial, write_sqlite, schema_for
from estate_ranking.harmonise import (IdentityRegistry, load_bus_stops, load_mtr_exits, reconcile_bus,
                                     spatial_rows, to_common_crs, decode_network)
from estate_ranking.ingest import confirm_network_definitions, load_network, safe_extract_network, sha256
from estate_ranking.models import SpatialDataset, Table, identifier
from estate_ranking.mtr_links import link_mtr_tables, normalise_station, parse_exit_description
from estate_ranking.validate import ValidationReport, unique


class StepOneTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="step_1_test_")
        self.root = Path(self.tmp.name)
        self.report = ValidationReport()

    def tearDown(self):
        self.tmp.cleanup()

    def test_axis_order_and_unknown_point_height(self):
        # Official iGeoCom Fanling station supplies both WGS84 and HK1980 grid
        # coordinates, giving an independent axis-order check (metre rounding).
        ds = spatial_rows("example", [dict(id="x", longitude=114.13867, latitude=22.4921)], "example")
        cfg = {"validation": {"coordinate_roundtrip_deg": 1e-8}}
        to_common_crs(ds, {"crs": "EPSG:4326", "crs_evidence": "fixture"}, cfg, self.report)
        self.assertAlmostEqual(ds.value("easting", 0), 832337, delta=2)
        self.assertAlmostEqual(ds.value("northing", 0), 839169, delta=2)
        self.assertFalse(shapely.has_z(ds.geometry)[0])
        self.assertFalse(self.report.errors)
        with self.assertRaises(ValueError):
            to_common_crs(ds, {"crs": "EPSG:2326"}, cfg, self.report)

    def test_identity_stable_across_order_and_explicit_rename(self):
        a = IdentityRegistry()
        ida = a.get("estate", "A")
        idb = a.get("estate", "B")
        b = IdentityRegistry()
        self.assertEqual(idb, b.get("estate", "B"))
        self.assertEqual(ida, b.get("estate", "A"))
        a.alias("estate", "Renamed A", "A")
        restored = IdentityRegistry(a.entries)
        self.assertEqual(ida, restored.get("estate", "Renamed A"))
        self.assertNotEqual(ida, a.get("hospital", "A"))

    def test_provider_dictionary_confirms_units_without_inventing_sign_convention(self):
        provider_pdf = Path(__file__).resolve().parents[1] / "data/3DPN_DataDictionary_v2.2.pdf"
        definitions = confirm_network_definitions(provider_pdf)
        self.assertEqual(definitions["gradient"]["unit"], "radians")
        self.assertEqual(definitions["gradient"]["sign_convention"], "not explicitly documented")
        self.assertEqual(definitions["shape_length"]["measurement"], "horizontal XY polyline length")
        self.assertEqual(definitions["shape_length"]["pdf_page"], 14)

    def test_igeocom_original_grid_fields_do_not_collide_with_working_coordinates(self):
        point = {"type": "Feature", "geometry": {"type": "Point", "coordinates": [114.13867, 22.4921]},
                 "properties": {"GEONAMEID": 1, "ENGLISHNAME": "Station-A Access", "CHINESENAME": "站",
                                "TYPE": "MTA", "SUBCAT": None, "EASTING": 832337, "NORTHING": 839169}}
        write_json(self.root / "exits.json", {"type": "FeatureCollection", "features": [point]})
        ds = load_mtr_exits(self.root / "exits.json")
        to_common_crs(ds, {"crs": "EPSG:4326", "crs_evidence": "fixture"},
                      {"validation": {"coordinate_roundtrip_deg": 1e-8, "igeocom_residual_review_m": 3}}, self.report)
        self.assertEqual(ds.value("source_grid_easting", 0), 832337)
        self.assertEqual(json.loads(ds.value("raw_json", 0))["properties"]["EASTING"], 832337)
        write_spatial(self.root / "out.gpkg", [ds], self.report)
        self.assertFalse(self.report.errors)

    def test_nullable_integer_and_duplicate_identity(self):
        t = Table("nullable").add("id", [117.0, np.nan], "int32")
        self.assertEqual(identifier(t.value("id", 0)), "117")
        self.assertIsNone(t.value("id", 1))
        self.assertIsNone(identifier(np.nan))
        with self.assertRaises(ValueError):
            identifier(117.5)
        with self.assertRaises(ValueError):
            Table("bad").add("id", [117.5], "int32")
        unique(Table.from_rows("dup", [{"id": "a"}, {"id": "a"}]), "id", self.report)
        self.assertEqual(len(self.report.errors), 1)

    def test_code_two_is_false_not_truthy(self):
        from estate_ranking.harmonise import DOMAIN_FIELDS
        ds = Table("network")
        domains = {}
        for field, domain in DOMAIN_FIELDS.items():
            ds.add(field, [1, 2, None], "int32")
            domains[domain] = {"values": {"1": "True", "2": "False"}}
        decode_network(ds, domains, self.report)
        self.assertIs(ds.value("WheelchairBarrier_bool", 0), True)
        self.assertIs(ds.value("WheelchairBarrier_bool", 1), False)
        self.assertIsNone(ds.value("WheelchairBarrier_bool", 2))

    def test_archive_traversal_is_rejected_before_extraction(self):
        archive = self.root / "bad.zip"
        with zipfile.ZipFile(archive, "w") as z:
            z.writestr("../escaped", "bad")
            z.writestr("db.gdb/file", "content")
        with self.assertRaises(ValueError):
            safe_extract_network(archive, self.root / "cache", sha256(archive))
        self.assertFalse((self.root / "escaped").exists())

    def test_schedule_records_are_never_read(self):
        fields = {"PedestrianRouteID": ("int32", 101), "Gradient": ("float64", 0.1),
                  "Shape_Length": ("float64", 10), "FeatureType": ("int32", 1),
                  "WheelchairBarrier": ("int32", 2), "WheelchairAccess": ("int32", 2),
                  "Enabled": ("int32", 1), "Direction": ("int32", 0),
                  "TerminalID": ("int32", 10), "FloorID": ("int32", None), "SiteID": ("int32", None),
                  "BuildingID_1": ("int32", None), "BuildingID_2": ("int32", None),
                  "AccessTimeID": ("int32", 999999), "AliasNameEN": ("object", None), "AliasNameTC": ("object", None)}
        description = {"fields": list(fields), "dtypes": [t for t, _ in fields.values()],
                       "source_count": 1, "geometry_type": "MultiLineString Z"}
        inspection = {"layers": {"AccessTime": {}, "PedestrianRoute": description, "AccessTimeDetails": {}}}
        data = [np.array([np.nan if value is None and t == "int32" else value],
                        dtype=object if t == "object" else "float64" if value is None else t)
                for t, value in fields.values()]
        geometry = shapely.to_wkb(shapely.from_wkt(["MULTILINESTRING Z ((836694 819070 10,836695 819071 11))"]))
        with patch("estate_ranking.ingest.pyogrio.raw.read", return_value=(
                {"fields": np.array(list(fields))}, np.array([1]), geometry, data)) as reader:
            network, tables = load_network("fixture.gdb", inspection)
            reader.assert_called_once()
            self.assertEqual(reader.call_args.kwargs["layer"], "PedestrianRoute")
            self.assertEqual(network.value("AccessTimeID", 0), 999999)
            self.assertEqual(tables, [])

    def test_full_storage_roundtrip_preserves_Z_parts_masks_unicode_and_dates(self):
        ds = SpatialDataset("network", vertical_crs="EPSG:5738", geometry_type="MultiLineString Z")
        ds.add("id", ["lift", "multi"])
        ds.add("source_id", [117, None], "int32")
        ds.add("name", ["升降機", None])
        ds.add("flag", [False, None], "bool")
        ds.add("cost", [0.125, None], "float64")
        ds.add("source_date", ["2021/02/28 00:00:00+00", None], "timestamp_text")
        ds.geometry = shapely.from_wkt([
            "MULTILINESTRING Z ((836694 819070 10, 836694 819070 20))",
            "MULTILINESTRING Z ((836695 819071 5, 836700 819075 6), (836701 819076 7, 836704 819078 8))"])
        write_spatial(self.root / "harmonised.gpkg", [ds], self.report, batch_size=1)
        write_json(self.root / "schema.json", {"spatial_layers": {"network": schema_for(ds, {})}})
        loaded = read_spatial_dataset(self.root, "network")
        self.assertEqual(loaded.columns["source_id"].dtype, np.dtype("int32"))
        self.assertEqual(loaded.value("source_id", 0), 117)
        self.assertIsNone(loaded.value("source_id", 1))
        self.assertIs(loaded.value("flag", 0), False)
        self.assertIsNone(loaded.value("flag", 1))
        self.assertTrue(np.array_equal(shapely.to_wkb(ds.geometry), shapely.to_wkb(loaded.geometry)))
        write_sqlite(self.root / "tables.sqlite", [Table("refs").add("id", [1, None], "int32").add("active", [False, None], "bool")], self.report)
        self.assertFalse(self.report.errors, self.report.as_dict())

    def test_colocated_stop_ids_remain_separate_and_union_operators_checked(self):
        stops = [{"stop_id": sid, "bus_stop": "Stop", "bus_stop_zh": "站", "latitude": 22.3,
                  "longitude": 114.17, "operators": [op], "KMB": op == "KMB", "CTB": False,
                  "GMB": op == "GMB"} for sid, op in [(1, "KMB"), (2, "GMB")]]
        write_json(self.root / "stops.json", stops)
        for source, sid, op in [("bus", 1, "KMB"), ("gmb", 2, "GMB")]:
            p = dict(stopId=sid, companyCode=op, stopNameE="Stop", stopNameC="站", stopPickDrop=3,
                     routeId=10, routeSeq=1, stopSeq=1, serviceMode="R", lastUpdateDate="2026-01-01")
            write_json(self.root / (source + ".json"), {"features": [{"geometry": {"type": "Point", "coordinates": [114.17, 22.3]}, "properties": p}]})
        ds = load_bus_stops(self.root / "stops.json")
        tables = reconcile_bus(ds, self.root / "bus.json", self.root / "gmb.json", self.report)
        self.assertEqual(len(ds), 2)
        self.assertNotEqual(ds.value("id", 0), ds.value("id", 1))
        self.assertFalse(self.report.errors)
        self.assertEqual(len(tables[0]), 2)
        ds.columns["KMB"][0] = False
        reconcile_bus(ds, self.root / "bus.json", self.root / "gmb.json", self.report)
        self.assertTrue(any(i["check"] == "bus_flag" for i in self.report.errors))

    def test_mtr_blank_categories_ambiguous_names_and_exact_exit_scope(self):
        self.assertEqual(parse_exit_description("Exits A1, B & C"), ["A1", "B", "C"])
        self.assertEqual(parse_exit_description("Lift near Exit A, contact staff"), [])
        self.assertEqual(normalise_station("Mass Transit Railway Fanling Station"), "fanling")
        def csv_file(name, rows):
            import csv
            path = self.root / name
            with path.open("w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
            return path
        station = csv_file("stations.csv", [dict(**{"Station ID": str(i), "Station Code": "X"+str(i),
            "English Name": "Shared", "Chinese Name": "共享"+str(i), "Line Code": "L", "Direction": "D", "Sequence": "1"}) for i in [1, 2]])
        cats = csv_file("cats.csv", [{"Item_Code": "AJ3", "Facility_En": "Lift", "Facility_Zh": "升降機"}])
        facilities = csv_file("facilities.csv", [{"Station_No": "1", "Key": "AJ3", "Value": "Y", "AJTextEn": "Exit A", "AJTextZh": "A出口"}])
        overrides = csv_file("override.csv", [{"dataset": "", "source_id": "", "station_id": "", "reason": ""}])
        exoverride = csv_file("exoverride.csv", [{"access_id": "", "station_id": "", "exit_code": "", "reason": ""}])
        row = dict(id="igeocom:10", source_id="10", name="Shared-A Access", longitude=114.17, latitude=22.3,
                   E_SITENAME="Shared Station", C_SITENAME=None, ENGLISHNAME="Mass Transit Railway Shared Station-A Access", CHINESENAME=None, SUBCAT=None)
        exits = spatial_rows("mtr_exits", [row], "mtr_exits")
        railway = spatial_rows("railway_stations", [dict(row, id="igeocom:11", source_id="11")], "railway_stations")
        tables, review = link_mtr_tables(exits, railway, station, facilities, cats, overrides, exoverride, self.report)
        self.assertEqual(exits.value("station_match_status", 0), "ambiguous")
        self.assertIsNone(exits.value("station_id", 0))
        self.assertEqual(exits.value("access_evidence", 0), "unknown")
        self.assertTrue(review)
        self.assertEqual(len(next(t for t in tables if t.name == "mtr_access_facility_links")), 0)

    def test_failed_candidate_does_not_replace_current_data_or_registry(self):
        a, b = self.root / "runs/a", self.root / "runs/b"
        a.mkdir(parents=True); b.mkdir(parents=True)
        write_json(a / "entity_ids.json", {"old": {"id": "stable"}})
        write_json(b / "entity_ids.json", {"new": {"id": "changed"}})
        current, registry = self.root / "current", self.root / "config/entity_ids.json"
        publish_run(a, current, registry)
        before = registry.read_bytes()
        # A failed candidate is deliberately never passed to publish_run.
        report = ValidationReport(); report.error("fixture", "b", "failed export")
        if not report.errors:
            publish_run(b, current, registry)
        self.assertEqual(current.resolve(), a.resolve())
        self.assertEqual(registry.read_bytes(), before)
        publish_run(b, current, registry)
        self.assertEqual(current.resolve(), b.resolve())
        self.assertEqual(json.loads(registry.read_text()), {"new": {"id": "changed"}})

    def test_real_pipeline_failure_preserves_previous_success_and_writes_diagnostics(self):
        from estate_ranking.step_1 import run
        good = self.root / "runs/good"
        good.mkdir(parents=True)
        write_json(good / "entity_ids.json", {"estate:A": {"id": "stable"}})
        current, registry = self.root / "current", self.root / "config/entity_ids.json"
        publish_run(good, current, registry)
        configuration = self.root / "config/step_1.json"
        write_json(configuration, {"work_root": "..", "runs": "runs", "output": "current", "registry": "config/entity_ids.json",
            "access_policy": {"always_open": True}, "sources": {"network": {"path": "missing.zip"}}})
        with patch("estate_ranking.step_1.progress"):
            self.assertEqual(run(configuration), 1)
        self.assertEqual(current.resolve(), good.resolve())
        self.assertEqual(json.loads(registry.read_text()), {"estate:A": {"id": "stable"}})
        failed = next((self.root / "cache/step_1_staging").iterdir())
        report = json.loads((failed / "validation_report.json").read_text())
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["issues"][0]["details"]["exception_type"], "FileNotFoundError")

    def test_fresh_checkout_restores_committed_aliases_without_local_registry_link(self):
        from estate_ranking.step_1 import load_registry
        published = self.root / "precomputed/step_1"
        published.mkdir(parents=True)
        registry = IdentityRegistry()
        original = registry.get("estate", "A")
        registry.alias("estate", "Renamed A", "A")
        write_json(published / "entity_ids.json", registry.entries)
        restored = load_registry(self.root, {"registry": "config/entity_ids.json", "output": "precomputed/step_1"})
        self.assertEqual(restored.get("estate", "Renamed A"), original)


if __name__ == "__main__":
    unittest.main()
