# Step 1 implementation plan: ingest and harmonise the housing-ranking data

Prepared 13 October 2026 after inspecting the local files with the repository's `.venv`.

Rechecked against the design and source files on 13 October 2026. The additional checks confirmed exact bus-list reconciliation, exact estate-crosswalk coordinates, readable coded domains in the selected network archive, and a successful GeoPackage round trip with 3D multipart paths and nulls. This document remains an implementation plan; the full pipeline has not been built or run.

## Objective and scope

Implement **Step 1, “Harmonise data (`ingest.py`, `harmonise.py`)”**, in `estate_ranking_design.md`. The result will be separate, consistent spatial datasets ready for graph construction and point snapping, with a source manifest and validation report.

**Always-open assumption (user instruction):** All routes are assumed open at every time of day and on every date. Access schedules are outside the algorithm: do not load or export `AccessTime` or `AccessTimeDetails`, evaluate opening/closing hours, check schedule references, or request a journey date/time. Preserve an original `AccessTimeID` only as an unused source attribute for traceability; it must not affect route eligibility, cost, or ranking. This assumption concerns opening hours; stairs, gradients, physical barriers, direction, and other non-schedule suitability rules still apply in their respective later stages.

Step 1 includes loading, coordinate harmonisation, field standardisation, Housing Authority district assignment, MTR table reconciliation, and validation. Graph construction, stair exclusion, edge weights, snapping, shortest paths, and ranking belong to later steps. Preserve information needed by those steps rather than applying their policies during ingestion.

All new code and outputs will live under `work/`. Use the repository-root `.venv/bin/python`, install nothing during this step, and leave source files unchanged. No Homebrew packages are needed. If implementation reveals a necessary missing dependency, explain it and request permission before installing it.

## What the local inspection established

| Dataset | Preferred input | Observed contents and implications |
|---|---|---|
| Estates | `work/data/prh-estates (1).json` | 244 estates; multilingual names, administrative district, map latitude/longitude, block names/counts, and other metadata. No block coordinates or entrance coordinates in the inspected schema. |
| Hospitals | `work/data/facility-hosp.json` | 44 institutions; English/traditional/simplified Chinese names, coordinates, cluster, address, and A&E yes/no fields. |
| Pedestrian network | `work/data/3D_Pedestrian_Network_FGDB.zip` | Contains `3DPN_P2.gdb`; `PedestrianRoute` has 465,892 `MultiLineString Z` features. Horizontal CRS is EPSG:2326; vertical CRS is HKPD height, EPSG:5738. |
| Network support tables | Same geodatabase | Seven nonspatial tables exist in the source. Load only the five non-schedule tables: terminal, floor, building, site, and distance-post references. Skip `AccessTime` and `AccessTimeDetails`. No separate node layer among the eight listed layers. |
| MTR access points | `work/data/mtr_access_points.geojson` | 611 records; native `GEONAMEID`, station/site names, entrance names, access subcategory, WGS84 geometry, and HK1980 easting/northing attributes. |
| Railway station reference | `work/data/railway_stations.geojson` | 98 records. Station reference points, not entrance locations or a guaranteed match to the station CSV. |
| Bus/minibus stop list | `work/data/bus_stops.json` | 9,264 distinct stop IDs; includes 4,776 GMB-labelled stops, operator lists and flags. This is broader than the older bus-only audit. |
| Original route-stop records | `work/data/JSON_BUS.json`, `work/data/JSON_GMB.json` | 56,209 bus rows and 13,155 GMB rows. Useful for validating the stop list and preserving service/pickup evidence. Read using `utf-8-sig`: a BOM is present in at least the bus input. |
| MTR CSV references | `data/organized/core/mtr/` | `mtr_lines_and_stations.csv`, `barrier_free_facilities.csv`, `barrier_free_facility_category.csv`. The original accessibility CSV has empty exit-coordinate fields. |
| Housing district crosswalk | `analysis/maps/estate_housing_district_crosswalk.csv` | Covers all 244 current estate names: Urban 109, Extended Urban 70, New Territories 60, Islands 5. |
| Source documentation | Both PDFs in `work/data/`; existing reports under `analysis/` | iGeoCom dictionary confirms the two coordinate systems and access subcategory meanings. Network metadata and previous audits are supporting evidence, not substitutes for validating the selected inputs. |

Read `whole_chat_export.md` together with the design. In particular, coordinate harmonisation does not create a graph, and point locations must remain available separately from future snapped locations.

## Implementation choices

### Python libraries and output format

The installed environment runs Python 3.9.6 and contains Pyogrio 0.11.1, Shapely 2.0.7, PyProj 3.6.1, NumPy 2.0.2, and pypdf 6.20.0. GeoPandas, pandas, PyArrow, Fiona, and rasterio are absent. Keep code compatible with Python 3.9, including its type-annotation and standard-library APIs.

Use **Pyogrio's raw reader + NumPy attribute arrays + Shapely geometry arrays + PyProj**. A small in-memory `SpatialDataset` container will carry fields, geometry, horizontal CRS, vertical metadata, and source identity. This serves the same purpose as the design's GeoDataFrames without requiring new packages. Later functions should accept this container through a consistent interface.

Define that contract explicitly: an ordered mapping of named, equal-length attribute arrays; a same-length Shapely geometry array; declared field types and null masks where needed; horizontal CRS; optional vertical CRS; and dataset/source metadata. Nonspatial support tables use the same attribute/type contract without a geometry array. Raw readers can represent nullable integers as floating arrays containing NaN, so use the declared source schema to restore nullable integer fields rather than allowing identifiers to become strings such as `"117.0"`.

Recommended persisted format: **GeoPackage** for spatial layers, and standard-library SQLite/JSON/CSV for nonspatial tables and reports. Verify the installed GDAL GeoPackage writer and Pyogrio raw write API in a small read/write round trip before implementing the full export. Encode list-valued attributes as documented JSON text where necessary; preserve types and nulls. GeoPackage can store projected geometries and network Z values, whereas conventional GeoJSON is intended for geographic coordinates. Keep the original compound CRS WKT and vertical datum explicitly in the manifest regardless of writer behaviour.

The recheck confirmed that both OpenFileGDB and GeoPackage drivers are available and that `pyogrio.raw.write()` works without pandas. A temporary two-layer GeoPackage preserved WKB for a vertical lift and multipart 3D path, Unicode text, null text, and a null floating attribute, and read back as EPSG:2326. Implementation still needs full-data export checks, especially nullable integer/boolean fields and timestamps; this small check does not establish preservation of every source type.

Alternative: GeoPandas + GeoParquet would closely follow the original outline and provide a convenient table API, but requires additional packages. It is unnecessary for the first implementation. If the existing writer proves inadequate, choose an explicit WKB/SQLite representation with CRS metadata or request permission for a justified dependency; do not silently lose geometry dimensions or types.

### Coordinate policy

- All working X/Y coordinates use **EPSG:2326, in metres**, with X=easting and Y=northing.
- Original longitude/latitude and source attributes remain available for audit and display.
- Use `Transformer.from_crs(..., always_xy=True)` for direct PyProj transformations.
- Confirm a source CRS from metadata or documented coordinate fields before transforming. Plausible values alone are a diagnostic, not sufficient CRS evidence.
- For JSON point lists without embedded CRS metadata, record the source documentation supporting WGS84. If that evidence is unavailable locally, record a clearly labelled WGS84 assumption in configuration and the validation report and check it against independent projected/reference coordinates where possible. Do not silently assign a CRS. An input with neither supported CRS nor an explicit accepted assumption remains unresolved and stops publication.
- The network already uses HK1980 Grid horizontally. Do not transform its Z coordinates or discard them. Treat HKPD height as separate vertical metadata; do not claim that a two-dimensional transformation converts vertical datums.
- Facility points have unknown heights. Do not invent Z=0 or sample a terrain raster during Step 1.
- iGeoCom's WGS84 geometry will be the canonical point source; compare its projected coordinates with supplied easting/northing. The inspected 611 access records differ by approximately 0.03–1.77 m, establishing a useful local baseline. Record residuals and investigate outliers rather than averaging the two coordinate representations.

## Implementation sequence

### 1. Make an explicit input inventory

Create `work/config/step_1.json` listing each selected input, source role, expected CRS evidence, and expected schema. Prefer `work/data`; use exact paths to the identified supplementary files outside `work` rather than scanning and selecting whichever similarly named file appears first.

Record SHA-256, size, selected archive members, source dates where known, and library versions. Treat file modification time separately from a source publication or download date. This manifest makes it clear which snapshot generated each output and resolves duplicate copies in the parent directory.

For the first implementation, copy the needed MTR CSVs and district crosswalk/documentation into `work/data/reference/`, retaining original path and checksums in the manifest. Compare the crosswalk's estate names and coordinates to the current estate file before reuse. Do not import existing scripts that have hard-coded destinations outside `work`.

### 2. Inspect and load the geodatabase

Safely extract the archive to `work/cache/3DPN_P2.gdb`: reject archive paths that escape the cache, confirm the expected `.gdb` directory, and reuse an extraction only when its recorded input hash matches.

Use `pyogrio.list_layers()` and `read_info()` to save the actual layer names, schemas, CRS, feature counts, bounds, geometry dimensions, and available coded domains. Load `PedestrianRoute` using `pyogrio.raw.read()`, in bounded batches if necessary. Read the five non-schedule supporting tables separately without requiring geometries. Record `AccessTime` and `AccessTimeDetails` as intentionally excluded in the source manifest, without reading their records or exporting them.

Preserve `PedestrianRouteID`, all vertices, multipart structure, Z values, and the original attributes. Important fields include `FeatureType`, `Gradient`, `Direction`, `WheelchairBarrier`, `WheelchairAccess`, `Enabled`, `Location`, `FloorID`, `TerminalID`, and `Shape_Length`. Any original `AccessTimeID` is retained solely as an unused source attribute, not decoded or joined.

Keep source codes and add decoded labels using the geodatabase domains. `list_layers()` and `read_info()` do not expose coded domains through the installed Pyogrio public API. The recheck found 18 embedded `GPCodedValueDomain2` XML definitions in this archive's `.gdbtable` files, readable using the standard library; the earlier audit uses this approach too. Implement that bounded metadata extraction separately, record its source, and validate extracted values against observed codes. Existing domain descriptions in `analysis/audit_summary.json` can be a documented fallback, checked against the selected archive. Do not cast coded values directly to Python booleans: for several fields, `1` means true and `2` means false. `WheelchairAccess` describes an accessible entrance connection; it is not a universal path-usability flag.

Preserve `Gradient` as `gradient_raw` with unresolved unit/sign metadata until authoritative evidence is available. Comparing its distribution with vertex-based slopes can detect inconsistencies but cannot alone establish its meaning. The available metadata PDF did not establish gradient units in this inspection. Step 2's cost model must resolve this before using it. Similarly, retain `Shape_Length` as a source attribute; distinguish planar XY length from 3D length rather than assuming which it represents.

Assume every route is always open. Do not inspect opening/closing schedules, flag schedule gaps, or add schedule-based restrictions in this or later stages.

No path filtering, splitting, endpoint merging, or planar-intersection creation occurs here. Coincident X/Y coordinates at different heights must remain distinct for later topology work.

### 3. Standardise the estate and hospital points

Load JSON with the standard library; retain the source record and extract typed fields into the common schema. Decode HTML entities and convert `<br>` into readable separators in display names, while retaining raw text.

For estates:

- Extract English/traditional/simplified Chinese names, source administrative district, region, map coordinates, and block metadata.
- Set `location_role="estate_map_point"`; do not describe it as a gate or block entrance.
- Join the existing crosswalk to add a separate `housing_district` field. Match exact source names initially; require unique matches and report coordinate discrepancies. Use explicit alias overrides if necessary, never a silent fuzzy match.
- Preserve crosswalk provenance and its limitations: town boundaries for Tung Chung and Tseung Kwan O are derived geographic proxies, not HA-issued allocation polygons. Avoid a blanket administrative-district mapping for Islands or Sai Kung.

For hospitals:

- Extract multilingual institution names, cluster, address, coordinates, and `has_ae` as a nullable boolean.
- Set `location_role="institution_map_point"` and retain entrance uncertainty.
- Preserve all 44 supplied institutions. Do not make A&E availability an eligibility requirement here; downstream configuration can select A&E hospitals or the full supplied set.

Where the input has no native entity ID, create and persist an ID registry using source namespace and an explicit identity key, initially the exact English name. Detect collisions; do not assign IDs from row position. Handle future renames through recorded aliases rather than silently creating a different identity.

Keep the authoritative registry at `work/config/entity_ids.json`, outside replaceable output directories. Copy its committed snapshot into each successful output. Use deterministic initial IDs from the namespace and identity key, and preserve recorded aliases on subsequent runs. Stage registry updates with the output so a failed run cannot change existing entity identities.

### 4. Reconcile the MTR sources

Load the three CSV references with `csv.DictReader`, `utf-8-sig`, and identifiers preserved as strings. Drop genuinely blank rows with an audit count. Keep station-line membership separate: repeated station IDs on different lines/directions are meaningful relationships.

Join facility `Key` to category `Item_Code`, and facility `Station_No` to the station table's `Station ID`. Report unmatched keys and station IDs. Earlier audit discrepancies, such as facility station IDs absent from the station CSV, should be checked again against these selected files.

Use an explicit station crosswalk to connect iGeoCom site/station names to the MTR station CSV. Start with documented prefix removal, whitespace/case normalisation, and exact English/Chinese comparisons; write proposed matches and unresolved cases to a review table. Do not infer that iGeoCom `GEONAMEID` equals an MTR station ID or network `TerminalID`. A controlled override table handles aliases and exceptions.

Parse named exit descriptions only when unambiguous. Facility text can mention multiple exits or equipment serving only part of a journey; retain raw descriptions and match evidence. A station-level facility match must not label every exit accessible. Railway station points assist reconciliation and do not replace exit coordinates.

Preserve all 611 access records. Interpret the dictionary subcategories as evidence:

| Code | Meaning | Normalised evidence |
|---|---|---|
| `MTRLIF` | Barrier-free access with lift | `lift` |
| `MTRRAM` | Barrier-free access with ramp | `ramp` |
| `MTRSLV` | Barrier-free access at same level | `same_level` |
| `MTRSTL` | Barrier-free access with stair lift | `stair_lift` |
| `MTRWCA` | Barrier-free access with wheelchair aid | `wheelchair_aid` |
| blank | Unspecified | `unknown` |

Observed counts: 119 lift, 56 ramp, 61 same-level, 11 stair-lift, 2 wheelchair-aid, and 362 unspecified. Keep an evidence/source field and station/exit match status. These categories do not prove a continuous accessible route to a platform or current equipment availability. Later routing policy decides which categories qualify; Step 1 does not make that decision.

### 5. Standardise and verify the bus/minibus stop list

Use the 9,264-row `bus_stops.json` as the preferred point list. Preserve `stop_id` as a source identifier, operators as a list, and `GMB`, `KMB`, `CTB` flags. Normalise names without overwriting raw names. Keep different IDs separate even when coordinates or names coincide.

Validate the derived list against both supplied route-stop datasets: compare ID sets, coordinates, operator unions, and naming variants. Report inconsistent coordinates for one ID rather than selecting the first unnoticed. Preserve route/service evidence in a related nonspatial table or a lossless reference to raw records, including `stopPickDrop`, `routeId`, `routeSeq`, `stopSeq`, `serviceMode`, and `lastUpdateDate`.

Recheck result: the local list exactly matches the union of raw stop IDs, coordinates, and operator sets, with no conflicting coordinates for a stop ID. Its original builder used `JSON_BUS.json.1` in the parent directory; that file's SHA-256 equals `work/data/JSON_BUS.json`, and the parent GMB file also equals its `work/data` copy. Record this provenance rather than assuming similar filenames contain the same snapshot.

Do not infer pickup permission from an undocumented code or wheelchair boarding ability from an operator flag. Set boarding-accessibility evidence to `unknown` where absent. Keep GMB distinct so later ranking can include or exclude minibuses. The bus stop dataset can be retained now even if boarding-code semantics need further documentation.

### 6. Validate and write reproducible outputs

Run validation before finalising outputs. Write to a staging directory and promote a complete, consistent result only after the required checks pass. Leave the previous successful output intact on failure.

Make any record exceeding a configured coordinate-residual or crosswalk-coordinate tolerance an explicit error or review item, with tolerances and units recorded in configuration. The current crosswalk has exact coordinate matches for all 244 estates. Broad geographic bounds are only a sanity check and cannot establish district membership or accurate alignment by themselves.

**Errors that stop publication:** missing required inputs or fields; unsupported/unresolved source CRS for transformation; duplicate primary IDs; non-finite required coordinates; empty/wrong geometry types in the usable output; missing/ambiguous housing-district assignments; failed read/write preservation checks. Retain offending records and diagnostics in a rejection report; never silently discard them.

**Issues that remain visible without stopping ingestion:** unmatched MTR station/exit references; unspecified access categories; entrance uncertainty; unconfirmed gradient semantics; suspicious source publication/update dates; overlapping coordinates. Source publication/update dates describe dataset provenance and do not control route opening hours. Mark them explicitly so later stages can enforce their own requirements.

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
    step_1.json
    entity_ids.json               # authoritative identity/alias registry
    mtr_station_overrides.csv
    mtr_exit_overrides.csv
  data/
    ...existing inputs...
    reference/                   # selected supplementary inputs with provenance
  cache/
    3DPN_P2.gdb/
  src/
    estate_ranking/
      __init__.py
      models.py                  # SpatialDataset and validation result contracts
      ingest.py                  # source readers, safe extraction, inventory
      harmonise.py               # coordinates, fields, identifiers, district join
      mtr_links.py                # station/exit reconciliation and evidence
      validate.py                # checks and diagnostics
      export.py                  # spatial/table persistence and round trips
      step_1.py                  # command-line orchestration
  tests/
    test_step_1.py                # small fixtures for consequential transformations
  precomputed/
    step_1/
      harmonised.gpkg             # network, estates, hospitals, MTR exits/stations, stops
      reference_tables.sqlite     # non-schedule network references, MTR/service relations
      source_manifest.json
      schema.json
      validation_report.json
      validation_report.md
      mtr_match_review.csv
      rejected_records.jsonl
      entity_ids.json
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
| `link_mtr_tables(stations, exits, facilities, categories, overrides)` | Produce relationships, evidence and unresolved-match reports. |
| `validate(datasets, tables, manifest)` | Return structured errors, warnings and reconciliation totals. |
| `write_outputs(...)` | Stage outputs, verify round trips and finalise the successful run. |

Planned command, from the new working directory:

```sh
cd work
PYTHONPATH=src ../.venv/bin/python -m estate_ranking.step_1 --config config/step_1.json
```

Resolve input and output paths relative to `work` or the configuration's declared project root, never implicitly to whichever directory starts Python.

## Implementation milestones and completion criteria

1. **Input inventory and writer proof:** explicit sources, environment check, safe extraction, small geometry/table round trip with Z and nulls preserved.
2. **Core loaders and coordinate harmonisation:** network/five non-schedule support tables and all facility/estate datasets loaded through the common container.
3. **District and MTR relationships:** verified crosswalk, match evidence, override mechanism and unresolved-case exports; bus-list reconciliation complete.
4. **Validation and reproducible export:** reports, manifest and outputs produced by one command, with focused fixture checks and a full real-data run.

The fixture checks should exercise axis order, Z preservation for lifts and multipart paths, `1`/`2` code interpretation, duplicate identifiers, ambiguous joins, blank MTR subcategories, and colocated bus stops with different IDs. These protect transformations that could otherwise produce plausible but incorrect routing inputs.

Step 1 is complete when every selected source record is accounted for (the two access-schedule tables are explicitly excluded), all published spatial layers share EPSG:2326 horizontally, original network heights survive, all 244 estates have one documented housing district, and unresolved accessibility or source-semantic questions are explicit in the report. MTR records with uncertain matches remain in the output with flags. No missing evidence is converted into a claim of accessibility. This completes ingestion and harmonisation; a remaining gradient interpretation or route-eligibility issue must still be resolved before the affected Step 2 or Step 3 operation proceeds.

## Questions carried forward to later steps

Access schedules are already decided: assume all routes are always open, with no date/time inputs or schedule checks. The remaining questions below do not prevent writing the Step 1 pipeline:

- Gradient units, sign convention, and the meaning of source `Shape_Length` need authoritative confirmation before edge costs are calculated.
- “No stairs” and independent wheelchair access may require different policies for escalators, stair lifts, assisted access, and steep ramps.
- Estate and hospital map points are not verified entrances; additional entrance locations may improve later snapping.
- MTR station/exit aliases may require manual review of the generated match table.
- Pickup/drop-off code meanings and wheelchair boarding evidence require further documentation for transport eligibility.
- The later query configuration must decide whether “any hospital” includes every supplied institution or only an A&E subset, and whether GMB is part of bus access.
- The DTM remains optional for later connector/terrain checks; Step 1 does not resample it or use bare-earth heights to overwrite elevated network geometry.

If documentary gaps require new external data, first identify the exact missing evidence and source. The initial implementation can proceed with local inputs and explicit unknowns.
