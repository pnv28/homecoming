# Step 1 implementation plan: ingest and harmonise the housing-ranking data

> **Archived development guide.** This copy preserves the original implementation record, workspace paths, commands, and relative links. Some linked plans, project-context documents, and reports were omitted from the standalone application, so those links may not resolve here.
>
> See [this guide in its original location on `development`](https://github.com/pnv28/homecoming/blob/development/work/instructions/step_1/step_1_implementation_plan.md), the [development plans and project context](https://github.com/pnv28/homecoming/tree/development/work/instructions), and the [development reports](https://github.com/pnv28/homecoming/tree/development/work/precomputed/docs). For current standalone usage and implementation status, follow the [README](../../README.md) and [current implementation status](../implementation-status.md).

> **Latest decisions:** Read [the project context and agent handoff](../project_context_and_decisions.md). It records the user's later assumptions and cost-model choices, which override earlier unresolved questions or suggested defaults in this document. Implementation status is distinguished from agreed policy.

Prepared 13 October 2026 after inspecting the local files with the repository's `.venv`.

**Documentation update — 14 October 2026:** accept the existing 276 mobility access points as the complete wheelchair MTR target pool; accept the three equipment-description differences as mobility access without exact ramp/lift reconciliation; use the latest Castle Peak Hospital site amendment; ignore missing terminal/floor/building references as non-blocking investigation tasks. The implementation and saved run below predate these decisions. A new run is not claimed by this documentation update.

Rechecked from original inputs on 13 October 2026 after today's policy decisions, physical MTR integration, candidate/boarding preparation and the GeoDataFrame output requirement. Successful run `20261013T121410Z-c823aaf9` has 476,153 spatial records, zero errors, 14 warning groups and 31 passing tests. All six outputs reopened as actual GeoDataFrames, all sixteen reference tables and eight MTR JSON files passed read-back checks, and all 23 source hashes were rechecked. See `work/precomputed/outputs/current/validation_report.md`. Actual remaining evidence gaps and later graph/routing/ranking work stay unchecked in the human-readable plan.

## Objective and scope

Implement **Step 1, “Harmonise data (`ingest.py`, `harmonise.py`)”**, in `estate_ranking_design.md`. The result will be separate, consistent spatial datasets ready for graph construction and point snapping, with a source manifest and validation report.

**Always-open assumption (user instruction):** All routes are assumed open at every time of day and on every date. Access schedules are outside the algorithm: do not load or export `AccessTime` or `AccessTimeDetails`, evaluate opening/closing hours, check schedule references, or request a journey date/time. Preserve an original `AccessTimeID` only as an unused source attribute for traceability; it must not affect route eligibility, cost, or ranking. This assumption concerns opening hours; stairs, gradients, physical barriers, direction, and other non-schedule suitability rules still apply in their respective later stages.

Step 1 includes loading, coordinate harmonisation, field standardisation, Housing Authority district assignment, MTR table reconciliation, and validation. Graph construction, parameter-dependent path filtering, edge weights, snapping, shortest paths, and ranking belong to later steps. Preserve information needed by those steps rather than applying their policies during ingestion. The latest policy retains stairs generally and excludes stairs/escalators/travelators only in future wheelchair mode.

All new code and outputs live under `work/`. Use the repository-root `.venv/bin/python` and preserve original inputs. GeoPandas/pandas were installed through an approved request for the new output requirement. No Homebrew packages were installed. Further missing dependencies require explanation and permission.

## What the local inspection established

| Dataset | Preferred input | Observed contents and implications |
|---|---|---|
| Estates | `work/original_data/prh-estates (1).json` | 244 estates; multilingual names, administrative district, map latitude/longitude, block names/counts, and other metadata. No block coordinates or entrance coordinates in the inspected schema. |
| Hospitals | `work/original_data/facility-hosp.json` | 44 institutions; English/traditional/simplified Chinese names, coordinates, cluster, address, and A&E yes/no fields. |
| Pedestrian network | `work/original_data/3D_Pedestrian_Network_FGDB.zip` | Contains `3DPN_P2.gdb`; `PedestrianRoute` has 465,892 `MultiLineString Z` features. Horizontal CRS is EPSG:2326; vertical CRS is HKPD height, EPSG:5738. |
| Network support tables | Same geodatabase | Seven nonspatial tables exist in the source. Load only the five non-schedule tables: terminal, floor, building, site, and distance-post references. Skip `AccessTime` and `AccessTimeDetails`. No separate node layer among the eight listed layers. |
| MTR access points | `work/original_data/mtr_access_points.geojson` | 611 records; native `GEONAMEID`, station/site names, entrance names, access subcategory, WGS84 geometry, and HK1980 easting/northing attributes. |
| Railway station reference | `work/original_data/railway_stations.geojson` | 98 records. Station reference points, not entrance locations or a guaranteed match to the station CSV. |
| Bus/minibus stop list | `work/original_data/bus_stops.json` | 9,264 distinct stop IDs; includes 4,776 GMB-labelled stops, operator lists and flags. This is broader than the older bus-only audit. |
| Original route-stop records | `work/original_data/JSON_BUS.json`, `work/original_data/JSON_GMB.json` | 56,209 bus rows and 13,155 GMB rows. Useful for validating the stop list and preserving service/pickup evidence. Read using `utf-8-sig`: a BOM is present in at least the bus input. |
| MTR CSV references | `data/organized/core/mtr/` | `mtr_lines_and_stations.csv`, `barrier_free_facilities.csv`, `barrier_free_facility_category.csv`. The original accessibility CSV has empty exit-coordinate fields. |
| Housing district crosswalk | `analysis/maps/estate_housing_district_crosswalk.csv` | Covers all 244 current estate names: Urban 109, Extended Urban 70, New Territories 60, Islands 5. |
| Source documentation | Six provider PDFs in `work/original_data/`; existing reports under `analysis/` | 3DPN dictionary confirms radians and horizontal metres; iGeoCom confirms WGS84 geometry/HK1980 attributes. Estate, hospital and bus specifications define latitude/longitude but do not explicitly name a datum. |

Read `whole_chat_export.md` together with the design. In particular, coordinate harmonisation does not create a graph, and point locations must remain available separately from future snapped locations.

## Implementation choices

### Python libraries and output format

Use the repository's Python 3.9.6 `.venv`: Pyogrio 0.11.1, Shapely 2.0.7, PyProj 3.6.1, NumPy 2.0.2, pypdf 6.20.0, GeoPandas 1.0.1 and pandas 2.3.3. GeoPandas/pandas and their missing dependencies were installed with approval to satisfy the user's GeoDataFrame requirement. Versions are pinned in `work/requirements.txt`; further installations still require permission. No Homebrew packages are involved.

**Public spatial outputs are actual GeoPandas GeoDataFrames.** Persist six layers in `harmonised.gpkg`, then use `read_outputs()` or `read_geodataframe(directory, layer)` to load them with nullable pandas types restored from `schema.json`. Keep original Z/parts/vertices, EPSG:2326 horizontal CRS, HKPD vertical metadata and exact timestamp text. Internal `SpatialDataset`/`Table` arrays remain ingestion/export containers; future consumers use the GeoDataFrame interface.

Write reference tables to SQLite and modelling/source/review records to JSON/CSV. GeoPackage avoids a PyArrow dependency. Round-trip every stored value through both the storage engine and the actual GeoDataFrame loader. Verify IDs, schema, nulls, unicode, timestamps, CRS and exact geometry WKB. The latest full rerun completed those checks for all 476,153 spatial records and all 16 reference tables.

**Location:** `work/precomputed/outputs/` is a real directory with successful `runs/` snapshots and a `current/` link. Only fully checked candidates are selected. Cache/staging stays outside finished outputs, and successful outputs remain trackable in Git. A tested one-time migration moves the local identity-registry link to `outputs/current/entity_ids.json` without losing IDs; failed publication restores its previous link.

### Coordinate policy

- All working X/Y coordinates use **EPSG:2326, in metres**, with X=easting and Y=northing.
- Original longitude/latitude and source attributes remain available for audit and display.
- Use `Transformer.from_crs(..., always_xy=True)` for direct PyProj transformations.
- Confirm a source CRS from metadata or documented coordinate fields before transforming. Plausible values alone are a diagnostic, not sufficient CRS evidence. The supplied estate, hospital and bus specifications confirm latitude/longitude fields but do not explicitly name their datum; retain the WGS84 assumptions for these inputs. The iGeoCom dictionary explicitly confirms WGS84 geometry and HK1980 attributes.
- For JSON point lists without embedded CRS metadata, record the source documentation supporting WGS84. If that evidence is unavailable locally, record a clearly labelled WGS84 assumption in configuration and the validation report and check it against independent projected/reference coordinates where possible. Do not silently assign a CRS. An input with neither supported CRS nor an explicit accepted assumption remains unresolved and stops publication.
- The network already uses HK1980 Grid horizontally. Do not transform its Z coordinates or discard them. Treat HKPD height as separate vertical metadata; do not claim that a two-dimensional transformation converts vertical datums.
- Facility points have unknown heights. Do not invent Z=0 or sample a terrain raster during Step 1.
- iGeoCom's WGS84 geometry will be the canonical point source; compare its projected coordinates with supplied easting/northing. The inspected 611 access records differ by approximately 0.03–1.77 m, establishing a useful local baseline. Record residuals and investigate outliers rather than averaging the two coordinate representations.

## Implementation sequence

### 1. Make an explicit input inventory

Create `work/config/step_1.json` listing each selected input, source role, expected CRS evidence, and expected schema. Prefer `work/original_data`; use exact paths to the identified supplementary files outside `work` rather than scanning and selecting whichever similarly named file appears first.

Record SHA-256, size, selected archive members, source dates where known, and library versions. Treat file modification time separately from a source publication or download date. This manifest makes it clear which snapshot generated each output and resolves duplicate copies in the parent directory.

For the first implementation, copy the needed MTR CSVs and district crosswalk/documentation into `work/original_data/reference/`, retaining original path and checksums in the manifest. Compare the crosswalk's estate names and coordinates to the current estate file before reuse. Do not import existing scripts that have hard-coded destinations outside `work`.

### 2. Inspect and load the geodatabase

Safely extract the archive to `work/cache/3DPN_P2.gdb`: reject archive paths that escape the cache, confirm the expected `.gdb` directory, and reuse an extraction only when its recorded input hash matches.

Use `pyogrio.list_layers()` and `read_info()` to save the actual layer names, schemas, CRS, feature counts, bounds, geometry dimensions, and available coded domains. Load `PedestrianRoute` using `pyogrio.raw.read()`, in bounded batches if necessary. Read the five non-schedule supporting tables separately without requiring geometries. Record `AccessTime` and `AccessTimeDetails` as intentionally excluded in the source manifest, without reading their records or exporting them.

Preserve `PedestrianRouteID`, all vertices, multipart structure, Z values, and the original attributes. Important fields include `FeatureType`, `Gradient`, `Direction`, `WheelchairBarrier`, `WheelchairAccess`, `Enabled`, `Location`, `FloorID`, `TerminalID`, and `Shape_Length`. Any original `AccessTimeID` is retained solely as an unused source attribute, not decoded or joined.

Keep source codes and add decoded labels using the geodatabase domains. `list_layers()` and `read_info()` do not expose coded domains through the installed Pyogrio public API. The recheck found 18 embedded `GPCodedValueDomain2` XML definitions in this archive's `.gdbtable` files, readable using the standard library; the earlier audit uses this approach too. Implement that bounded metadata extraction separately, record its source, and validate extracted values against observed codes. Existing domain descriptions in `analysis/audit_summary.json` can be a documented fallback, checked against the selected archive. Do not cast coded values directly to Python booleans: for several fields, `1` means true and `2` means false. `WheelchairAccess` describes an accessible entrance connection; it is not a universal path-usability flag.

Preserve `Gradient` as `gradient_raw`, with the confirmed unit **radians** from `3DPN_DataDictionary_v2.2.pdf`, PDF page 12. Retain `Shape_Length` as the confirmed **horizontal XY polyline length in metres**, defined on PDF page 14. The pipeline verifies these definitions against the selected PDF and compares every source length with the preserved XY geometry; all 465,892 current lengths match exactly. The portal metadata PDF confirms the horizontal CRS but does not supply these field definitions.

Gradient sign convention and within-path aggregation are not explicitly documented. All current source gradients are nonnegative, despite both rising and falling vertex orders. Do not use the permitted-travel `Direction` field as a slope sign. Step 2 must adopt a documented directional-slope/aggregation rule, deriving uphill/downhill from ordered Z coordinates where appropriate. Confirmed radians can be used in an angle-based penalty, or converted with `tan(angle)` for a rise/run-based model; routing policy itself is outside Step 1.

Assume every route is always open. Do not inspect opening/closing schedules, flag schedule gaps, or add schedule-based restrictions in this or later stages.

No path filtering, splitting, endpoint merging, or planar-intersection creation occurs here. Coincident X/Y coordinates at different heights must remain distinct for later topology work.

### 3. Standardise the estate and hospital points

Load JSON with the standard library; retain the source record and extract typed fields into the common schema. Decode HTML entities and convert `<br>` into readable separators in display names, while retaining raw text.

For estates:

- Extract English/traditional/simplified Chinese names, source administrative district, region, map coordinates, and block metadata.
- Set `location_role="estate_map_point"`; do not describe it as a gate or block entrance.
- Join the existing **estate allocation lookup** (`work/original_data/reference/estate_housing_district_crosswalk.csv`, copied from `analysis/maps/estate_housing_district_crosswalk.csv`) to add a separate `housing_district` field. Here “crosswalk” means a data mapping table, not a physical pedestrian crossing. Its latitude/longitude are copied estate map points: all 244 match the estate JSON exactly. Use estate JSON geometry as canonical; lookup coordinate comparison checks identity/snapshot consistency and does not supply entrance or road-crossing locations. Match exact source names, require a unique row, check administrative district/coordinates, and preserve unresolved matches as blocking diagnostics.
- Preserve the estate allocation lookup provenance and its limitations: town boundaries for Tung Chung and Tseung Kwan O are derived geographic proxies, not HA-issued allocation polygons. Avoid a blanket administrative-district mapping for Islands or Sai Kung.

For hospitals:

- Extract multilingual institution names, cluster, address, coordinates, and `has_ae` as a nullable boolean.
- Set `location_role="institution_map_point"` and retain entrance uncertainty.
- Preserve all 44 supplied institutions. The user has settled no-preference hospital scope as all 44, without an A&E-only filter. Preferred-hospital choice is applied in the later query stage.

Where the input has no native entity ID, create and persist an ID registry using source namespace and an explicit identity key, initially the exact English name. Detect collisions; do not assign IDs from row position. Handle future renames through recorded aliases rather than silently creating a different identity.

Keep `work/config/entity_ids.json` as a managed link to the selected run's registry snapshot. Save the snapshot in each successful output and restore it on a fresh checkout if the local link is absent. Use deterministic initial IDs from the namespace and identity key, and preserve recorded aliases on subsequent runs. Stage registry updates with the output so a failed run cannot change existing entity identities.

### 4. Reconcile MTR using physical station masters

Read the three station/facility/category CSVs using `utf-8-sig`, and decode the relevant PDFs in `mtr DataDictionary.zip`. Facility Station_No refers to the old CSV Station ID; Key refers to category Item_Code; Y/N means available/unavailable. The facility coordinate field is explicitly not in use. iGeoCom station/access geometries supply coordinates.

Build the masters directly from the configured source snapshot through `mtr_master.prepare()`, not from a potentially stale output link. Use stable MTR-S/MTR-A IDs based on native station/access GEONAMEIDs. All 98 physical station points and 611 access points match; map all 100 legacy CSV IDs separately. Keep lines/routes out of the masters and preserve source CSVs/hashes and blank-row accounting. No source-ID equivalence with TerminalID is assumed.

Use `mtr_prepare.attach_masters()` to attach physical station IDs, exit codes and mobility evidence to the spatial layers and create the SQLite relationships. Include 276 mobility records: 249 explicit subcategories plus 27 positive named-exit supplements. Preserve all 611 points, 3,564 facilities and the full review. Do not spread paid-area/station-level facilities across external entrances or equate exit-level equipment evidence with precise equipment coordinates.

General mode starts with all 611 mapped access points and excludes exclusively stair-lift/wheelchair-aid equipment. Wheelchair mode accepts the existing 276 mobility points as its complete target pool for this model; no extra entrance research or complete station coverage is required. The other 335 points stay general candidates and outside wheelchair targets. Candidate flags prepare selection, not path connectivity. Preserve source coordinates, assisted types, exit-only descriptions and coincident identities. Accept Tin Shui Wai C, Diamond Hill A2 and LOHAS Park B as mobility access without reconciling their ramp/lift/same-level descriptions; preserve both descriptions without selecting an unsupported exact type. Ten genuinely unnamed exit codes remain null.

Legacy override CSVs are empty. Nonempty legacy overrides require explicit migration to physical IDs; do not silently ignore them or apply line-specific IDs. No overrides are needed for this snapshot's physical-name matches.

Save and verify all eight JSON files in the run's `mtr_master/` folder and use the same records for its database. Check physical station foreign keys and facility links. Report remaining IDs 70/888 (72 rows), unknown/unlocated evidence, three equipment differences and three stations without mapped mobility access. `mtr_match_review.csv` now contains ten unnamed codes rather than the old 45 matching cases. Historical runs keep their original reports.

The latest decisions accept the three equipment differences and the 276-point coverage as modelling choices. Keep the original review evidence, but do not require those descriptions or unlocated facilities to be resolved before using the accepted target pool. Route direction, physical path eligibility and connectivity still apply.

### 5. Standardise and verify the bus/minibus stop list

Use the 9,264-row `bus_stops.json` as the preferred point list. Preserve `stop_id` as a source identifier, operators as a list, and `GMB`, `KMB`, `CTB` flags. Normalise names without overwriting raw names. Keep different IDs separate even when coordinates or names coincide.

Validate the derived list against both supplied route-stop datasets: compare ID sets, coordinates, operator unions, and naming variants. Report inconsistent coordinates for one ID rather than selecting the first unnoticed. Preserve route/service evidence in a related nonspatial table or a lossless reference to raw records, including `stopPickDrop`, `routeId`, `routeSeq`, `stopSeq`, `serviceMode`, and `lastUpdateDate`.

Recheck result: the local list exactly matches the union of raw stop IDs, coordinates, and operator sets, with no conflicting coordinates for a stop ID. Its original builder used `JSON_BUS.json.1` in the parent directory; that file's SHA-256 equals `work/original_data/JSON_BUS.json`, and the parent GMB file also equals its `work/original_data` copy. Record this provenance rather than assuming similar filenames contain the same snapshot.

Preserve raw pickup/drop-off codes and source accessibility evidence. Later derived selection follows the accepted user policy: unknown codes become 99 and are assumed both pickup/drop-off; KMB/CTB are wheelchair-eligible, while GMB is eligible only in general mode. Bus scope is KMB/CTB/GMB. Other operators remain preserved as source data but are outside this bus subcost. These assumptions do not imply new provider evidence. Implement filtering after preserving the original data.

### 6. Validate and write reproducible outputs

Run validation before finalising outputs. Write to a staging directory and promote a complete, consistent result only after the required checks pass. Leave the previous successful output intact on failure.

Make any record exceeding a configured coordinate-residual or crosswalk-coordinate tolerance an explicit error or review item, with tolerances and units recorded in configuration. The current crosswalk has exact coordinate matches for all 244 estates. Broad geographic bounds are only a sanity check and cannot establish district membership or accurate alignment by themselves.

**Errors that stop publication:** missing required inputs or fields; unsupported/unresolved source CRS for transformation; duplicate primary IDs; non-finite required coordinates; empty/wrong geometry types in the usable output; missing/ambiguous housing-district assignments; failed read/write preservation checks. Retain offending records and diagnostics in a rejection report; never silently discard them.

**Issues that remain visible without stopping ingestion:** unmatched MTR station/exit references; unspecified access categories; entrance uncertainty; unconfirmed gradient semantics; suspicious source publication/update dates; overlapping coordinates. Source publication/update dates describe dataset provenance and do not control route opening hours. Mark them explicitly so later stages can enforce their own requirements.

**Latest accepted-warning treatment:** missing terminal, floor and building references are non-blocking. Preserve their IDs, path geometry and diagnostics, but do not require investigation or drop affected paths because of these missing references. Normal height/level/connectivity checks remain necessary. Missing site and distance-post/path references are separate findings not covered by this instruction. For the Castle Peak Hospital site versions, select the record with the latest parsed `LastAmendmentDate` (13 July 2026, SiteID 1503020249), preserve both raw records, and ensure a canonical join does not duplicate paths. This selection is planned; the saved run still preserves both versions without a preferred one.

Checks will cover:

- Row-count reconciliation between inputs, valid outputs, and quarantined records. The current counts above are snapshot baselines, not permanent hard-coded dataset sizes.
- Unique entity IDs, required fields, known code domains, multilingual string handling, and null preservation.
- Geometry type, nonempty geometry, finite coordinates, plausible Hong Kong bounds, and geographic-to-projected round trips. Use documented broad bounds as a sanity check; avoid rejecting coastal points solely because a land polygon excludes them.
- Network multipart and Z preservation, including vertical lift geometries whose planar length can be zero. Do not apply polygon repair or two-dimensional zero-length rejection indiscriminately to 3D paths.
- Uniqueness and referential integrity in non-schedule network references, station, category, and district joins, respecting station-line relationships. Do not validate `AccessTimeID` references or schedule tables.
- Current crosswalk completeness and counts; bus-list agreement with raw records; iGeoCom projected-coordinate residuals.
- Output round trips: IDs, counts, nulls, CRS, field types, multipart structure, and vertex/Z coordinates remain intact within a documented numerical tolerance.

Network connectivity analysis is a Step 2 check because it needs an actual graph and an access policy. Step 1 reports the absence of a node layer and preserves topology evidence, but does not claim routes are connected.

## Proposed code and output layout

```text
work/
  config/
    step_1.json                  # input/output selections
    routing_policy.json          # accepted modelling decisions
    entity_ids.json              # local link to selected registry snapshot
    mtr_*_overrides.csv           # empty legacy overrides; migrate before use
  original_data/
    ...original inputs and provider dictionaries...
    reference/                   # verified supplementary copies
  cache/                         # extraction, staging and failure diagnostics
  src/estate_ranking/
    models.py                    # internal arrays and null masks
    ingest.py, harmonise.py       # sources, coordinates and preserved data
    mtr_master.py, mtr_prepare.py # physical station masters and database integration
    policy.py                    # candidate and derived boarding preparation
    validate.py, export.py        # full checks and GeoDataFrame output API
    step_1.py                    # command-line orchestration
  tests/                         # preservation, policy, identity and failure fixtures
  precomputed/outputs/
    runs/<run_id>/               # complete successful snapshots
    current/                     # selected successful snapshot
      harmonised.gpkg            # six persisted GeoDataFrame layers
      reference_tables.sqlite    # sixteen nonspatial reference/evidence tables
      mtr_master/                # eight checked MTR JSON files
      model_policy.json          # the exact policy snapshot used
      schema.json, source_manifest.json
      validation_report.md, validation_report.json
      mtr_match_review.csv, rejected_records.jsonl
      entity_ids.json, SUCCESS.json
```

Common spatial fields: `id`, `source_id` where available, `name`, `name_en`, `name_zh_hant`, `name_zh_hans` where available, `entity_type`, geometry, and provenance reference. Include `name` to retain the original design's `id`/`name`/`geometry` interface, using the available English name first and a documented Chinese fallback. Names may be missing for network paths; do not manufacture them. Dataset metadata carries CRS; type-specific fields retain the distinctions described above. Store raw source attributes or a lossless source-record reference alongside normalised fields.

Suggested function responsibilities:

| Function | Responsibility |
|---|---|
| `inventory_sources(config)` | Resolve explicit files and record hashes/provenance. |
| `inspect_network(gdb_path)` | Discover layers, CRS, schema, counts and domains. |
| `load_network(gdb_path)` | Return spatial paths and five non-schedule support tables; skip the two access-schedule tables. |
| `load_estates()`, `load_hospitals()`, `load_mtr_exits()`, `load_bus_stops()` | Parse each input without assigning routing policy. |
| `to_common_crs(dataset, target="EPSG:2326")` | Transform X/Y with explicit source CRS and preserved vertical metadata. |
| `assign_housing_districts(estates, crosswalk)` | Add the four-category district field with join diagnostics. |
| `mtr_master.prepare()` / `mtr_prepare.attach_masters()` | Build physical masters and attach matching IDs/evidence to layers and tables. |
| `validate(datasets, tables, manifest)` | Return structured errors, warnings and reconciliation totals. |
| `write_outputs(...)` | Stage outputs, verify round trips and finalise the successful run. |

Planned command, from the new working directory:

```sh
cd work
PYTHONPATH=src ../.venv/bin/python -m estate_ranking.step_1 --config config/step_1.json
```

Resolve input and output paths relative to `work` or the configuration's declared project root, never implicitly to whichever directory starts Python.

## Implementation milestones and completion criteria

`[X]` marks a completed action or an explicitly labelled recorded decision. `[ ]` marks unfinished implementation or unresolved source evidence. Recording an accepted limitation does not repair the source data.

- [X] **1. Input inventory and writer proof:** explicit sources, environment check, safe extraction, small geometry/table round trip with Z and nulls preserved.
- [X] **2. Core loaders and coordinate harmonisation:** network/five non-schedule support tables and all facility/estate datasets loaded through the common container.
- [X] **3. District and MTR relationships:** verified crosswalk, match evidence, override mechanism and unresolved-case exports; bus-list reconciliation complete. Reporting source gaps does not resolve them.
- [X] **4. Validation and reproducible export:** reports, manifest and outputs produced by one command, with focused fixture checks and a full real-data run.

### Latest warning-review checklist — 14 October 2026

- [X] **Decision recorded: MTR coverage.** Accept the existing 276 mobility access points as the complete wheelchair target pool; retain the other 335 as general-mode candidates only, subject to general equipment rules.
- [X] **Decision recorded: equipment differences.** Accept Tin Shui Wai C, Diamond Hill A2 and LOHAS Park B as mobility access without exact ramp/lift/same-level reconciliation.
- [X] **Decision recorded: Castle Peak Hospital version.** Use SiteID 1503020249's latest `LastAmendmentDate`, 13 July 2026, while preserving both source versions.
- [X] **Decision recorded: terminal/floor/building warnings.** Ignore these non-blocking findings as investigation tasks; preserve paths, source IDs and diagnostics. Normal height/connectivity checks still apply.
- [ ] **Implementation pending.** Apply the latest decisions to executable policy/accepted-warning treatment, implement the Castle Peak Hospital preferred-version selection, verify it and generate a new checked output snapshot.
- [ ] **Source evidence still unresolved.** Unnamed exit codes, IDs 70/888, unlocated facility descriptions and other missing references remain source gaps. The accepted limitations above are not mandatory investigation tasks; assess other relationships only where a required later operation needs them.
- [ ] **Later-stage implementation.** Build graph connections, route costs, subcosts and final ranking; the wheelchair speed model and final combining method remain deferred.

The fixture checks should exercise axis order, Z preservation for lifts and multipart paths, `1`/`2` code interpretation, duplicate identifiers, ambiguous joins, blank MTR subcategories, and colocated bus stops with different IDs. These protect transformations that could otherwise produce plausible but incorrect routing inputs.

Step 1 is complete when every selected source record is accounted for (the two access-schedule tables are explicitly excluded), all published spatial layers share EPSG:2326 horizontally, original network heights survive, all 244 estates have one documented housing district, and unresolved accessibility or source-semantic questions are explicit in the report. MTR records with uncertain matches remain in the output with flags. No missing evidence is converted into a claim of accessibility. This completes ingestion and harmonisation; a remaining gradient interpretation or route-eligibility issue must still be resolved before the affected Step 2 or Step 3 operation proceeds.

## Questions carried forward to later steps

The current, itemised resolution register is in [the human-readable plan](step_1_implementation_human_readable.md#resolution-register-what-is-confirmed-and-what-remains); the [handoff](../project_context_and_decisions.md) records later accepted modelling assumptions. The separate MTR masters resolve the physical station identities behind the older 28 ambiguous and 5 unmatched cases. Two of the old 12 exit-code cases now parse; ten genuinely unnamed codes remain null. Of 362 unspecified categories, 27 now have positive named-exit facility evidence and 335 remain unknown. Facility IDs 70/888 remain unidentified; three equipment-description differences and specific unlocated facility/exit relationships remain in the new review. The older database/review remain historical. The rerun embeds the physical masters and uses them in its new database, with ten unnamed-code review records.


Access schedules are already decided: assume all routes are always open, with no date/time inputs or schedule checks. The remaining questions below do not prevent writing the Step 1 pipeline:

- Gradient/length units and use are settled: supplied magnitude with height-derived sign; at most two rounds of four random interpolated path samples when endpoints are level; ten-point flat classification if both rounds remain level; repeatable samples and summed local interval times. Standard Tobler is adopted for walking using tan(signed angle). Implement/test these rules; wheelchair speed is deferred.
- General routes retain stairs/escalators/travelators; wheelchair routes exclude them. Lifts/stair lifts/wheelchair aids qualify for wheelchair mode, while wheelchair aids and stair lifts are excluded generally. Ordinary lift timing is 30 seconds travel plus zero wait, and no maximum ramp-slope cutoff applies for now. WheelchairBarrier=1 is excluded for wheelchair mode. Other equipment timing and actual graph connectivity still need implementation.
- Estate/hospital map-point approximation is accepted; implement sensible connections and topology checks rather than require verified entrance collection.
- MTR physical station matching is resolved. Use the accepted 276-point wheelchair target pool without requiring extra mobility coverage or ramp/lift reconciliation for the three accepted equipment differences. Preserve missing exit labels, facility identities and unlocated descriptions as source unknowns; investigate only if a later feature actually requires those relationships. Do not reopen solved line-ID ambiguity.
- Unknown boarding codes become derived 99, assumed to allow pickup/drop-off, while raw values stay preserved. Step 1 has implemented KMB/CTB/GMB general and KMB/CTB wheelchair boarding candidates without deleting raw records. Route reachability/costs remain later work.
- No-preference hospital scope is all 44 institutions. MTR general mode starts with all 611 access points, subject to general equipment rules; wheelchair mode uses the accepted complete pool of 276 mobility access points. Actual journeys still obey path rules and connectivity. Use minimum reachable route cost within each target group and preserve three separate subcosts, target IDs, units and reachability. Final combination/scaling is deliberately undecided.
- Apply the latest Castle Peak Hospital site-version rule and accepted-warning treatment when implementation resumes. Missing terminal/floor/building references do not require investigation. Updating documentation does not update the saved run or its machine-readable policy snapshot.
- The DTM remains optional for later connector/terrain checks; Step 1 does not resample it or use bare-earth heights to overwrite elevated network geometry.

If documentary gaps require new external data, first identify the exact missing evidence and source. The initial implementation can proceed with local inputs and explicit unknowns.
