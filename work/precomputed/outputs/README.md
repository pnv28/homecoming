# Prepared Step 1 outputs

The latest complete, validated output is in [current/](current/). Successful snapshots are stored in `runs/`. The current full run is `20261014T090829Z-20d0139c`: **476,153 spatial records, zero errors and 14 warning groups; the repository suite now passes 151 tests**.

The six spatial datasets are actual GeoPandas GeoDataFrames when loaded through the public API. They are persisted as layers in [harmonised.gpkg](current/harmonised.gpkg): `network`, `estates`, `hospitals`, `mtr_exits`, `railway_stations` and `bus_stops`. The network retains all original XYZ vertices. `schema.json` restores nullable column types, and height metadata is retained separately from horizontal EPSG:2326.

From `work/`, run Python with `PYTHONPATH=src ../.venv/bin/python`, then:

```python
from estate_ranking.export import read_outputs, read_geodataframe

frames = read_outputs()  # dictionary of six geopandas.GeoDataFrame objects
estates = frames["estates"]
network = read_geodataframe("precomputed/outputs/current", "network")
print(network.crs)                       # EPSG:2326
print(network.attrs["vertical_crs"])     # EPSG:5738
```

Other files in the selected run:

- [reference_tables.sqlite](current/reference_tables.sqlite): sixteen preserved nonspatial reference/evidence tables, including derived boarding flags alongside raw source codes.
- [mtr_master/](current/mtr_master/): eight physical-station/access/dictionary/review JSON files; these are also integrated into the GeoPackage/SQLite relationships.
- [model_policy.json](current/model_policy.json): exact agreed modelling rules used for candidate preparation and recorded for later routing.
- [schema.json](current/schema.json): field types, missing-value rules, CRS and source definitions.
- [source_manifest.json](current/source_manifest.json): all 23 selected input hashes, software versions, assumptions and output interface.
- [validation_report.md](current/validation_report.md) and [validation_report.json](current/validation_report.json): complete preservation checks and remaining source gaps.
- [Historical warning explanation](../history/step_1/20261013T121410Z-c823aaf9/warnings_explained.md): explanation for the earlier snapshot; current decisions and warning counts come from the selected validation report and project context.
- [Historical independent audit](../history/step_1/20261013T121410Z-c823aaf9/step_1_recheck.json): verification performed on the earlier snapshot before cleanup.
- [mtr_match_review.csv](current/mtr_match_review.csv): ten unnamed source exit codes; their locations and physical station links are known.
- [entity_ids.json](current/entity_ids.json): stable estate/hospital identity snapshot.
- [rejected_records.jsonl](current/rejected_records.jsonl): blocking-record diagnostics, empty for this successful run.
- [SUCCESS.json](current/SUCCESS.json): successful-run identity/completion marker.

All source rows remain available. `general_mode_candidate`, `wheelchair_mode_candidate` and boarding-candidate fields are preparation flags, not computed routes or reachability. Step 2 now implements Tobler/sampling route costs and lift identity states; Step 3 implements destination attachments and Step 4 caches journeys; final ranking remains deferred. Actual remaining MTR/network reference gaps stay visible; accepted assumptions are not converted into publisher facts.

The standalone MTR command writes its independent output to `outputs/mtr_master/` and snapshots to `outputs/mtr_master_runs/`. The MTR snapshot embedded in `current/` belongs to that Step 1 run. The older `precomputed/mtr_master` bookmark points to the selected Step 1 snapshot's master folder; compact historical metadata remains under `../history/`, while superseded full build artifacts were removed at the user's request.

The selected pedestrian graph is [step_2/current](step_2/current/), run `20261016T075559Z-119a5636`, paired with Step 3 `20261016T080509Z-4c604c82` through [the rebuild registry](rebuild/current.json). Its frozen Step 1 dependency is retained. See the [cleanup inventory](../history/cleanup_20261014.json) for the removed superseded snapshots and failed staging output.


The selected journey cache is [step_4/current](step_4/current/), run `20261016T102523Z-8e69faad`. It contains 10,736 shared hospital-distance pairs, 976 primary and 976 baseline transport-group rows, all exact tied winners and 931 baseline comparisons to primary winners. Readers return GeoDataFrames without running Dijkstra. See [the Step 4 guide](../../instructions/step_4/step_4_implementation.md) and [validation](step_4/current/validation_report.json). Two hospital-only overrides correct Kwai Luen and Chun Shek; graph and transport outputs are unchanged and Kam Peng remains unavailable. The [Step 5 plan](../../instructions/step_5/step_5_plan.md) records agreed scaling, weights and incomplete ordering; ranking implementation is pending.
