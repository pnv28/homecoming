"""Verify mode candidates, raw-code preservation and actual GeoDataFrame outputs."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import geopandas as gpd
import numpy as np
import shapely

from estate_ranking.export import (as_geodataframe, publish_run, read_geodataframe,
                                  schema_for, verify_geodataframes, write_json, write_spatial, write_sqlite)
from estate_ranking.harmonise import load_mtr_exits
from estate_ranking.models import SpatialDataset
from estate_ranking.mtr_master import prepare, write_checked
from estate_ranking.mtr_prepare import attach_masters
from estate_ranking.policy import add_network_candidates, boarding_fields, load_policy
from estate_ranking.validate import ValidationReport


WORK = Path(__file__).resolve().parents[1]


class UpdatedPreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = load_policy(WORK / "config/routing_policy.json")

    def test_operator_and_boarding_filtering_precedes_stop_aggregation(self):
        cases = [(1, "KMB", False, False, 1), (2, "CTB", True, True, 2),
                 (3, "GMB", True, False, 3), (0, "KMB+CTB", True, True, 99),
                 (None, "GMB", True, False, 99), (2, "LWB", False, False, 2),
                 (2, "LWB+CTB", True, True, 2)]
        for code, operators, general, wheelchair, derived in cases:
            with self.subTest(code=code, operators=operators):
                result = boarding_fields(code, operators, self.policy)
                self.assertEqual(result["general_boarding_candidate"], general)
                self.assertEqual(result["wheelchair_boarding_candidate"], wheelchair)
                self.assertEqual(result["stop_pick_drop_derived"], derived)
                self.assertEqual(result["boarding_code_assumed"], derived == 99)

    def test_stairs_and_equipment_are_retained_but_mode_candidates_differ(self):
        network = SpatialDataset("network")
        kinds = ["Staircase", "Escalator", "Travelator", "Stairlift", "M_Stairlift", "Footway", "Ramp", None]
        network.add("FeatureType_label", kinds)
        network.add("WheelchairBarrier_bool", [False, False, False, False, False, True, None, False], "bool")
        report = ValidationReport()
        add_network_candidates(network, self.policy, report)
        self.assertEqual(len(network), len(kinds))
        self.assertEqual([network.value("general_mode_candidate", i) for i in range(len(network))],
                         [True, True, True, False, False, True, True, None])
        self.assertEqual([network.value("wheelchair_mode_candidate", i) for i in range(len(network))],
                         [False, False, False, True, True, False, None, None])
        self.assertEqual(report.checks["network:mode_candidates"]["rows_removed"], 0)

    def test_geodataframe_storage_loader_preserves_3d_nulls_ids_and_dates(self):
        dataset = SpatialDataset("network", geometry_type="MultiLineString Z", vertical_crs="EPSG:5738")
        dataset.add("id", ["path:one", "path:two"])
        dataset.add("integer_reference", [117, None], "int64")
        dataset.add("barrier", [False, None], "bool")
        dataset.add("timestamp", ["2026-01-01T00:00:00+08:00", None], "timestamp_text")
        dataset.geometry = np.array([shapely.MultiLineString([[(830000, 820000, 3), (830000, 820000, 7)]]),
                                     shapely.MultiLineString([[(830002, 820002, 1), (830003, 820003, 2)]])], dtype=object)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = ValidationReport()
            write_spatial(root / "harmonised.gpkg", [dataset], report)
            write_json(root / "schema.json", {"spatial_layers": {"network": schema_for(dataset, {})}})
            frame = read_geodataframe(root, "network")
            self.assertIsInstance(frame, gpd.GeoDataFrame)
            self.assertEqual(str(frame["integer_reference"].dtype), "Int64")
            self.assertEqual(str(frame["barrier"].dtype), "boolean")
            self.assertEqual(frame["integer_reference"].iloc[0], 117)
            self.assertTrue(frame["integer_reference"].isna().iloc[1])
            self.assertTrue(shapely.has_z(frame.geometry.array).all())
            self.assertEqual(frame.attrs["vertical_crs"], "EPSG:5738")
            verify_geodataframes(root, [dataset], report)
            self.assertFalse(report.errors)

    def test_failed_output_location_migration_restores_previous_registry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old = root / "old"
            new = root / "new"
            old.mkdir()
            new.mkdir()
            write_json(old / "entity_ids.json", {"old": "identity"})
            write_json(new / "entity_ids.json", {"new": "identity"})
            registry = root / "config/entity_ids.json"
            registry.parent.mkdir()
            registry.symlink_to("../old/entity_ids.json")
            current = root / "outputs/current"
            original_replace = os.replace
            def fail_current(src, dst):
                if Path(dst) == current:
                    raise OSError("simulated publication failure")
                return original_replace(src, dst)
            with patch("estate_ranking.export.os.replace", side_effect=fail_current):
                with self.assertRaisesRegex(OSError, "publication failure"):
                    publish_run(new, current, registry, ["../old/entity_ids.json"])
            self.assertEqual(os.readlink(registry), "../old/entity_ids.json")
            self.assertFalse(current.exists())
            self.assertEqual(json.loads(registry.read_text()), {"old": "identity"})
            publish_run(new, current, registry, ["../old/entity_ids.json"])
            self.assertEqual(current.resolve(), new.resolve())
            self.assertEqual(json.loads(registry.read_text()), {"new": "identity"})

    def test_rebuilt_masters_attach_physical_ids_and_roundtrip_evidence_tables(self):
        files, accounting = prepare(WORK)
        exits = load_mtr_exits(WORK / "original_data/mtr_access_points.geojson")
        railway = load_mtr_exits(WORK / "original_data/railway_stations.geojson", "railway_stations")
        report = ValidationReport()
        tables, review = attach_masters(exits, railway, files, accounting, self.policy, report)
        self.assertFalse(report.errors)
        self.assertEqual(set(exits.columns["station_match_status"]), {"matched"})
        self.assertEqual(set(railway.columns["station_match_status"]), {"matched"})
        self.assertEqual(len(review), accounting["access_points_without_exit_codes"])
        self.assertTrue(all(r["issue"] == "exit_code_unspecified" for r in review))
        self.assertEqual(int(exits.columns["wheelchair_mode_candidate"].sum()), accounting["mobility_access_records"])
        self.assertLess(int(exits.columns["general_mode_candidate"].sum()), len(exits))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_checked(root / "mtr_master", files)
            write_sqlite(root / "references.sqlite", tables, report)
            self.assertFalse(report.errors)


if __name__ == "__main__":
    unittest.main()
