# Estate-ranking preparation and pedestrian graphs

> **Latest decisions:** Read [the project context and agent handoff](instructions/project_context_and_decisions.md). It records the user's later assumptions and cost-model choices, which override earlier unresolved questions or suggested defaults in this document. Implementation status is distinguished from agreed policy.


**16 October rebuild:** the complete coordinated rebuild with reviewed fallback times and primary/baseline comparisons passed, including **134 tests**. The fallback is flat walking time plus 6 s/m ascent and 2 s/m descent, shared with wheelchair mode as an explicit approximation. Original geometry and failure evidence remain unchanged; separate baseline time graphs retain original exclusions. To rebuild both stages together, use:

```sh
PYTHONPATH=work/src .venv/bin/python -m estate_ranking.rebuild
```

The public readers select the verified pair through `precomputed/outputs/rebuild/current.json` when present. Each Step 3 run pins its own Step 2 dependency. Use an explicit run directory to inspect historical data. Individual stage builders are for explicit candidate work; a coordinated pair is the default published result.

Step 3 is implemented and fully verified in **`20261016T080509Z-4c604c82`**, pinned to Step 2 **`20261016T075559Z-119a5636`**. It preserves **10,163 facility points**, records **20,814 primary + 20,238 baseline selections**, and publishes six augmented routing graphs. All eligible points attach, with **36 general / 34 wheelchair bus records per scenario beyond 50 m**, including approximate straight connectors up to **5.2 km**. These are flagged; attachment is not proof of a usable journey. Read [the Step 3 guide](instructions/step_3/step_3_implementation.md) and [full-data validation report](precomputed/outputs/step_3/current/validation_report.md). Step 4 now saves journey subcosts; Step 5 ranking implementation remains pending.

```sh
PYTHONPATH=work/src .venv/bin/python -m estate_ranking.step_3
```

```python
from estate_ranking.attachments import read_attached_graph
graph = read_attached_graph(wheelchair=False, metric="time")
# graph.entities / attachments / connectors / terminals preserve source identities and statuses.
```

The audited Step 2 passed a full-data build: **397,225 nodes and 466,406 pieces**, with **465,861 general / 430,496 wheelchair eligible source paths** before splitting. All six primary/baseline matrices passed persistence and shortest-path checks. The validated run is `20261016T075559Z-119a5636`. Its [source/routing audit](precomputed/outputs/step_2/current/source_routing_audit.md) records the repaired endpoint connection, 29 recovered healthy pieces and retained original-source limitations.

Step 2 implementation and review: [instructions/step_2/step_2_implementation.md](instructions/step_2/step_2_implementation.md). The latest plan adopts shared Tobler costs for both modes, excludes disabled paths, and charges 30 seconds per original lift identity on entry. Older deferred-speed notes below describe historical snapshots.

For explicit stage-only candidate work, build all six graphs from the successful Step 1 snapshot, from the repository root (use the coordinated command above for a new selected pair):

```sh
PYTHONPATH=work/src .venv/bin/python -m estate_ranking.step_2
```

Read a saved graph:

```python
from estate_ranking.graph import read_graph, build_graph

graph = read_graph(wheelchair=False, metric="time")  # or metric="distance"
# graph.nodes and graph.edges are actual GeoDataFrames.
# graph.matrix is a SciPy CSR; graph.edge_mapping maps each entry to its source piece.
costs_seconds = graph.costs_from(node_index=0)
```

A time journey starts in the physical node's state with no current lift. Destination costs take the minimum across that node's states; `costs_from` handles both rules. Lift state identities are separate from physical geometry. Preserved source rows, eligibility reasons and source-level cost status are in `graph.physical.sources`. Original sampling evidence remains in `profiles.jsonl`; separate reviewed estimates are in `derived_profiles.jsonl`. Use `read_graph(..., scenario="baseline")` or `read_attached_graph(..., scenario="baseline")` to exclude estimates for time comparisons. `source_routing_audit.json` retains exact source provenance, rejected-cluster routes and unavailable-piece endpoint reachability. Invalid cost intervals are isolated after junction decisions so healthy adjacent geometry remains usable.

Validated Step 2 runs live under `precomputed/outputs/step_2/runs/`; the pair registry selects the compatible runs, with `step_2/current/` retained as a compatibility link. The manifest freezes one resolved Step 1 run and policy. GeoPackage, sparse matrices, mappings, evidence and review reports remain trackable in Git (large artifacts use the repository's Git LFS conventions). Failed candidates stay in cache and preserve the previous selection. Superseded build artifacts were removed at the user's request; compact historical reports are in [precomputed/history](precomputed/history/README.md). The current Step 2 build and its frozen Step 1 dependency remain complete.

Original inputs are stored in `original_data/`, renamed from `data/` at the user's request. Active configuration, code and documentation use the new folder. Historical saved-run manifests retain their paths at the time of that run; resolve an old `work/data/` path through `work/original_data/` when checking those records. The separate repository-root `data/` directory retains its name.

This Python pipeline reads the selected local sources, aligns horizontal locations to Hong Kong 1980 Grid (EPSG:2326), prepares stable identities, adds estate allocation categories, reconciles MTR references, and validates/export the result. It follows both documents in [instructions/step_1](instructions/step_1/).

**All routes are assumed always open.** `AccessTime` and `AccessTimeDetails` are not loaded, checked, or exported. Any original `AccessTimeID` is an inert attribute. The pipeline retains all source records and prepares mode-candidate flags from the agreed rules: general paths retain stairs; wheelchair paths exclude ordinary stairs/escalators/travelators and WheelchairBarrier=1; general equipment excludes stair lifts/wheelchair aids. These are candidates, not connected routes or computed costs.

The latest Step 1 rerun (`20261014T090829Z-20d0139c`) passed with **476,153 spatial records, zero errors and 14 retained warning groups**. The complete repository suite passes **134 tests** after full-data acceptance. See [the recorded test result](precomputed/docs/rebuild_test_report.json), [saved artifact/source preservation audit](precomputed/docs/rebuild_source_preservation.json) and [public-reader checks](precomputed/docs/rebuild_reader_verification.json). All six saved layers were reopened as actual **GeoPandas GeoDataFrames** and every geometry, attribute and null was checked.

From the repository root:

```sh
cd work
PYTHONPATH=src ../.venv/bin/python -m estate_ranking.step_1 --config config/step_1.json
```

The command uses the installed `.venv` packages and needs no installation or network access. Configuration paths are relative to the `work_root` declared in the configuration (resolved from the configuration file), not the current shell directory.

The selected supplementary inputs are copied to `original_data/reference/` and verified against their original checksums. If a reference copy and its selected origin later differ, the run stops so the intended snapshot can be selected explicitly. Source publication/download dates are kept separate from file modification dates; missing source dates remain unknown.

The finished result is available under `precomputed/outputs/current/`:

- `harmonised.gpkg`: six persisted GeoDataFrame layers, including all original network vertices/heights.
- `reference_tables.sqlite`: five non-schedule network tables, MTR relationships, estate crosswalk, and lossless raw bus route-stop records.
- `schema.json`: field types, missing-value rules, CRS, original source schemas and coded domains.
- `source_manifest.json`: selected inputs, hashes, provenance, assumptions and software versions.
- `model_policy.json`: snapshot of [the agreed rules](config/routing_policy.json), including explicit later-stage/deferred choices.
- `mtr_master/`: eight rebuilt MTR JSON files, integrated into this run's spatial layers and reference tables.
- `validation_report.md` and `.json`: checks and remaining issues.
- `mtr_match_review.csv`: ten source access records without named exit codes; physical station matching is complete.
- `rejected_records.jsonl`: blocking-record diagnostics (empty for successful runs).
- `entity_ids.json`: the successful run's persistent identity/alias registry snapshot.

Each candidate run is staged under `cache/step_1_staging/`. Only a run that passes validation and full read-back checks moves to `precomputed/outputs/runs/` and becomes current. `precomputed/outputs/current` is a link to the successful run. `config/entity_ids.json` links to that run's registry, so changing the current-run link publishes both the prepared data and identities together. Failed runs retain diagnostics in cache without changing the previous current result. A local process lock prevents simultaneous runs. Successful precomputed data and reports are not excluded from Git; temporary/cache files and the local registry link are ignored.

The registry supports explicit name aliases through `IdentityRegistry.alias(namespace, new_name, original_name)`. Renames must be recorded deliberately; row order never determines estate/hospital IDs. A fresh Git checkout without the local registry link restores IDs and aliases from the versioned current output snapshot. To change a committed registry, stage the edits in a new candidate snapshot and publish it with a successful run. Do not replace the managed registry link with an unrelated file.

The old MTR override CSVs remain empty. The rerun now uses physical MTR-S station IDs; all 611 access points and 98 stations match without overrides. If a legacy override is added later, the command stops for explicit migration rather than silently ignoring or applying a line-specific ID to the new physical model. Facility station IDs 70/888 remain null and visible in the embedded review. Named-exit equipment evidence does not locate every piece of equipment at each associated point.

Step 1 now rebuilds and embeds the **physical MTR masters** using `original_data/mtr DataDictionary.zip`. A standalone command is also available:

```sh
PYTHONPATH=src ../.venv/bin/python -m estate_ranking.mtr_master
```

The integrated run contains [98 physical stations](precomputed/outputs/current/mtr_master/mtr_station_master.json) and [276 mobility access records](precomputed/outputs/current/mtr_master/mtr_mobility_exit_master.json), with stable source-based IDs and original WGS84 coordinates. Lines/routes do not enter the masters. All 611 access points link to physical stations and all 100 CSV station IDs are mapped separately. All 3,564 facility rows are decoded; the provider coordinate field is not in use. Read [the master guide](precomputed/docs/mtr_master_readme.md) for evidence gaps. Historical saved runs retain their old reports; the new database uses the updated physical relationships.

WGS84 is an explicit, reported assumption for estate, hospital and bus point sources: their supplied provider specifications identify latitude/longitude but do not explicitly name the datum. iGeoCom's dictionary explicitly confirms WGS84 point geometry and HK1980 grid attributes. The original network's HKPD height reference is preserved separately from its horizontal grid. Map points for estates and hospitals remain unverified entrance locations.

The supplied `3DPN_DataDictionary_v2.2.pdf` confirms **Gradient in radians** (PDF page 12) and **SHAPE_Length as horizontal length in metres** (PDF page 14). The pipeline records these definitions and checks every source horizontal length against the preserved XY polyline. Gradient sign convention and within-path aggregation are not explicitly documented. This snapshot has no negative gradient values even though ordered path vertices include both rising and falling paths. Later directional cost calculations must derive uphill/downhill direction from the ordered Z coordinates or adopt a documented policy; the `Direction` field specifies permitted travel, not uphill/downhill sign.

Focused tests, from `work/`:

```sh
PYTHONPATH=src ../.venv/bin/python -m unittest discover -s tests -v
```

Load the actual GeoDataFrame outputs from `work/`:

```python
from estate_ranking.export import read_outputs, read_geodataframe

frames = read_outputs()  # dict of six geopandas.GeoDataFrame objects
estates = frames["estates"]
network = read_geodataframe("precomputed/outputs/current", "network")
```

The loader restores nullable integer/boolean/string types and height metadata from the schema. Network timestamps remain exact text, including timezone suffixes. GeoPandas 1.0.1 and pandas 2.3.3 were installed with approval in the local `.venv`; PyArrow is unnecessary for the GeoPackage format. Internal `SpatialDataset` arrays remain an ingestion implementation detail, not the public spatial output type.

Bus service records retain original `stopPickDrop`, alongside derived unknown code 99 and explicit pickup/dropoff flags. Stop candidates are 8,848 generally and 4,130 for wheelchair scope. No source stop/service is deleted. Network base candidates are 465,887 generally and 430,522 for wheelchair scope, from all 465,892 retained paths. Connectivity and route costs are not computed by Step 1.

iGeoCom's original `EASTING` and `NORTHING` attributes are saved as `source_grid_easting` and `source_grid_northing`, with the original field-name mapping documented in layer metadata. This keeps them separate from the transformed `easting` and `northing` fields: GeoPackage/SQLite treats field names as case-insensitive. The complete original property names and values also remain in each point's `raw_json`.

Reference tables retain native geodatabase FIDs as `source_fid` and a separate `record_id`. Source entity IDs in these tables can have multiple versions: this snapshot has two Castle Peak Hospital site-reference records with the same `SiteID` and different source dates/name capitalisation. Both are preserved and flagged; the pipeline does not silently choose one version. The unique source-record identity is separate from the shared entity reference.


Step 4 is implemented: the [selected journey cache](precomputed/outputs/step_4/current/) saves all shared hospital pairs, both transport modes/scenarios, tied winners, comparisons and paths. Use `estate_ranking.step_4.read_subcosts`, `read_hospital_costs`, `read_transport_comparisons` and `read_route`; all return GeoDataFrames and use cached results without new shortest-path searches. See [the reader/build guide](instructions/step_4/step_4_implementation.md). The hospital-only amendment corrects Kwai Luen and Chun Shek while leaving graph/transport outputs unchanged and Kam Peng unavailable. The [Step 5 plan](instructions/step_5/step_5_plan.md) records bounded scaling, equal-thirds default weights and incomplete ordering; ranking code remains pending.
