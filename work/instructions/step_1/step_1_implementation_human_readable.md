# Step 1 implementation plan: prepare consistent data for estate ranking

Prepared and rechecked on 13 October 2026. Revised to explain the work for team members who have project ideas but are less familiar with programming and geographic-data terminology.

This is the plan for **Step 1, “Harmonise data”**, in `estate_ranking_design.md`. The Step 1 pipeline is implemented and has completed a full real-data run with **0 errors and 93 warnings**. All 476,153 spatial records and all saved reference-table values passed read-back checks. The focused test suite has **14 passing tests**. Access schedules are excluded and successful precomputed outputs can be tracked in Git.

See [running instructions](../../README.md), [validation report](../../precomputed/step_1/validation_report.md), and [MTR match review](../../precomputed/step_1/mtr_match_review.csv).

**Checklist status:** `[X]` means the listed implementation action is complete. `[ ]` means it is unresolved or belongs to later work. Saving an unknown value is complete preparation, but does not resolve that unknown. Unresolved coordinate evidence, gradient interpretation, entrance evidence, and MTR cases remain unchecked below.

## How to read this plan

Every area separates two kinds of writing:

- **Explanation for the team** describes what the terms mean, why the work matters, and what the result will tell us.
- **Steps we will take** describes the implementation work, in order. The original action wording is retained; Markdown checkboxes now record which actions are complete and which questions remain open.

The file names and Python function names remain in the document so developers can connect the explanation to the implementation. An explanation is provided before technical terms are needed. The numbered areas below are parts of Step 1; they are not the five main stages of the overall ranking algorithm.

## 1. What Step 1 will accomplish

### Explanation for the team

Our files describe different things: housing estates, hospitals, transport access points, and pedestrian paths. They come in different formats and do not necessarily use the same conventions for names, coordinates, or missing information.

**Ingestion** means opening a source file and reading its contents into the program. **Harmonisation** means making the information consistent enough to use together. For example, an estate may use `Estate Map Longitude`, while a hospital uses `longitude`. We can give both a consistent working field without changing the original file. A **field** is one named item of information, similar to a spreadsheet column; a **record** is one item being described, similar to a row.

Step 1 will produce separate, cleaned working datasets. We will still have an estate table, a hospital table, a transport-access table, and a path table. They will share conventions for identifying records, storing locations, and documenting uncertainty. Combining their conventions does not mean putting every kind of information into one large table.

A later stage will turn the pedestrian paths into a **graph**: a structure with connection points and links between them. Another stage will **snap** estate and facility points to suitable paths, meaning find and record where they connect to the walking network. Later stages will calculate journeys and rank estates. Step 1 prepares the inputs for that work.

**Opening-hours decision:** We will assume every route is open all the time, on every day and date. We will ignore access schedules throughout preparation and routing. This removes the need to ask for a journey time or date. It does not make stairs, steep gradients, or physical barriers suitable; those still need their own later rules. This is our modelling assumption, not a claim that every real-world route operates continuously.

The sources do not establish everything we might want to know. An estate map point may not be its accessible gate. A lift label does not establish whether the lift works today. We will preserve those distinctions so later stages can make informed decisions.

### Steps we will take

- [X] **1.** We will read `estate_ranking_design.md` and `whole_chat_export.md` together and keep the scope tied to their first main stage.
- [X] **2.** We will load the source files, standardise their fields and coordinates, add the four Housing Authority allocation categories, and connect related MTR reference tables.
- [X] **3.** We will check the prepared data and save it with reports describing the sources and any unresolved issues.
- [X] **4.** We will preserve information needed for later stages, including path heights, slope values, and uncertainty about entrances. We will exclude access schedules and treat every route as always open.
- [X] **5.** We will leave graph construction, stair exclusion, route costs, snapping, shortest-path calculation, and ranking to their corresponding later stages.
- [X] **6.** We will keep new code and outputs under `work/`, use the repository's local `.venv`, and leave original source files unchanged. We will install no packages during this planned implementation. If a necessary missing dependency is discovered, we will explain why and request permission before installing it. No Homebrew packages are needed by the current plan.

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
| Pedestrian paths and related tables | `work/data/3D_Pedestrian_Network_FGDB.zip` | A geographic database named `3DPN_P2.gdb`, with 465,892 path records and seven supporting tables. We will use five reference tables and skip the two access-schedule tables. |
| MTR access points | `work/data/mtr_access_points.geojson` | 611 access records, with names, locations, station/site descriptions, and access categories. |
| Railway station reference points | `work/data/railway_stations.geojson` | 98 station records. Station map points are different from station entrance points. |
| Combined bus/minibus stops | `work/data/bus_stops.json` | 9,264 distinct stop IDs, including 4,776 stops labelled GMB. |
| Original bus route-stop records | `work/data/JSON_BUS.json` | 56,209 records describing stops used by routes. A stop can appear many times. |
| Original minibus route-stop records | `work/data/JSON_GMB.json` | 13,155 route-stop records. |
| MTR reference CSVs | `data/organized/core/mtr/` | Station/line list, facility list, and facility-category definitions. The facility list's exit-coordinate fields are empty. |
| Estate allocation-category lookup | `analysis/maps/estate_housing_district_crosswalk.csv` | A mapping for all 244 estate names: Urban 109, Extended Urban 70, New Territories 60, Islands 5. |
| Documentation | The two PDFs in `work/data/`, plus existing reports under `analysis/` | Definitions and prior findings that help interpret the source fields. |

A **crosswalk**, in data processing, is a lookup table connecting records or labels. Here it means an estate-name-to-allocation-category lookup, not a pedestrian crossing. Section 6 shows the exact existing file and explains why its coordinates are copied estate map points.

JSON is a text format for structured records; CSV is a spreadsheet-like text format; GeoJSON is structured text that also describes geographic shapes. ZIP is a compressed package containing other files. We will use a suitable reader for each format.

### Steps we will take

- [X] **1.** We will create `work/config/step_1.json` with an explicit path and purpose for each selected input.
- [X] **2.** We will prefer the copies in `work/data` and list exact supplementary paths when information is only available outside `work`.
- [X] **3.** We will copy the needed MTR CSVs, estate crosswalk, and supporting documentation into `work/data/reference/`, recording their original locations and checksums.
- [X] **4.** We will calculate each selected input's checksum and file size. For compressed files, we will also record which contained files we use.
- [X] **5.** We will record known publication/download dates separately from file modification times, leaving dates unknown when evidence is unavailable.
- [X] **6.** We will record the installed Python and library versions so someone can reproduce the run.
- [X] **7.** We will compare the crosswalk's names and coordinates with the selected estate file before reusing it. The recheck found exact coordinate matches for all 244 current estates.
- [X] **8.** We will save these findings in `source_manifest.json`. We will read existing analysis for evidence but will not run or import scripts that write to hard-coded destinations outside `work`.

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

- [X] **1.** We will confirm the installed environment at the start of implementation and write code compatible with Python 3.9.
- [X] **2.** We will define `SpatialDataset` in `models.py`. It will contain ordered named attribute arrays, a same-length Shapely geometry array, field types, missing-value information, coordinate-system information, and source metadata.
- [X] **3.** We will define a similar structure for supporting tables that contain descriptions and relationships but no geographic shapes.
- [X] **4.** We will make every source reader return these structures, so later stages do not have to understand each original file format.
- [X] **5.** We will keep source field types available when converting values. Where necessary, we will use a separate null mask: a record-by-record indicator of which values are missing.
- [X] **6.** We will preserve original attributes, or a precise reference to their original records, alongside the standardised fields.
- [X] **7.** We will use Pyogrio's raw reader, NumPy, Shapely, PyProj, and Python's built-in file/table tools. GeoPandas with GeoParquet remains an alternative if later needs justify installing additional libraries; it is not required for this plan.

## 4. Put locations into one map reference system

### Explanation for the team

Coordinates only make sense when we know the rules behind them. A **coordinate reference system**, or **CRS**, specifies those rules. One file may express a location as longitude/latitude; another may use distances east and north within a Hong Kong map grid. Comparing their numbers directly would be meaningless.

**WGS84** is the geographic reference used by the iGeoCom point geometries. Its longitude/latitude values are angles. **EPSG:2326** is the identifier for Hong Kong 1980 Grid, a projected map system using metres. “EPSG” codes are reference numbers for defined coordinate systems.

Our working X/Y convention will be X=easting and Y=northing. Easting measures position eastward in the grid; northing measures position northward. For longitude/latitude inputs, X means longitude and Y means latitude. The program must keep that ordering consistent. PyProj's `always_xy=True` explicitly enforces it when we call coordinate transformations directly.

The pedestrian network also contains **Z**, or height. Its height reference is Hong Kong Principal Datum, **HKPD**, identified as EPSG:5738. Together, a horizontal map reference and a height reference form a **compound CRS**. Keeping the same horizontal grid does not mean we have converted heights. Estate and hospital points lack documented heights, so assigning height zero would invent information.

The iGeoCom file gives two representations of each access point: WGS84 geometry and HK1980 easting/northing attributes. We can transform one and compare it with the other. Their separation is a **residual**, a measured disagreement. In the checked access records, the separation is approximately 0.03–1.77 metres. Small disagreement can reflect source precision; large disagreement would need investigation.

### Steps we will take

- [ ] **1.** We will determine and record the source CRS for each input using embedded metadata or source documentation. **Still open:** the supplied estate specification (PDF page 6), hospital specification (PDF page 2), and bus specification (PDF page 1) define latitude/longitude fields but do not explicitly name WGS84 or another datum. WGS84 therefore remains an explicit assumption for these three inputs. iGeoCom WGS84 is confirmed by its dictionary, PDF page 6; the network CRS is confirmed by its embedded metadata and 3DPN dictionary, PDF page 8.
- [X] **2.** For a JSON point list without embedded CRS, we will look for documentary evidence supporting WGS84. If that is unavailable locally, we will explicitly label any WGS84 assumption in configuration and the report and check it against independent reference coordinates where possible. We will stop output finalisation for a source with neither a supported CRS nor an explicit accepted assumption.
- [X] **3.** We will retain original longitude/latitude and any original grid coordinates, so conversions can be audited.
- [X] **4.** We will transform point X/Y coordinates into EPSG:2326 using `Transformer.from_crs(..., always_xy=True)`.
- [X] **5.** We will retain the network's existing EPSG:2326 X/Y values and its original Z values. We will record its HKPD height reference separately.
- [X] **6.** We will leave facility heights unknown and will not sample the terrain raster or introduce height zero in Step 1.
- [X] **7.** We will use iGeoCom's WGS84 geometry as the main point location and compare its transformed X/Y with the supplied grid attributes. We will record residuals and configurable review thresholds rather than average the two locations.
- [X] **8.** We will check plausible geographic bounds and convert selected transformed coordinates back to their source system to check the transformation. Bounds alone will not prove accurate alignment or district membership.

## 5. Open and preserve the pedestrian network

### Explanation for the team

A **File Geodatabase** is a geographic database stored as a directory ending in `.gdb`. Our ZIP contains `3DPN_P2.gdb`. A **layer** groups one kind of geographic information, like a sheet in a workbook. The main layer, `PedestrianRoute`, contains paths. Seven other tables exist in the source: five contain references we will use, and two contain access schedules we will ignore. The presence of a schedule in the source will not change our always-open assumption.

The path geometry is `MultiLineString Z`. A **LineString** is a line described by a sequence of points. A **vertex** is one of those points. “Multi” means a record can contain more than one line part; “Z” means the coordinates include heights. We must keep the intermediate vertices because they describe bends and height changes. We must also keep separate line parts and their order.

The listed layers contain no separate node layer. Nodes are connection points used by the later graph. We will preserve the path information needed to construct them later rather than assume the database already supplies them.

Some attributes use codes rather than words. A **coded domain** is the dictionary explaining those codes. In several yes/no fields, `1` means true and `2` means false; ordinary Python conversion would treat both nonzero numbers as true. That would produce incorrect access information.

The network's `WheelchairAccess` field describes whether a connection to a facility/building/site is an accessible entrance. It does not mean every path must have that flag to be usable. `WheelchairBarrier` is a different field. Their meanings must remain separate.

**Gradient** describes steepness as an angle. The provider's `3DPN_DataDictionary_v2.2.pdf` confirms radians on PDF page 12. For example, converting an angle to a rise/run slope uses `tan(angle)`; multiplying that ratio by 100 expresses a percentage slope. `Shape_Length` is confirmed to be horizontal length in metres on PDF page 14. It measures the complete XY polyline, including bends, without adding height changes. Our check of all 465,892 paths found an exact match between this field and the calculated XY length.

**Still open:** the dictionary does not explicitly explain gradient sign or how the segment value summarises a path whose slope changes between vertices. All gradients in this snapshot are nonnegative even though vertex order includes both rising and falling paths. `Direction` specifies permitted travel relative to the drawn line, not an uphill/downhill sign. Later routing can derive directional slopes from ordered vertex heights, with an explicit rule for paths containing slope changes. This remaining routing interpretation is unchecked in Area 14.

### Steps we will take

- [X] **1.** We will inspect ZIP member paths and reject extraction paths that would escape `work/cache/`. We will extract the database to `work/cache/3DPN_P2.gdb`.
- [X] **2.** We will associate the extraction with the ZIP checksum. We will reuse it only when it matches the selected source contents.
- [X] **3.** We will call `pyogrio.list_layers()` and `read_info()` to record actual layer names, field definitions, row counts, geometry types, CRS, and geographic extent.
- [X] **4.** We will load `PedestrianRoute` using `pyogrio.raw.read()`, with bounded batches if needed for memory use. The current snapshot contains 465,892 records.
- [X] **5.** We will load the five non-schedule supporting tables separately: terminal, floor, building, site, and distance-post references. We will skip `AccessTime` and `AccessTimeDetails` entirely and record their deliberate exclusion in the source manifest. Their records will not be read or copied into the prepared outputs.
- [X] **6.** We will preserve `PedestrianRouteID`, all line parts, every vertex, every Z value, and original attributes. Important fields include `FeatureType`, `Gradient`, `Direction`, `WheelchairBarrier`, `WheelchairAccess`, `Enabled`, `Location`, `FloorID`, `TerminalID`, and `Shape_Length`. If the original path record includes `AccessTimeID`, we will keep it only as an unused source attribute so the original record remains traceable. We will not look up that ID or use it in any decision.
- [X] **7.** We will extract the archive's coded-domain definitions separately. The installed Pyogrio public API does not expose them through `read_info()`. The recheck found 18 readable `GPCodedValueDomain2` XML definitions inside `.gdbtable` files. XML is structured text; we will read only the bounded definition blocks and parse them using Python's built-in tools.
- [X] **8.** We will keep both source codes and decoded descriptions, and compare observed codes with the extracted dictionaries. If a dictionary cannot be read, we will check the documented fallback in `analysis/audit_summary.json` against the selected archive and record that use.
- [X] **9.** We have preserved `gradient_raw` and confirmed its unit as radians from the provider dictionary (PDF page 12). We have confirmed `Shape_Length` as horizontal polyline length in metres (PDF page 14), recorded both definitions in metadata/schema, and checked the source lengths against every original XY polyline. This tick covers preservation, confirmed units and length meaning. Gradient sign/within-path aggregation remain separate unresolved questions in Area 14.
- [X] **10.** We will assume every route is always open. We will not read opening hours, closing hours, day-of-week rules, or date restrictions. We will not join schedule references, produce schedule warnings, or restrict a route because of a schedule. Later routing will follow the same assumption and will not require a journey time or date.
- [X] **11.** We will keep all paths in Step 1. We will not split lines, merge endpoints, remove stairs, or create connections wherever lines cross on a flat map. Paths at the same X/Y but different heights must remain distinguishable.

## 6. Prepare estate locations and add Housing Authority allocation categories

### Explanation for the team

In this section, **crosswalk is a data-processing term for a lookup table**: a table that connects matching records or labels between two sources. Here it connects an estate name to its Housing Authority allocation category. It does **not** mean a pedestrian crossing, zebra crossing, or coordinates where someone crosses a road. We will call it the **estate allocation lookup** throughout this section to avoid that confusion.

There is no additional road-crossing dataset required by this section. The lookup already exists in earlier project analysis at [`analysis/maps/estate_housing_district_crosswalk.csv`](../../../analysis/maps/estate_housing_district_crosswalk.csv). Step 1 copied it into [`work/data/reference/estate_housing_district_crosswalk.csv`](../../data/reference/estate_housing_district_crosswalk.csv). The filename retains the old technical term. This is a project-derived lookup, not a separate official dataset supplied by the Housing Authority. Its construction and source limitations are described in [`HOUSING_DISTRICTS_README.md`](../../data/reference/HOUSING_DISTRICTS_README.md).

The table contains five columns: estate name, original administrative district, allocation category, latitude, and longitude. Its coordinates are copies of the **estate map points** in `work/data/prh-estates (1).json`. They are not road-crossing locations, a second set of estate locations, or verified estate entrance locations. We checked all 244 rows: the lookup coordinates exactly match the original estate coordinates.

For example:

| Estate | Administrative district in the estate data | Allocation category added by the lookup | Copied estate latitude | Copied estate longitude |
|---|---|---|---:|---:|
| Ap Lei Chau Estate | Southern | Urban | 22.24443 | 114.15216 |
| Butterfly Estate | Tuen Mun | New Territories | 22.37593 | 113.96182 |
| Cheung Ching Estate | Kwai Tsing | Extended Urban | 22.34968 | 114.10681 |

The **estate JSON remains the source of the estate's location**. The lookup supplies the allocation category. Comparing its copied coordinates with the JSON is an identity/snapshot check: it helps detect a lookup row that belongs to a different estate or an older location. It is not a walking-distance calculation and does not move the estate point.

The two district fields answer different questions. The estate JSON's administrative district is a local-government classification. The ranking query needs one of the four Housing Authority allocation choices: Urban, Extended Urban, New Territories, or Islands. We keep both fields, because changing the administrative district into an allocation category would lose original information.

A **join** means finding the matching lookup row for an estate and attaching the category from that row. We currently match the exact original English estate name and require exactly one lookup row. We also check that the original administrative district and copied coordinates agree. Similar-looking names are not enough to make a match.

Some administrative districts contain estates in different allocation categories. The existing lookup distinguishes Tung Chung from other Islands locations and Tseung Kwan O estates from the entire Sai Kung administrative area. Earlier map work used smaller geographic areas as **proxies**, or approximate representations of those towns. Those shapes are not HA-issued allocation boundaries. The assignments and their provenance remain documented; if we add a new estate later, we must establish its category rather than apply an unsupported whole-district shortcut.

An **estate ID** is the program's stable label for an estate. The source JSON does not supply a native estate ID in the inspected schema. We therefore maintain an ID registry: a saved list of estate identities and their assigned IDs. Reordering the source file will not change IDs. If an estate name changes, an explicit alias records that the new name belongs to the same estate.

### Steps we will take

- [X] **1.** Read the 244 estate records from `work/data/prh-estates (1).json` and preserve each original record. This file supplies the estate locations.
- [X] **2.** Extract each estate's multilingual names, administrative district, region, map latitude/longitude, and block information into consistently named working fields. Coordinate conversion follows Area 4; original coordinates remain available.
- [X] **3.** Prepare readable names by decoding text formatting such as `<br>`, while preserving the original text. Use the exact original name for identity/matching, so display cleanup does not accidentally change which estate is being matched.
- [X] **4.** Assign a stable estate ID using the source type and exact original English name. Check for duplicate identities instead of using the row number as the estate ID.
- [X] **5.** Store and reuse those IDs through the registry at `work/config/entity_ids.json`, backed by the successful output snapshot. Record future name changes as explicit aliases.
- [X] **6.** Label the supplied point `estate_map_point`. Do not describe it as a gate, entrance or individual block location: the source does not establish that.
- [X] **7.** Read the estate allocation lookup at `work/data/reference/estate_housing_district_crosswalk.csv`, verify its selected original copy, and find exactly one matching row for each estate by its exact source name. Stop finalising the output if a required match is missing or ambiguous.
- [X] **8.** Check that the lookup row's administrative district and copied estate coordinates agree with the estate JSON. Keep the estate JSON coordinates as the location source. The current 244 coordinate comparisons all match exactly; future disagreement will be reported for investigation.
- [X] **9.** Attach the lookup's allocation category as `housing_district`, retaining the original administrative district separately. Check the category is one of the four permitted values, record its lookup provenance, and report totals: Urban 109, Extended Urban 70, New Territories 60, Islands 5.
- [X] **10.** Save the prepared estate layer, the lookup and provenance, and the committed ID-registry snapshot with the successful outputs. Failed runs must not replace the previous successful data or identities.

The location preparation and allocation lookup are completed. Verification of real estate entrance locations remains a separate unchecked issue in Area 14; it is not established by the lookup coordinate check.

## 7. Prepare hospital locations

### Explanation for the team

The hospital file has 44 institutions, including A&E information. **A&E** means Accident and Emergency. Having no A&E department does not mean an institution has no value to someone who needs a particular hospital.

We should preserve all supplied institutions now. The later query can choose a particular hospital or define which institutions qualify when the user chooses none.

A **nullable boolean** is a yes/no field that can also be unknown. It matters because missing A&E information should not be changed into “No.” Hospital map points also need the same entrance uncertainty as estate points.

### Steps we will take

- [X] **1.** We will read the hospital JSON and retain original record references.
- [X] **2.** We will extract multilingual institution names, cluster, address, and coordinates.
- [X] **3.** We will create persistent hospital IDs through the same registry mechanism, using a separate hospital namespace.
- [X] **4.** We will interpret documented A&E yes/no values as `has_ae`, preserving missing or unrecognised values as unknown with a diagnostic.
- [X] **5.** We will transform the supplied coordinates using the policy in Area 4 and set `location_role="institution_map_point"`.
- [X] **6.** We will preserve all 44 institutions. We will leave A&E-only eligibility and preferred-hospital selection to later configuration.

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

- [X] **1.** We will load `mtr_lines_and_stations.csv`, `barrier_free_facilities.csv`, and `barrier_free_facility_category.csv` with `csv.DictReader` and `utf-8-sig`. This encoding handles an optional BOM, an invisible file-start marker that could otherwise become part of a column name.
- [X] **2.** We will keep IDs as strings, drop only wholly blank rows with an audit count, and separate unique station records from their line/direction memberships.
- [X] **3.** We will join facility `Key` to category `Item_Code` to attach the equipment definition.
- [X] **4.** We will join facility `Station_No` to station `Station ID`, reporting unknown station IDs and facility keys. We will recheck previously observed mismatches against the selected files.
- [X] **5.** We will load all 611 iGeoCom access records and all 98 railway-station reference records, retaining their native IDs, coordinates, names, source attributes, and subcategories.
- [X] **6.** We will build an explicit crosswalk between iGeoCom station/site names and the MTR station CSV. We will try documented prefix removal, whitespace/case normalisation, and exact English/Chinese comparison.
- [X] **7.** We will accept unambiguous matches under documented rules and save ambiguous or unmatched cases to `mtr_match_review.csv`, including the evidence and candidates where available.
- [X] **8.** We will apply recorded exceptions from `mtr_station_overrides.csv` and `mtr_exit_overrides.csv`. We will validate each exception's referenced records and retain why it was needed.
- [X] **9.** We will connect exit-specific facility descriptions only when the exit reference is unambiguous. Descriptions listing multiple exits will retain that relationship; unclear descriptions will remain unresolved. Station-level equipment will stay station-level.
- [X] **10.** We will add the dictionary-based access evidence label, its source, and station/exit match status to every access record. Conflicting evidence will be reported rather than silently overwritten.
- [X] **11.** We will keep unknown or unresolved entrances in the harmonised data with visible flags. We will not substitute station map points for entrances or decide routing eligibility during Step 1.

## 9. Prepare and verify bus and minibus stops

### Explanation for the team

The raw files describe stops as used by routes. If ten routes use one stop, the raw file may contain many records for it. The prepared `bus_stops.json` instead provides one point per stop ID. **Deduplication** means removing repeated representations of the same identity; it does not mean merging every nearby point.

Different stop IDs must remain separate even when names or locations coincide. They may represent different boarding points or services. GMB identifies green-minibus service, while KMB and CTB are other operator labels. We should retain all operators rather than treat the three named flags as an exhaustive list.

A service at a stop does not automatically allow boarding there in every direction, and operator membership does not establish wheelchair boarding access. The raw `stopPickDrop` field contains codes whose meanings must be documented before eligibility rules use them.

The recheck compared the prepared list with both raw inputs. The 9,264 IDs, coordinates, and combined operator sets matched exactly, with no coordinate conflict for one ID. The earlier builder used the parent's `JSON_BUS.json.1`; checksums confirm it equals `work/data/JSON_BUS.json`. The GMB copies also match. We will retain this evidence and still verify future runs.

### Steps we will take

- [X] **1.** We will load `bus_stops.json` as the preferred list and preserve `stop_id` as a source ID.
- [X] **2.** We will retain English/Chinese names, coordinates, the full operator list, and `GMB`, `KMB`, and `CTB` flags. We will make readable display names while retaining original text.
- [X] **3.** We will load both raw route-stop files with `utf-8-sig` and group records by source stop ID.
- [X] **4.** We will compare the raw ID union with the prepared list, check every stop's coordinates, combine operator memberships, and check the saved flags against that combined membership.
- [X] **5.** We will report naming variants and conflicting coordinates for one ID. We will keep distinct IDs separate and will not silently choose the first conflicting location.
- [X] **6.** We will preserve route/service evidence in a related table or a lossless reference to raw records. This includes `stopPickDrop`, `routeId`, `routeSeq`, `stopSeq`, `serviceMode`, and `lastUpdateDate`.
- [X] **7.** We will transform stop coordinates to EPSG:2326 and retain source coordinates and file provenance.
- [X] **8.** We will mark boarding-accessibility evidence as unknown when absent. We will retain undocumented pickup/drop-off codes without interpreting them, and keep GMB separate so later query configuration can include or exclude it.

## 10. Check that the prepared information is trustworthy

### Explanation for the team

**Validation** means checking that the data satisfies the rules needed by later stages. A program can finish without crashing and still produce incorrect locations or joins. We need checks that detect plausible-looking errors.

An **error** prevents the prepared output from being finalised, such as a coordinate system the program cannot interpret. A **warning** records a limitation while allowing the data to be retained, such as an entrance with unknown access evidence. A warning can still prevent a later routing operation if that operation needs the missing information.

**Referential integrity** means that an ID pointing to another table can be resolved appropriately. For example, a path's terminal ID should connect to the terminal reference table. Missing references need reports. A station can also have several line memberships, so those valid repeated relationships must not be mistaken for duplicate identities. Schedule IDs and schedule tables are excluded from these checks.

A **round-trip check** saves data, reopens it, and compares the result with what was written. This catches export problems, such as heights being dropped or missing values turning into zero. A **fixture** is a small deliberately chosen example used to test a consequential case without reading the whole dataset.

A **quarantined record** is preserved separately with a reason because it cannot be safely used. Quarantining does not silently make a blocking error acceptable. The program will account for every input record and will keep the previous successful output when a required check fails.

### Steps we will take

- [X] **1.** We will check required files and fields, declared types, unique entity IDs, and source record counts.
- [X] **2.** We will reconcile input counts with usable and quarantined records, accounting for every record. Current counts are snapshot expectations rather than permanently hard-coded dataset sizes.
- [X] **3.** We will check required coordinates for finite numeric values, plausible bounds, supported reference systems, and appropriate geometry types. We will not treat a broad Hong Kong bounding box as proof of precise location or category membership.
- [X] **4.** We will check all 244 current estate assignments for one documented allocation category and verify crosswalk coordinates against configured tolerances.
- [X] **5.** We will check MTR station/category relationships, non-schedule network references, source code dictionaries, and the bus-list reconciliation while respecting valid one-to-many relationships. We will not check schedule references or schedule records.
- [X] **6.** We will check path vertex counts, line-part structure, and Z preservation. We will retain vertical lift lines even when their flat-map length is zero and will not apply two-dimensional shape repair indiscriminately to 3D paths.
- [X] **7.** We will record coordinate comparison thresholds and units in configuration and report outliers as errors or review items under explicit rules.
- [X] **8.** We will use fixtures to check axis ordering, vertical/multipart geometry preservation, `1`/`2` code interpretation, nullable IDs, ambiguous matches, blank access categories, and colocated stops with distinct IDs.
- [X] **9.** We will stop finalisation for missing required inputs/fields, unresolved CRS without an accepted assumption, duplicate primary IDs, unusable required coordinates/geometries, missing or ambiguous estate categories, or failed read/write preservation. We will save the offending records and diagnostics.
- [X] **10.** We will report unresolved MTR matches, unknown access categories, entrance uncertainty, gradient interpretation gaps, suspicious source publication/update dates, and coordinate overlaps as visible issues. Source dates describe how old the data is; they are not used as route opening or closing dates. Later stages must enforce any requirements these affect.
- [X] **11.** We will write both `validation_report.json` for program use and `validation_report.md` for team review. Each issue will identify the source, relevant record, check, and consequence.
- [X] **12.** We will leave network connectivity checks to Step 2, where a graph and access policy exist. Step 1 cannot establish route reachability from file integrity alone.

## 11. Save the prepared data without losing information

### Explanation for the team

An **output format** determines how prepared data is stored for later use. A **GeoPackage**, ending in `.gpkg`, can hold several geographic layers in one file. It supports projected coordinates and 3D line shapes, which fit this project. **SQLite** is a local database format suitable for supporting tables; Python already includes tools for it.

The proposed spatial output is `harmonised.gpkg`; nonspatial tables go into `reference_tables.sqlite`. JSON and CSV provide readable structured reports and review lists. Conventional GeoJSON is intended for geographic coordinates, so GeoPackage is a clearer choice for the EPSG:2326 working layers.

The recheck confirmed the installed OpenFileGDB and GeoPackage readers/writers are available. A temporary two-layer GeoPackage preserved the geometry of a vertical lift and multipart 3D line, Chinese text, null text, and a null decimal value. It reopened as EPSG:2326. That is useful evidence, but full-data export checks must still cover additional types and records.

**WKB**, or Well-Known Binary, is a standard byte representation of a geometry. **WKT**, or Well-Known Text, is a text representation; CRS definitions also use a WKT form. We will keep the original full CRS definition in the manifest so the height reference remains documented even if a writer records only the horizontal CRS.

A **staging directory** is a temporary location for a candidate output. We validate that candidate before making it the current successful result. This protects a previously usable output if the next run fails.

### Steps we will take

- [X] **1.** We will create a staging directory for the run and save separate GeoPackage layers for paths, estates, hospitals, MTR access points, railway station references, and bus/minibus stops.
- [X] **2.** We will store the five non-schedule network reference tables, MTR relationships, and retained route/service evidence in SQLite or through documented lossless source references. The two access-schedule tables will not appear in the outputs. We will record the always-open assumption in the manifest and validation report.
- [X] **3.** We will encode list-valued fields, such as operators, as documented JSON text where the destination field cannot hold a list directly.
- [X] **4.** We will save `schema.json` describing each field's meaning, type, allowed codes, missing-value rules, and relationships.
- [X] **5.** We will save source metadata, including original compound CRS WKT, the HKPD height reference, input hashes, assumptions, and software versions.
- [X] **6.** We will reopen all outputs and compare IDs, counts, field types, nulls, Unicode names, timestamps, CRS, multipart structure, and vertex/Z coordinates with the prepared in-memory data. Any numerical tolerance will be documented.
- [X] **7.** We will save validation reports, MTR match-review records, rejected-record diagnostics, and a snapshot of the ID registry with the candidate output.
- [X] **8.** We will finalise the output and registry updates only after required checks pass, preserving the previous successful result on failure. Implementation must ensure incomplete staged changes are not selected as current outputs.
- [X] **9.** If the installed writer cannot preserve a necessary feature, we will use an explicitly documented WKB/SQLite representation or explain why an additional library is necessary and request permission before installing it. We will not silently drop heights or change types.

## 12. Organise the program and make it runnable

### Explanation for the team

A **module** is a Python file grouping related work. A **function** is a named operation within that program. Separating reading, matching, checking, and writing makes problems easier to locate and allows later stages to reuse the prepared data.

The proposed structure is shown below. The code, configuration and successful output files now exist. The directory tree below describes their roles; the extracted database is stored under a checksum-specific subdirectory of `cache` so different source snapshots are kept separate. `config` holds deliberate choices, `data` holds inputs, `cache` holds reusable extraction, `src` holds program code, and `precomputed` holds saved results.

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
| `load_network(gdb_path)` | Read paths and the five non-schedule supporting tables without building connections; skip the two access-schedule tables. |
| `load_estates()`, `load_hospitals()`, `load_mtr_exits()`, `load_bus_stops()` | Read the relevant source and return the shared working structure. |
| `to_common_crs(dataset, target="EPSG:2326")` | Convert horizontal positions while retaining original coordinates and height metadata. |
| `assign_housing_districts(estates, crosswalk)` | Add documented allocation categories and report failed/ambiguous matches. |
| `link_mtr_tables(...)` | Build supported station/exit/facility relationships and review records. |
| `validate(datasets, tables, manifest)` | Produce structured check results with errors and warnings. |
| `write_outputs(...)` | Save a candidate result, reopen it for checks, and finalise a successful run. |

### Steps we will take

- [X] **1.** We will create the configuration and code structure under `work/` and define the common schema before implementing individual readers.
- [X] **2.** We will implement readers and transformations in their corresponding modules, returning the shared data structures.
- [X] **3.** We will create the override-table formats and the persistent ID registry, including validation for references and conflicting entries.
- [X] **4.** We will implement structured validation results and the export/round-trip process.
- [X] **5.** We will make `step_1.py` run the operations in order: inventory, database extraction/inspection, source loading, coordinate/field standardisation, identity/category/MTR matching, validation, staged export, and finalisation.
- [X] **6.** We will resolve paths from the configuration's declared project root, rather than from whichever folder happened to start Python.
- [X] **7.** We will document one command for running the completed pipeline. From the repository root, it will be:

```sh
cd work
PYTHONPATH=src ../.venv/bin/python -m estate_ranking.step_1 --config config/step_1.json
```

`cd work` selects the working directory. `PYTHONPATH=src` tells Python where our code lives. `../.venv/bin/python` selects the existing environment one directory above. `-m estate_ranking.step_1` runs the program module, and `--config` points to the file containing the selected inputs and settings. This command is implemented and has been run successfully with the supplied data.

## 13. Build in milestones and decide when Step 1 is finished

### Explanation for the team

A **milestone** is an intermediate result we can inspect before completing the whole stage. This keeps a problem in one area from remaining hidden until the final export.

A completed Step 1 means we have prepared, traceable inputs for later work. It does not mean we have measured walking distances or certified an accessible journey. Uncertainty can be retained honestly, but the next stage must resolve any uncertainty that affects the operation it is about to perform.

### Steps we will take

- [X] **1.** **Milestone 1 — inputs and storage:** We will complete the explicit source inventory, confirm the environment, safely extract the database, and prove the required output types can survive saving and reopening.
- [X] **2.** **Milestone 2 — loaded, aligned data:** We will load paths, the five non-schedule supporting tables, estates, hospitals, MTR records, and stops into the shared structures and standardise horizontal coordinates.
- [X] **3.** **Milestone 3 — relationships:** We will complete estate allocation assignments, supported MTR matches, review/override mechanisms, persistent identities, and bus-list reconciliation.
- [X] **4.** **Milestone 4 — checked deliverables:** We will run the focused fixtures and one full real-data pipeline run, then save the outputs, manifest, schema, and reports through the documented command.
- [X] **5.** We will consider Step 1 finished when every selected input record is accounted for, the two schedule tables are documented as deliberately excluded, published spatial layers use EPSG:2326 horizontally, original network heights survive, all 244 current estates have one documented allocation category, required checks pass, and unresolved evidence is visible in the report.
- [X] **6.** We will review the human-readable report before starting graph construction and identify which remaining issues block a particular later operation.

## 14. Keep later decisions visible without guessing their answers

### Explanation for the team

Some questions affect the final ranking but do not require an answer to read and preserve the source data. Recording them now prevents an implementation choice from quietly becoming a project policy.

For example, “avoid stairs” and “independent wheelchair access” can lead to different rules for assisted stair lifts. Similarly, the choice to rank against any supplied institution or only A&E hospitals affects the final hospital score.

The **DTM**, or digital terrain model, describes bare-earth elevation. Its five-metre cells do not represent the height of every footbridge or elevated walkway. It can be useful later for terrain or connector checks, but it should not overwrite the network's supplied heights.

Access schedules are a settled decision: routes are always open in this model. We will not carry opening-hours questions forward or ask users to choose a journey date/time.

### Steps we will take

- [ ] **1.** We will choose and verify a directional-slope and within-path aggregation rule for routing. Gradient units (radians) and source length (horizontal metres) are confirmed. The provider dictionary does not explicitly define gradient sign or how it summarises changing slopes, so those two routing questions remain open.
- [ ] **2.** We will carry forward the access-policy decision for escalators, stair lifts, wheelchair aids, and steep ramps. Later filtering must implement the intended user requirements explicitly.
- [ ] **3.** We will retain estate/hospital entrance uncertainty and identify where better entrance or block coordinates would improve later snapping.
- [ ] **4.** We will carry unresolved MTR aliases into the review table and resolve relevant cases before relying on those matches.
- [ ] **5.** We will implement transport-target eligibility using the now-confirmed pickup/drop-off meanings: 1=drop-off only, 2=pick-up only, 3=both. The new bus PDF resolves those definitions. Code 0 remains undocumented (25 source rows at two stop IDs), and wheelchair boarding evidence remains unresolved. Definitions being known does not mean the eligibility rule has already been implemented.
- [ ] **6.** We will leave the definition of “any hospital” and inclusion of GMB to later query configuration while preserving the data needed for either choice.
- [ ] **7.** We will decide whether later connector/terrain checks benefit from the DTM. Its exclusion from Step 1 is already implemented; the unchecked item concerns possible later use, not a failure to prepare the current data.
- [ ] **8.** If a documentary gap requires external information, we will identify the exact missing evidence and source. We can proceed with locally supported preparation and explicit unknowns, while blocking any later operation that needs an unresolved answer.

## Resolution register: what is confirmed and what remains

Updated 13 October 2026 after checking all six provider PDFs, the estate allocation lookup, and the latest prepared outputs. This replaces the earlier unresolved-only list. `[X]` marks a confirmed fact or completed preparation action. Every unresolved item remains `[ ]`. Suggested next actions are not claims of completion.

The latest full run has **0 blocking errors and 93 warning records**. Repeated warnings can describe the same underlying issue: for example, 72 facility rows refer to just two missing station IDs. This register lists the underlying questions rather than treating every warning row as a separate problem. Some entries are source-verification work; others are decisions or implementation belonging to later stages.

### 1. Coordinate systems

**Confirmed**

- [X] The pedestrian network uses HK1980 Grid horizontally and HKPD heights in metres. This is documented in its embedded CRS and the 3DPN dictionary, PDF page 8.
- [X] iGeoCom geometry uses WGS84, and its easting/northing attributes use HK1980 Grid. Its dictionary confirms this on PDF page 6.
- [X] The estate, hospital and bus specifications define their latitude/longitude fields. Point transformation, bounds checks, preservation and coordinate round-trip checks are implemented.

**Still needed**

- [ ] **1.1 — Estate datum confirmation.** Find an explicit publisher definition of the datum behind Estate Map Latitude/Longitude. The estate specification defines the fields on PDF page 6 but does not name WGS84. Current processing retains an explicit WGS84 assumption.
- [ ] **1.2 — Hospital datum confirmation.** Find equivalent explicit confirmation for hospital latitude/longitude. The hospital specification's PDF page 2 names the fields but not the datum. WGS84 remains recorded as an assumption.
- [ ] **1.3 — Bus datum confirmation.** Establish the publisher's coordinate-reference interpretation for the supplied bus/GMB GeoJSON. The new bus specification names latitude/longitude but does not explicitly name the datum. Coordinate order in the actual files is already checked as longitude, latitude; that is separate from datum confirmation.

These are evidence gaps rather than failed coordinate transformations. See [the provider-document review](../../precomputed/docs/step_1_provider_documentation_review.md).

### 2. Gradient and length

**Confirmed**

- [X] Gradient is measured in **radians**, confirmed by the 3DPN dictionary, PDF page 12.
- [X] Shape_Length is **horizontal XY polyline length in metres**, confirmed on PDF page 14.
- [X] All 465,892 supplied lengths exactly match the calculated XY polyline lengths, including bends.
- [X] The original gradients, source lengths, all vertices and Z heights are preserved. Definitions and provider-page references are saved in metadata/schema.

**Still needed for the later cost model**

- [ ] **2.1 — Directional slope rule.** Decide how uphill and downhill costs will be derived. The supplied gradients are nonnegative, and the dictionary does not explicitly define a gradient sign convention. An explicit calculation from ordered vertex heights can supply direction; the permitted-travel Direction field must not be used as a slope sign.
- [ ] **2.2 — Changing slopes along a path.** Decide whether to use the provider's single segment angle or calculate and combine costs between successive vertices. The dictionary does not explain within-path aggregation. Inspect representative paths, define the chosen calculation, and check that a climb followed by a descent is handled appropriately.
- [ ] **2.3 — Cost and facility rules.** Select the length-plus-gradient penalty or time model for the intended users, including a separate lift rule and any hard slope limit. These are Step 2 model choices, not unknown gradient units. Confirmed radians can be used directly by an angle-based penalty or converted with tan(angle) for a rise/run-based model.

### 3. Source relationships, accessibility evidence and remaining choices

**Confirmed or already handled**

- [X] All 244 current estate names and copied lookup coordinates match the estate input, with one documented allocation category per estate. The lookup is a project-derived mapping table; it contains estate points, not pedestrian-crossing coordinates.
- [X] All 9,264 bus/minibus stop IDs, coordinates and operator memberships reconcile with the raw sources. Distinct colocated IDs remain separate.
- [X] The new bus specification, PDF page 1, defines stopPickDrop: **1=drop-off only; 2=pick-up only; 3=pick-up and drop-off**. Those definitions are now confirmed; the current pipeline still retains raw codes without applying target-eligibility filtering.
- [X] Both Castle Peak Hospital site-reference versions are preserved with distinct source-record identities. No duplicate primary-record error remains.
- [X] Access schedules are excluded and all routes are assumed always open. They are not an unresolved question.
- [X] Required input/schema, primary identity, finite-coordinate, geometry, estate-category and full export/read-back checks passed for the selected snapshot. These checks do not establish real-world entrance or boarding accessibility.

**Still needed**

- [ ] **3.1 — MTR matching: 45 review records.** Resolve 28 ambiguous station matches, 5 unmatched records, and 12 exit-code parsing cases. The ambiguous examples include physical stations with separate Airport Express/Tung Chung Line IDs; model that one-to-many relationship rather than select an arbitrary ID. Review naming variants and missing references for the other cases. Some fixes can use existing local data; others may need provider information. Record every accepted match and rerun the matcher. See [the review CSV](../../precomputed/step_1/mtr_match_review.csv).
- [ ] **3.2 — Facility station IDs 70 and 888.** Establish which station records these IDs represent. They account for 72 facility rows missing from the station CSV. Obtain a documented ID mapping or compatible station list; do not invent replacement IDs.
- [ ] **3.3 — Five differences in entrance evidence.** Check the exact entrance, equipment scope and source dates where iGeoCom and linked CSV evidence describe different access types. A ramp and lift may coexist, so a difference does not automatically establish an error. Preserve both pieces of evidence until interpretation is supported.
- [ ] **3.4 — Unspecified MTR access evidence.** iGeoCom has 362 blank access categories. Of these, 23 have positive named-exit CSV facility evidence already retained; 339 have no positive linked CSV evidence. Inspect the 23 supplemented cases and seek entrance-specific evidence for relevant remaining cases. No record becomes certified accessible merely because a category or link is present.
- [ ] **3.5 — Missing non-schedule references.** Investigate 9 terminal IDs affecting 11 path rows, 3 floor IDs affecting 34 rows, 107 site IDs affecting 280 rows, and 44 BuildingID_1 values affecting 248 rows. Nine distance-post records also refer to missing path IDs. Check source-version compatibility and whether additional iB1000/reference information is required. Resolve the references used by later processing; do not drop otherwise preserved paths automatically. BuildingID_2 has no missing-reference finding in this snapshot.
- [ ] **3.6 — Preferred site-reference version, if needed.** If a later operation needs one canonical Castle Peak Hospital site record, establish a version-selection rule. Both versions are safely preserved; choosing one is not required merely to keep the records.
- [ ] **3.7 — Estate and hospital entrances.** Obtain or verify usable gates/entrances, or explicitly accept a map-point approximation with visible uncertainty. Checking lookup coordinates establishes consistency with the estate JSON, not entrance usability. This affects Step 3 point-to-network connectors.
- [ ] **3.8 — Code 0 and boarding-target eligibility.** The bus PDF does not define stopPickDrop=0. It occurs in 25 raw bus rows at two stop IDs. Obtain its meaning or define an explicit unknown-record policy. Implement eligibility using confirmed codes 1/2/3 without treating an unknown row as proof that an entire stop is unusable; other services at that stop may permit boarding. This is separate from wheelchair boarding.
- [ ] **3.9 — Wheelchair boarding and complete MTR access.** Obtain appropriate vehicle/boarding and street-to-platform evidence where the ranking requires it. Bus operator membership does not establish accessible boarding; MTR entrance equipment alone does not establish the complete journey. Define how unverified targets are reported or excluded for the intended users.
- [ ] **3.10 — Mobility/access policy.** Specify the intended user requirements and eligibility of escalators, stair lifts, wheelchair aids, travelators and steep ramps. The requirement to avoid stairs is already stated, but graph filtering is a later implementation step. Decide which assisted facilities qualify before applying suitability rules.
- [ ] **3.11 — Hospital target group and transport scope.** Decide whether the no-preference hospital group includes every supplied institution or only an A&E subset, and whether GMB is included in bus access. Preserve the current data for either choice and implement the selected configuration later.
- [ ] **3.12 — Allocation-boundary scope for future additions.** Current estate categories are complete and documented. The town-area polygons used in earlier analysis are geographic proxies rather than HA-issued allocation boundaries. If new estates are added, verify their allocation category instead of extending the proxy or administrative-district shortcut without evidence.
- [ ] **3.13 — Optional DTM use.** Step 1's exclusion of the terrain raster is complete. Decide whether later connector/terrain checks need it, while retaining original elevated-path heights. This is optional later work, not a missing Step 1 output.
- [ ] **3.14 — Dataset currency and location overlaps where relevant.** Full source-date plausibility auditing and real-world interpretation of overlapping records have not been completed. Review dates and co-located identities where they affect a selected match or access claim. No suspicious-date error was raised by the latest run; this does not imply a comprehensive date audit passed. Source dates concern dataset currency, not opening-hour restrictions.

Resolving an item means obtaining its evidence or agreeing/implementing its rule, recording the decision, and running the checks affected by it. Keep every still-open item unchecked. The historical validation report remains the record of the prepared snapshot; this register records what the newer documents now establish and what implementation/review is still needed.
