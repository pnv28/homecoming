# Step 1 implementation plan: prepare consistent data for estate ranking

Prepared and rechecked on 13 October 2026. Revised to explain the work for team members who have project ideas but are less familiar with programming and geographic-data terminology.

This is the plan for **Step 1, “Harmonise data”**, in `estate_ranking_design.md`. The full Step 1 program has not been built or run. Earlier checks inspected the source files and tested a small example of saving and reopening geographic data.

## How to read this plan

Every area separates two kinds of writing:

- **Explanation for the team** describes what the terms mean, why the work matters, and what the result will tell us.
- **Steps we will take** describes the actual implementation work, in order. These are planned actions, not claims that the program is already complete.

The file names and Python function names remain in the document so developers can connect the explanation to the implementation. An explanation is provided before technical terms are needed. The numbered areas below are parts of Step 1; they are not the five main stages of the overall ranking algorithm.

## 1. What Step 1 will accomplish

### Explanation for the team

Our files describe different things: housing estates, hospitals, transport access points, and pedestrian paths. They come in different formats and do not necessarily use the same conventions for names, coordinates, or missing information.

**Ingestion** means opening a source file and reading its contents into the program. **Harmonisation** means making the information consistent enough to use together. For example, an estate may use `Estate Map Longitude`, while a hospital uses `longitude`. We can give both a consistent working field without changing the original file. A **field** is one named item of information, similar to a spreadsheet column; a **record** is one item being described, similar to a row.

Step 1 will produce separate, cleaned working datasets. We will still have an estate table, a hospital table, a transport-access table, and a path table. They will share conventions for identifying records, storing locations, and documenting uncertainty. Combining their conventions does not mean putting every kind of information into one large table.

A later stage will turn the pedestrian paths into a **graph**: a structure with connection points and links between them. Another stage will **snap** estate and facility points to suitable paths, meaning find and record where they connect to the walking network. Later stages will calculate journeys and rank estates. Step 1 prepares the inputs for that work.

The sources do not establish everything we might want to know. An estate map point may not be its accessible gate. A lift label does not establish whether the lift works today. We will preserve those distinctions so later stages can make informed decisions.

### Steps we will take

1. We will read `estate_ranking_design.md` and `whole_chat_export.md` together and keep the scope tied to their first main stage.
2. We will load the source files, standardise their fields and coordinates, add the four Housing Authority allocation categories, and connect related MTR reference tables.
3. We will check the prepared data and save it with reports describing the sources and any unresolved issues.
4. We will preserve information needed for later stages, including path heights, slope values, access schedules, and uncertainty about entrances.
5. We will leave graph construction, stair exclusion, route costs, snapping, shortest-path calculation, and ranking to their corresponding later stages.
6. We will keep new code and outputs under `work/`, use the repository's local `.venv`, and leave original source files unchanged. We will install no packages during this planned implementation. If a necessary missing dependency is discovered, we will explain why and request permission before installing it. No Homebrew packages are needed by the current plan.

## 2. Select the exact source files and record their origins

### Explanation for the team

The parent directories contain duplicate files, earlier analysis, and several similarly named datasets. A program that selects the first matching file could accidentally use an older copy. We need a fixed list of inputs.

An **inventory** is that list. A **configuration file** stores choices the program reads, such as exact file paths and check thresholds. A **manifest** records what the program actually used, including file versions and checksums. **Provenance** means the history and origin of a piece of data.

A **SHA-256 checksum** is a fingerprint calculated from the contents of a file. Matching filenames do not prove files are identical; matching checksums provide strong evidence that their contents are identical. A source date also differs from a file's modification date: copying an old dataset today does not make its information current.

The inspection found these inputs:

| Information | Preferred input | What is available in this snapshot |
|---|---|---|
| Estates | `work/data/prh-estates (1).json` | 244 estates, names in three language forms, administrative districts, map coordinates, and block names/counts. The inspected schema has no block or entrance coordinates. |
| Hospitals | `work/data/facility-hosp.json` | 44 institutions, multilingual names, addresses, clusters, coordinates, and A&E yes/no fields. |
| Pedestrian paths and related tables | `work/data/3D_Pedestrian_Network_FGDB.zip` | A geographic database named `3DPN_P2.gdb`, with 465,892 path records and seven supporting tables. |
| MTR access points | `work/data/mtr_access_points.geojson` | 611 access records, with names, locations, station/site descriptions, and access categories. |
| Railway station reference points | `work/data/railway_stations.geojson` | 98 station records. Station map points are different from station entrance points. |
| Combined bus/minibus stops | `work/data/bus_stops.json` | 9,264 distinct stop IDs, including 4,776 stops labelled GMB. |
| Original bus route-stop records | `work/data/JSON_BUS.json` | 56,209 records describing stops used by routes. A stop can appear many times. |
| Original minibus route-stop records | `work/data/JSON_GMB.json` | 13,155 route-stop records. |
| MTR reference CSVs | `data/organized/core/mtr/` | Station/line list, facility list, and facility-category definitions. The facility list's exit-coordinate fields are empty. |
| Estate allocation-category lookup | `analysis/maps/estate_housing_district_crosswalk.csv` | A mapping for all 244 estate names: Urban 109, Extended Urban 70, New Territories 60, Islands 5. |
| Documentation | The two PDFs in `work/data/`, plus existing reports under `analysis/` | Definitions and prior findings that help interpret the source fields. |

A **crosswalk** is a lookup table connecting one set of records or labels to another. Here, the estate crosswalk connects an estate name to its Housing Authority allocation category.

JSON is a text format for structured records; CSV is a spreadsheet-like text format; GeoJSON is structured text that also describes geographic shapes. ZIP is a compressed package containing other files. We will use a suitable reader for each format.

### Steps we will take

1. We will create `work/config/step_1.json` with an explicit path and purpose for each selected input.
2. We will prefer the copies in `work/data` and list exact supplementary paths when information is only available outside `work`.
3. We will copy the needed MTR CSVs, estate crosswalk, and supporting documentation into `work/data/reference/`, recording their original locations and checksums.
4. We will calculate each selected input's checksum and file size. For compressed files, we will also record which contained files we use.
5. We will record known publication/download dates separately from file modification times, leaving dates unknown when evidence is unavailable.
6. We will record the installed Python and library versions so someone can reproduce the run.
7. We will compare the crosswalk's names and coordinates with the selected estate file before reusing it. The recheck found exact coordinate matches for all 244 current estates.
8. We will save these findings in `source_manifest.json`. We will read existing analysis for evidence but will not run or import scripts that write to hard-coded destinations outside `work`.

## 3. Choose the Python tools and the working data structure

### Explanation for the team

The local **virtual environment**, `.venv`, is the project's existing Python installation and collection of additional tools. A **library** is reusable code that handles a particular task. Using the existing environment avoids unnecessary installation and makes the project easier to reproduce.

The environment runs Python 3.9.6 and has the following tools:

| Tool | Version | Role in this plan |
|---|---|---|
| Pyogrio | 0.11.1 | Reads and writes geographic files through GDAL, a geographic-file engine. |
| Shapely | 2.0.7 | Represents and examines points, lines, and other shapes. |
| PyProj | 3.6.1 | Converts coordinates between map reference systems. |
| NumPy | 2.0.2 | Stores and processes columns of values efficiently. |
| pypdf | 6.20.0 | Reads text from PDF documentation. |

GeoPandas, pandas, PyArrow, Fiona, and rasterio are absent. The design originally suggested a **GeoDataFrame**, a spreadsheet-like object with a geographic shape attached to every row. We can provide that essential structure using the installed tools and a small Python object named `SpatialDataset`.

A **geometry** is the shape of a record: for example, an estate's point or a path's line. An **array** is an ordered collection of values. If array position 10 describes an estate's name, position 10 in the geometry array must describe the same estate's location. This is the data structure's **contract**: rules that every reader and later function must follow.

A **schema** describes the fields, their meanings, and their types. Types distinguish text, whole numbers, decimal numbers, and yes/no values. A **null** means missing or unknown; it is different from zero, an empty name, or “no.” Some readers store a whole-number column with missing values as decimal numbers. We must preserve the intended type so station ID `117` does not accidentally become `"117.0"` and fail to match another table.

### Steps we will take

1. We will confirm the installed environment at the start of implementation and write code compatible with Python 3.9.
2. We will define `SpatialDataset` in `models.py`. It will contain ordered named attribute arrays, a same-length Shapely geometry array, field types, missing-value information, coordinate-system information, and source metadata.
3. We will define a similar structure for supporting tables that contain descriptions and relationships but no geographic shapes.
4. We will make every source reader return these structures, so later stages do not have to understand each original file format.
5. We will keep source field types available when converting values. Where necessary, we will use a separate null mask: a record-by-record indicator of which values are missing.
6. We will preserve original attributes, or a precise reference to their original records, alongside the standardised fields.
7. We will use Pyogrio's raw reader, NumPy, Shapely, PyProj, and Python's built-in file/table tools. GeoPandas with GeoParquet remains an alternative if later needs justify installing additional libraries; it is not required for this plan.

## 4. Put locations into one map reference system

### Explanation for the team

Coordinates only make sense when we know the rules behind them. A **coordinate reference system**, or **CRS**, specifies those rules. One file may express a location as longitude/latitude; another may use distances east and north within a Hong Kong map grid. Comparing their numbers directly would be meaningless.

**WGS84** is the geographic reference used by the iGeoCom point geometries. Its longitude/latitude values are angles. **EPSG:2326** is the identifier for Hong Kong 1980 Grid, a projected map system using metres. “EPSG” codes are reference numbers for defined coordinate systems.

Our working X/Y convention will be X=easting and Y=northing. Easting measures position eastward in the grid; northing measures position northward. For longitude/latitude inputs, X means longitude and Y means latitude. The program must keep that ordering consistent. PyProj's `always_xy=True` explicitly enforces it when we call coordinate transformations directly.

The pedestrian network also contains **Z**, or height. Its height reference is Hong Kong Principal Datum, **HKPD**, identified as EPSG:5738. Together, a horizontal map reference and a height reference form a **compound CRS**. Keeping the same horizontal grid does not mean we have converted heights. Estate and hospital points lack documented heights, so assigning height zero would invent information.

The iGeoCom file gives two representations of each access point: WGS84 geometry and HK1980 easting/northing attributes. We can transform one and compare it with the other. Their separation is a **residual**, a measured disagreement. In the checked access records, the separation is approximately 0.03–1.77 metres. Small disagreement can reflect source precision; large disagreement would need investigation.

### Steps we will take

1. We will determine and record the source CRS for each input using embedded metadata or source documentation.
2. For a JSON point list without embedded CRS, we will look for documentary evidence supporting WGS84. If that is unavailable locally, we will explicitly label any WGS84 assumption in configuration and the report and check it against independent reference coordinates where possible. We will stop output finalisation for a source with neither a supported CRS nor an explicit accepted assumption.
3. We will retain original longitude/latitude and any original grid coordinates, so conversions can be audited.
4. We will transform point X/Y coordinates into EPSG:2326 using `Transformer.from_crs(..., always_xy=True)`.
5. We will retain the network's existing EPSG:2326 X/Y values and its original Z values. We will record its HKPD height reference separately.
6. We will leave facility heights unknown and will not sample the terrain raster or introduce height zero in Step 1.
7. We will use iGeoCom's WGS84 geometry as the main point location and compare its transformed X/Y with the supplied grid attributes. We will record residuals and configurable review thresholds rather than average the two locations.
8. We will check plausible geographic bounds and convert selected transformed coordinates back to their source system to check the transformation. Bounds alone will not prove accurate alignment or district membership.

## 5. Open and preserve the pedestrian network

### Explanation for the team

A **File Geodatabase** is a geographic database stored as a directory ending in `.gdb`. Our ZIP contains `3DPN_P2.gdb`. A **layer** groups one kind of geographic information, like a sheet in a workbook. The main layer, `PedestrianRoute`, contains paths; the seven other tables provide schedules and references.

The path geometry is `MultiLineString Z`. A **LineString** is a line described by a sequence of points. A **vertex** is one of those points. “Multi” means a record can contain more than one line part; “Z” means the coordinates include heights. We must keep the intermediate vertices because they describe bends and height changes. We must also keep separate line parts and their order.

The listed layers contain no separate node layer. Nodes are connection points used by the later graph. We will preserve the path information needed to construct them later rather than assume the database already supplies them.

Some attributes use codes rather than words. A **coded domain** is the dictionary explaining those codes. In several yes/no fields, `1` means true and `2` means false; ordinary Python conversion would treat both nonzero numbers as true. That would produce incorrect access information.

The network's `WheelchairAccess` field describes whether a connection to a facility/building/site is an accessible entrance. It does not mean every path must have that flag to be usable. `WheelchairBarrier` is a different field. Their meanings must remain separate.

**Gradient** describes steepness, but we have not established the source field's units or whether it records directional uphill/downhill information. `Shape_Length` is also a source measurement whose precise interpretation needs confirmation. A line's distance on a flat map differs from its distance including height changes. A vertical lift can have zero map distance while still connecting different heights.

### Steps we will take

1. We will inspect ZIP member paths and reject extraction paths that would escape `work/cache/`. We will extract the database to `work/cache/3DPN_P2.gdb`.
2. We will associate the extraction with the ZIP checksum. We will reuse it only when it matches the selected source contents.
3. We will call `pyogrio.list_layers()` and `read_info()` to record actual layer names, field definitions, row counts, geometry types, CRS, and geographic extent.
4. We will load `PedestrianRoute` using `pyogrio.raw.read()`, with bounded batches if needed for memory use. The current snapshot contains 465,892 records.
5. We will load all seven supporting tables separately. `AccessTime` currently has 2,413 rows and `AccessTimeDetails` has 3,483 rows; terminal, floor, building, site, and distance-post references will also be retained.
6. We will preserve `PedestrianRouteID`, all line parts, every vertex, every Z value, and original attributes. Important fields include `FeatureType`, `Gradient`, `Direction`, `WheelchairBarrier`, `WheelchairAccess`, `Enabled`, `Location`, `FloorID`, `AccessTimeID`, `TerminalID`, and `Shape_Length`.
7. We will extract the archive's coded-domain definitions separately. The installed Pyogrio public API does not expose them through `read_info()`. The recheck found 18 readable `GPCodedValueDomain2` XML definitions inside `.gdbtable` files. XML is structured text; we will read only the bounded definition blocks and parse them using Python's built-in tools.
8. We will keep both source codes and decoded descriptions, and compare observed codes with the extracted dictionaries. If a dictionary cannot be read, we will check the documented fallback in `analysis/audit_summary.json` against the selected archive and record that use.
9. We will store the slope value as `gradient_raw` and mark unresolved units/direction in metadata. We will retain `Shape_Length` without labelling it as a confirmed 3D or planar length. Source interpretation must be resolved before the affected route-cost calculation.
10. We will preserve schedules and reference IDs without deciding whether facilities are open at a chosen time. Those decisions belong to later routing policy.
11. We will keep all paths in Step 1. We will not split lines, merge endpoints, remove stairs, or create connections wherever lines cross on a flat map. Paths at the same X/Y but different heights must remain distinguishable.

## 6. Prepare estate locations and Housing Authority categories

### Explanation for the team

The estate file gives administrative district names, such as Islands or Sai Kung. The ranking query needs Housing Authority allocation categories: Urban, Extended Urban, New Territories, and Islands. These are different classifications.

A **join** connects records from two tables using matching information. We will join the estate list to the existing category crosswalk by estate name, while checking uniqueness and coordinates. A name that matches two rows is ambiguous and needs resolution.

Administrative boundaries cannot always be converted to allocation categories by a single district lookup. Tung Chung belongs to Extended Urban while other Islands locations belong to Islands. The existing work also distinguishes Tseung Kwan O estates from the whole Sai Kung administrative area.

The previous map work used smaller geographic areas as **proxies**, meaning approximations used to represent the named towns. Those are not HA-issued allocation boundary polygons. We can reuse the documented estate assignments while retaining this limitation.

An **ID** is a stable label for a record. Row numbers are unsuitable because sorting the source file would change them. The estate file has no native estate ID in the inspected schema, so we will maintain our own persistent lookup, or **ID registry**. An **alias** records that a changed name refers to an existing entity.

### Steps we will take

1. We will read the estate JSON while retaining the original record or a lossless reference to it.
2. We will extract English, traditional Chinese, and simplified Chinese names; administrative district; region; map coordinates; and block metadata.
3. We will create readable display text by decoding HTML entities and turning `<br>` markers into separators. We will retain the raw text as well.
4. We will give each estate a stable ID using its source namespace and explicit identity key, initially its exact English name. A namespace identifies the kind/source of record, preventing a hospital and estate with similar names from sharing an identity.
5. We will maintain the authoritative registry at `work/config/entity_ids.json`. Initial IDs will be deterministic, meaning the same namespace and identity key produce the same ID. Future renames will use recorded aliases; duplicate identities will be reported.
6. We will set `location_role="estate_map_point"`, preserving the distinction between the supplied map point and a verified gate or block entrance.
7. We will join the crosswalk by exact source name and require one match per estate. Where an alias is necessary, we will record it explicitly rather than guess using a similar-looking name.
8. We will compare crosswalk coordinates with the estate coordinates and report disagreement against documented thresholds.
9. We will add `housing_district` as a separate field, preserving `source_administrative_district` and the crosswalk's provenance. For this snapshot, we expect Urban 109, Extended Urban 70, New Territories 60, and Islands 5.
10. We will stage ID-registry changes with outputs and copy the committed registry into each successful output. A failed run must not replace existing identities.

## 7. Prepare hospital locations

### Explanation for the team

The hospital file has 44 institutions, including A&E information. **A&E** means Accident and Emergency. Having no A&E department does not mean an institution has no value to someone who needs a particular hospital.

We should preserve all supplied institutions now. The later query can choose a particular hospital or define which institutions qualify when the user chooses none.

A **nullable boolean** is a yes/no field that can also be unknown. It matters because missing A&E information should not be changed into “No.” Hospital map points also need the same entrance uncertainty as estate points.

### Steps we will take

1. We will read the hospital JSON and retain original record references.
2. We will extract multilingual institution names, cluster, address, and coordinates.
3. We will create persistent hospital IDs through the same registry mechanism, using a separate hospital namespace.
4. We will interpret documented A&E yes/no values as `has_ae`, preserving missing or unrecognised values as unknown with a diagnostic.
5. We will transform the supplied coordinates using the policy in Area 4 and set `location_role="institution_map_point"`.
6. We will preserve all 44 institutions. We will leave A&E-only eligibility and preferred-hospital selection to later configuration.

## 8. Connect the MTR station, entrance, and facility information

### Explanation for the team

The MTR sources answer different questions. The station CSV identifies stations and their lines. The facility CSV describes equipment and sometimes names exits. The iGeoCom access file supplies locations for entrances. The railway-station file supplies station reference points. We need to connect these sources without confusing a whole station with a particular entrance.

The same station can appear several times in the line table because it serves several lines or directions. That is a meaningful **one-to-many relationship**, not automatically a duplicate error. Similarly, one station can have many entrances.

Source IDs have different meanings. iGeoCom `GEONAMEID`, the MTR CSV station ID, and the pedestrian network's `TerminalID` are not interchangeable. A matching number would not prove that they refer to the same place.

Names can also differ: one source might include “Mass Transit Railway” before a station name. **Normalisation** here means controlled changes such as trimming spaces or removing a documented prefix to help compare names. A **manual override** is a recorded exception identifying a match that automatic rules cannot safely establish.

An accessible facility description may apply to one entrance, an internal paid-area lift, or a staff-assisted service. It must not label every entrance at the station accessible. Blank access information means unknown.

The iGeoCom dictionary gives this entrance evidence:

| Source code | Plain-language meaning | Working evidence label | Current records |
|---|---|---|---:|
| `MTRLIF` | Barrier-free access with a lift | `lift` | 119 |
| `MTRRAM` | Barrier-free access with a ramp | `ramp` | 56 |
| `MTRSLV` | Barrier-free access at the same level | `same_level` | 61 |
| `MTRSTL` | Barrier-free access with a stair lift | `stair_lift` | 11 |
| `MTRWCA` | Barrier-free access with wheelchair aid | `wheelchair_aid` | 2 |
| blank | Access type unspecified | `unknown` | 362 |

These are 611 access records, not a verified count of distinct physical exits. The labels do not establish current equipment operation or a continuous accessible journey from the street to a platform. The later route policy will decide which types qualify for the intended users.

### Steps we will take

1. We will load `mtr_lines_and_stations.csv`, `barrier_free_facilities.csv`, and `barrier_free_facility_category.csv` with `csv.DictReader` and `utf-8-sig`. This encoding handles an optional BOM, an invisible file-start marker that could otherwise become part of a column name.
2. We will keep IDs as strings, drop only wholly blank rows with an audit count, and separate unique station records from their line/direction memberships.
3. We will join facility `Key` to category `Item_Code` to attach the equipment definition.
4. We will join facility `Station_No` to station `Station ID`, reporting unknown station IDs and facility keys. We will recheck previously observed mismatches against the selected files.
5. We will load all 611 iGeoCom access records and all 98 railway-station reference records, retaining their native IDs, coordinates, names, source attributes, and subcategories.
6. We will build an explicit crosswalk between iGeoCom station/site names and the MTR station CSV. We will try documented prefix removal, whitespace/case normalisation, and exact English/Chinese comparison.
7. We will accept unambiguous matches under documented rules and save ambiguous or unmatched cases to `mtr_match_review.csv`, including the evidence and candidates where available.
8. We will apply recorded exceptions from `mtr_station_overrides.csv` and `mtr_exit_overrides.csv`. We will validate each exception's referenced records and retain why it was needed.
9. We will connect exit-specific facility descriptions only when the exit reference is unambiguous. Descriptions listing multiple exits will retain that relationship; unclear descriptions will remain unresolved. Station-level equipment will stay station-level.
10. We will add the dictionary-based access evidence label, its source, and station/exit match status to every access record. Conflicting evidence will be reported rather than silently overwritten.
11. We will keep unknown or unresolved entrances in the harmonised data with visible flags. We will not substitute station map points for entrances or decide routing eligibility during Step 1.

## 9. Prepare and verify bus and minibus stops

### Explanation for the team

The raw files describe stops as used by routes. If ten routes use one stop, the raw file may contain many records for it. The prepared `bus_stops.json` instead provides one point per stop ID. **Deduplication** means removing repeated representations of the same identity; it does not mean merging every nearby point.

Different stop IDs must remain separate even when names or locations coincide. They may represent different boarding points or services. GMB identifies green-minibus service, while KMB and CTB are other operator labels. We should retain all operators rather than treat the three named flags as an exhaustive list.

A service at a stop does not automatically allow boarding there in every direction, and operator membership does not establish wheelchair boarding access. The raw `stopPickDrop` field contains codes whose meanings must be documented before eligibility rules use them.

The recheck compared the prepared list with both raw inputs. The 9,264 IDs, coordinates, and combined operator sets matched exactly, with no coordinate conflict for one ID. The earlier builder used the parent's `JSON_BUS.json.1`; checksums confirm it equals `work/data/JSON_BUS.json`. The GMB copies also match. We will retain this evidence and still verify future runs.

### Steps we will take

1. We will load `bus_stops.json` as the preferred list and preserve `stop_id` as a source ID.
2. We will retain English/Chinese names, coordinates, the full operator list, and `GMB`, `KMB`, and `CTB` flags. We will make readable display names while retaining original text.
3. We will load both raw route-stop files with `utf-8-sig` and group records by source stop ID.
4. We will compare the raw ID union with the prepared list, check every stop's coordinates, combine operator memberships, and check the saved flags against that combined membership.
5. We will report naming variants and conflicting coordinates for one ID. We will keep distinct IDs separate and will not silently choose the first conflicting location.
6. We will preserve route/service evidence in a related table or a lossless reference to raw records. This includes `stopPickDrop`, `routeId`, `routeSeq`, `stopSeq`, `serviceMode`, and `lastUpdateDate`.
7. We will transform stop coordinates to EPSG:2326 and retain source coordinates and file provenance.
8. We will mark boarding-accessibility evidence as unknown when absent. We will retain undocumented pickup/drop-off codes without interpreting them, and keep GMB separate so later query configuration can include or exclude it.

## 10. Check that the prepared information is trustworthy

### Explanation for the team

**Validation** means checking that the data satisfies the rules needed by later stages. A program can finish without crashing and still produce incorrect locations or joins. We need checks that detect plausible-looking errors.

An **error** prevents the prepared output from being finalised, such as a coordinate system the program cannot interpret. A **warning** records a limitation while allowing the data to be retained, such as an entrance with unknown access evidence. A warning can still prevent a later routing operation if that operation needs the missing information.

**Referential integrity** means that an ID pointing to another table can be resolved appropriately. For example, a path's schedule ID should connect to a schedule, and that schedule may have several day/time rows. Missing references need reports; valid repeated schedule rows must not be mistaken for duplicate identities.

A **round-trip check** saves data, reopens it, and compares the result with what was written. This catches export problems, such as heights being dropped or missing values turning into zero. A **fixture** is a small deliberately chosen example used to test a consequential case without reading the whole dataset.

A **quarantined record** is preserved separately with a reason because it cannot be safely used. Quarantining does not silently make a blocking error acceptable. The program will account for every input record and will keep the previous successful output when a required check fails.

### Steps we will take

1. We will check required files and fields, declared types, unique entity IDs, and source record counts.
2. We will reconcile input counts with usable and quarantined records, accounting for every record. Current counts are snapshot expectations rather than permanently hard-coded dataset sizes.
3. We will check required coordinates for finite numeric values, plausible bounds, supported reference systems, and appropriate geometry types. We will not treat a broad Hong Kong bounding box as proof of precise location or category membership.
4. We will check all 244 current estate assignments for one documented allocation category and verify crosswalk coordinates against configured tolerances.
5. We will check MTR station/category relationships, schedule references, source code dictionaries, and the bus-list reconciliation while respecting valid one-to-many relationships.
6. We will check path vertex counts, line-part structure, and Z preservation. We will retain vertical lift lines even when their flat-map length is zero and will not apply two-dimensional shape repair indiscriminately to 3D paths.
7. We will record coordinate comparison thresholds and units in configuration and report outliers as errors or review items under explicit rules.
8. We will use fixtures to check axis ordering, vertical/multipart geometry preservation, `1`/`2` code interpretation, nullable IDs, ambiguous matches, blank access categories, and colocated stops with distinct IDs.
9. We will stop finalisation for missing required inputs/fields, unresolved CRS without an accepted assumption, duplicate primary IDs, unusable required coordinates/geometries, missing or ambiguous estate categories, or failed read/write preservation. We will save the offending records and diagnostics.
10. We will report unresolved MTR matches, unknown access categories, entrance uncertainty, gradient interpretation gaps, suspicious dates, coordinate overlaps, and schedule-reference gaps as visible issues. Later stages must enforce any requirements these affect.
11. We will write both `validation_report.json` for program use and `validation_report.md` for team review. Each issue will identify the source, relevant record, check, and consequence.
12. We will leave network connectivity checks to Step 2, where a graph and access policy exist. Step 1 cannot establish route reachability from file integrity alone.

## 11. Save the prepared data without losing information

### Explanation for the team

An **output format** determines how prepared data is stored for later use. A **GeoPackage**, ending in `.gpkg`, can hold several geographic layers in one file. It supports projected coordinates and 3D line shapes, which fit this project. **SQLite** is a local database format suitable for supporting tables; Python already includes tools for it.

The proposed spatial output is `harmonised.gpkg`; nonspatial tables go into `reference_tables.sqlite`. JSON and CSV provide readable structured reports and review lists. Conventional GeoJSON is intended for geographic coordinates, so GeoPackage is a clearer choice for the EPSG:2326 working layers.

The recheck confirmed the installed OpenFileGDB and GeoPackage readers/writers are available. A temporary two-layer GeoPackage preserved the geometry of a vertical lift and multipart 3D line, Chinese text, null text, and a null decimal value. It reopened as EPSG:2326. That is useful evidence, but full-data export checks must still cover additional types and records.

**WKB**, or Well-Known Binary, is a standard byte representation of a geometry. **WKT**, or Well-Known Text, is a text representation; CRS definitions also use a WKT form. We will keep the original full CRS definition in the manifest so the height reference remains documented even if a writer records only the horizontal CRS.

A **staging directory** is a temporary location for a candidate output. We validate that candidate before making it the current successful result. This protects a previously usable output if the next run fails.

### Steps we will take

1. We will create a staging directory for the run and save separate GeoPackage layers for paths, estates, hospitals, MTR access points, railway station references, and bus/minibus stops.
2. We will store schedules, network reference tables, MTR relationships, and retained route/service evidence in SQLite or through documented lossless source references.
3. We will encode list-valued fields, such as operators, as documented JSON text where the destination field cannot hold a list directly.
4. We will save `schema.json` describing each field's meaning, type, allowed codes, missing-value rules, and relationships.
5. We will save source metadata, including original compound CRS WKT, the HKPD height reference, input hashes, assumptions, and software versions.
6. We will reopen all outputs and compare IDs, counts, field types, nulls, Unicode names, timestamps, CRS, multipart structure, and vertex/Z coordinates with the prepared in-memory data. Any numerical tolerance will be documented.
7. We will save validation reports, MTR match-review records, rejected-record diagnostics, and a snapshot of the ID registry with the candidate output.
8. We will finalise the output and registry updates only after required checks pass, preserving the previous successful result on failure. Implementation must ensure incomplete staged changes are not selected as current outputs.
9. If the installed writer cannot preserve a necessary feature, we will use an explicitly documented WKB/SQLite representation or explain why an additional library is necessary and request permission before installing it. We will not silently drop heights or change types.

## 12. Organise the program and make it runnable

### Explanation for the team

A **module** is a Python file grouping related work. A **function** is a named operation within that program. Separating reading, matching, checking, and writing makes problems easier to locate and allows later stages to reuse the prepared data.

The proposed structure is shown below. These are planned files and directories, not a statement that they already exist. `config` holds deliberate choices, `data` holds inputs, `cache` holds reusable extraction, `src` holds program code, and `precomputed` holds saved results.

```text
work/
  config/
    step_1.json
    entity_ids.json
    mtr_station_overrides.csv
    mtr_exit_overrides.csv
  data/
    ...existing inputs...
    reference/
  cache/
    3DPN_P2.gdb/
  src/
    estate_ranking/
      __init__.py
      models.py
      ingest.py
      harmonise.py
      mtr_links.py
      validate.py
      export.py
      step_1.py
  tests/
    test_step_1.py
  precomputed/
    step_1/
      harmonised.gpkg
      reference_tables.sqlite
      source_manifest.json
      schema.json
      validation_report.json
      validation_report.md
      mtr_match_review.csv
      rejected_records.jsonl
      entity_ids.json
```

`__init__.py` identifies the code directory as a Python package. `models.py` defines the shared data structures. `ingest.py` reads files and inventories sources. `harmonise.py` standardises coordinates, fields, IDs, and estate categories. `mtr_links.py` matches MTR references. `validate.py` performs checks. `export.py` saves and reopens outputs. `step_1.py` coordinates the run.

The shared spatial fields will include `id`, `source_id` where available, `name`, language-specific names where supplied, `entity_type`, geometry, and provenance reference. `name` gives the original design's simple `id`/`name`/`geometry` interface a display name, using English first and a documented Chinese fallback. Paths without names will keep the name missing. Dataset metadata carries CRS; type-specific fields retain the distinctions explained above.

| Planned function | Operation in plain language |
|---|---|
| `inventory_sources(config)` | Find exactly the selected inputs and record their origins and fingerprints. |
| `inspect_network(gdb_path)` | Describe the database's layers, field definitions, coordinate system, and counts; coordinate separate domain extraction. |
| `load_network(gdb_path)` | Read paths and supporting tables without building connections. |
| `load_estates()`, `load_hospitals()`, `load_mtr_exits()`, `load_bus_stops()` | Read the relevant source and return the shared working structure. |
| `to_common_crs(dataset, target="EPSG:2326")` | Convert horizontal positions while retaining original coordinates and height metadata. |
| `assign_housing_districts(estates, crosswalk)` | Add documented allocation categories and report failed/ambiguous matches. |
| `link_mtr_tables(...)` | Build supported station/exit/facility relationships and review records. |
| `validate(datasets, tables, manifest)` | Produce structured check results with errors and warnings. |
| `write_outputs(...)` | Save a candidate result, reopen it for checks, and finalise a successful run. |

### Steps we will take

1. We will create the configuration and code structure under `work/` and define the common schema before implementing individual readers.
2. We will implement readers and transformations in their corresponding modules, returning the shared data structures.
3. We will create the override-table formats and the persistent ID registry, including validation for references and conflicting entries.
4. We will implement structured validation results and the export/round-trip process.
5. We will make `step_1.py` run the operations in order: inventory, database extraction/inspection, source loading, coordinate/field standardisation, identity/category/MTR matching, validation, staged export, and finalisation.
6. We will resolve paths from the configuration's declared project root, rather than from whichever folder happened to start Python.
7. We will document one command for running the completed pipeline. From the repository root, it will be:

```sh
cd work
PYTHONPATH=src ../.venv/bin/python -m estate_ranking.step_1 --config config/step_1.json
```

`cd work` selects the working directory. `PYTHONPATH=src` tells Python where our code lives. `../.venv/bin/python` selects the existing environment one directory above. `-m estate_ranking.step_1` runs the program module, and `--config` points to the file containing the selected inputs and settings. This command will become runnable after implementation.

## 13. Build in milestones and decide when Step 1 is finished

### Explanation for the team

A **milestone** is an intermediate result we can inspect before completing the whole stage. This keeps a problem in one area from remaining hidden until the final export.

A completed Step 1 means we have prepared, traceable inputs for later work. It does not mean we have measured walking distances or certified an accessible journey. Uncertainty can be retained honestly, but the next stage must resolve any uncertainty that affects the operation it is about to perform.

### Steps we will take

1. **Milestone 1 — inputs and storage:** We will complete the explicit source inventory, confirm the environment, safely extract the database, and prove the required output types can survive saving and reopening.
2. **Milestone 2 — loaded, aligned data:** We will load paths, all supporting tables, estates, hospitals, MTR records, and stops into the shared structures and standardise horizontal coordinates.
3. **Milestone 3 — relationships:** We will complete estate allocation assignments, supported MTR matches, review/override mechanisms, persistent identities, and bus-list reconciliation.
4. **Milestone 4 — checked deliverables:** We will run the focused fixtures and one full real-data pipeline run, then save the outputs, manifest, schema, and reports through the documented command.
5. We will consider Step 1 finished when every input record is accounted for, published spatial layers use EPSG:2326 horizontally, original network heights survive, all 244 current estates have one documented allocation category, required checks pass, and unresolved evidence is visible in the report.
6. We will review the human-readable report before starting graph construction and identify which remaining issues block a particular later operation.

## 14. Keep later decisions visible without guessing their answers

### Explanation for the team

Some questions affect the final ranking but do not require an answer to read and preserve the source data. Recording them now prevents an implementation choice from quietly becoming a project policy.

For example, “avoid stairs” and “independent wheelchair access” can lead to different rules for assisted stair lifts. Similarly, the choice to rank against any supplied institution or only A&E hospitals affects the final hospital score.

The **DTM**, or digital terrain model, describes bare-earth elevation. Its five-metre cells do not represent the height of every footbridge or elevated walkway. It can be useful later for terrain or connector checks, but it should not overwrite the network's supplied heights.

### Steps we will take

1. We will record the need to confirm gradient units, directional meaning, and `Shape_Length` interpretation before those source values are used in route costs.
2. We will carry forward the access-policy decision for escalators, stair lifts, wheelchair aids, and steep ramps. Later filtering must implement the intended user requirements explicitly.
3. We will retain estate/hospital entrance uncertainty and identify where better entrance or block coordinates would improve later snapping.
4. We will carry unresolved MTR aliases into the review table and resolve relevant cases before relying on those matches.
5. We will retain pickup/drop-off code meanings and wheelchair boarding evidence as questions requiring documentation before transport eligibility uses them.
6. We will leave the definition of “any hospital” and inclusion of GMB to later query configuration while preserving the data needed for either choice.
7. We will leave the DTM optional for later terrain/connector work. Step 1 will not resample it or use it to replace path heights.
8. If a documentary gap requires external information, we will identify the exact missing evidence and source. We can proceed with locally supported preparation and explicit unknowns, while blocking any later operation that needs an unresolved answer.
