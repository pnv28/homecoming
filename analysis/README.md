# Hong Kong pedestrian, terrain, and mobility analysis: complete handoff

Last documented: **12 October 2026**. Counts and findings below describe the local
snapshots inspected in this project. They are not a live inventory of Hong Kong.

This is the main entry point for a human or agent returning to the project. It explains
the source files, the work completed, how the generated files should be interpreted,
how to reproduce them, and which questions remain unresolved. The scripts and JSON
summaries are the implementation and numerical evidence; this document explains their
relationships and limitations.

## 1. What this project currently does

The work completed includes:

1. Auditing estate, hospital, bus, MTR, and pedestrian-network inputs, including the
   geodatabase's coded-value domains and related tables.
2. Preparing an accessibility data assessment and a proposed constrained routing model.
3. Finding and extracting official railway entrance coordinates and access categories
   from Lands Department iGeoCom, to supplement missing coordinates in the MTR CSV.
4. Inspecting the pedestrian geometry: paths are 3D polylines whose vertices contain
   X, Y, and height, rather than a supplied standalone node/point network.
5. Producing an overview map and a precise map of all pedestrian paths over district
   outlines and a land/coastline background, in SVG and PNG.
6. Producing a precise map distinguishing slopes and connector types, followed by
   separate feature maps to reduce crowding.
7. Visualising the supplied 5 m terrain raster as shaded elevation with district outlines.
8. Adding numbered estate and hospital locations to the precise path map, with a name index.
9. Analysing stored path steepness in **Yuen Long (map number 18)** and **North (map number 7)**.
10. Reinterpreting those two districts for mobility needs using percent-grade bands,
    connector types, and the available wheelchair/access fields.
11. Organising unchanged copies of selected source data under `data/organized/`, with
    a copy manifest. See [the separate data guide](../data/README.md).

**There is no implemented accessibility routing engine or verified estate-to-transit
journey yet.** Maps and district statistics are not a proof of a continuous usable route.
The mathematical ranking model in the accessibility report is a proposal; its numerical
example is illustrative, not a computed estate result.

## 2. Start here, depending on your task

| Goal | Read or open |
|---|---|
| Understand inputs and the proposed routing system | [accessibility_report.md](accessibility_report.md) and [data/README.md](../data/README.md) |
| Inspect audited counts and field dictionaries | [audit_summary.json](audit_summary.json) |
| Read the publisher's pedestrian metadata | [metadata_extracted.txt](metadata_extracted.txt), or the source PDF |
| Find official MTR entrance coordinates | [mtr_coordinate_sources.md](mtr_coordinate_sources.md) and `../data/official_igeocom/` |
| See the whole pedestrian network | [maps/hong_kong_paths_precise.png](maps/hong_kong_paths_precise.png) or [the vector SVG](maps/hong_kong_paths_precise.svg) |
| See general coverage with broader strokes | [maps/hong_kong_paths_overview.png](maps/hong_kong_paths_overview.png) |
| Inspect one connector type at a time | [the individual feature maps](#8-individual-feature-maps) |
| See terrain | [terrain SVG](maps/hong_kong_dtm_districts.svg) or [PNG preview](maps/hong_kong_dtm_districts_preview.png) |
| Find estates and hospitals on the map | [numbered location SVG](maps/hong_kong_estates_hospitals_numbered.svg) and [index CSV](maps/hong_kong_estates_hospitals_index.csv) |
| Compare Yuen Long and North slopes | [district_gradient_summary.json](maps/district_gradient_summary.json) |
| Compare those districts for mobility screening | [district_mobility_summary.json](maps/district_mobility_summary.json) |
| Regenerate outputs | [environment and execution instructions](#13-python-environment-and-reproduction) |

For quick viewing, use PNGs first. Individual path SVGs are roughly 49–57 MB because
each includes the complete unsimplified vector network. Some SVG viewers take time
to parse them. The terrain SVG is smaller because elevation is embedded raster imagery.

## 3. File layout and source-of-truth rules

```text
project root/
  3D_Pedestrian_Network_FGDB.zip
  Whole_HK_DTM_5m.zip
  JSON_BUS.json
  prh-estates (1).json
  facility-hosp.json
  mtr_lines_and_stations.csv
  barrier_free_facilities.csv
  barrier_free_facility_category.csv
  portal.csdi.gov.hk_csdi-webpage_metadata_landsd_rcd_1637222018065_52265_html.pdf
  .venv/
  data/
    README.md
    official_igeocom/             Official downloads, extracts, dictionary, manifest
    organized/                   Unchanged selected copies; see copy_manifest.json
    2020 data github public set/  Older reference bundle
  analysis/
    README.md                    This handoff
    accessibility_report.md      Data assessment and proposed routing model
    mtr_coordinate_sources.md    Official entrance-source investigation
    audit_data.py
    audit_summary.json
    metadata_extracted.txt
    requirements.txt             Audit dependencies only
    extract_mtr_access.py
    maps/
      README.md                  Original map notes
      FEATURE_MAP_README.md
      TERRAIN_AND_SERIES_README.md
      DISTRICT_MOBILITY_README.md
      render_maps.py
      render_feature_map.py
      render_terrain_and_series.py
      render_estates_hospitals.py
      analyse_district_gradients.py
      analyse_district_mobility.py
      district_boundaries.json
      hong_kong_land.geojson
      [SVGs, PNGs, JSON summaries, and district CSVs described below]
      feature_series/
        hong_kong_paths_precise_<category>.svg
        hong_kong_paths_precise_<category>_preview.png
        render_summary.json
```

The **original root files remain unchanged**. The organised collection consists of
copies, not moved files. The scripts in this folder generally still reference the
original root files, not the organised copies. Do not remove or rename root inputs
and expect these scripts to keep working without updating their path configuration.

`data/organized/copy_manifest.json` records the original path, copied path, size, and
SHA-256 for 20 copied artifacts. A renamed `.geojson` file in the organised collection
can be an unchanged copy of a root `.json` file, not a conversion.

Generated maps and summaries can be reproduced. Source snapshots, dictionaries,
manifests, and reviewed interpretation notes should be retained. Do not regard a new
download as interchangeable with the snapshot used for these counts.

## 4. Input inventory and joins

| Original input | Observed contents | Correct use / limitation |
|---|---|---|
| `3D_Pedestrian_Network_FGDB.zip` | `3DPN_P2.gdb`, containing 465,892 route features and seven nonspatial tables | Main path geometry and access attributes; graph topology still needs construction |
| `Whole_HK_DTM_5m.zip` | One ASCII raster, `Whole_HK_DTM_5m.asc`, about 302 MB uncompressed | Terrain context; not a survey of kerbs, cross-slopes, or short ramps |
| `prh-estates (1).json` | 244 unique estates, all with map coordinates; 199 have barrier-free document links | Estate lookup and approximate map origins; map pins are not verified accessible entrances |
| `facility-hosp.json` | 44 hospital records, with coordinates and A&E indicators | Destination context; neither the point nor A&E status identifies an accessible entrance |
| `JSON_BUS.json` | GeoJSON points: 56,209 route-stop records; 4,488 distinct stop IDs; 4,487 distinct coordinate pairs | Separate physical-stop records from route memberships and service directions |
| `mtr_lines_and_stations.csv` | 273 rows, including three entirely blank rows; 100 nonblank station IDs | Station identity and line/direction membership; not entrance geometry |
| `barrier_free_facilities.csv` | 3,564 station-facility records for 99 station numbers | Station facilities and free-text entrance arrangements; all original exit-coordinate cells are empty |
| `barrier_free_facility_category.csv` | 36 facility definitions | Join facility `Key` to dictionary `Item_Code` |
| Metadata PDF | Pedestrian dataset coverage, reference system, update and accuracy information | Local metadata stamp is 2026-09-16; stated accuracy is approximately 1 m XY and 2 m Z |

Important join rules:

- `Station_No` in the facilities CSV can be provisionally matched to `Station ID`
  in the station CSV, consistently represented as strings. It needs reconciliation:
  facility IDs `70` and `888` are unmatched, while station IDs `44`, `45`, and `46`
  have no exact facility-ID match. These may reflect station complexes or alternate IDs.
- No duplicate `(Station_No, Key)` pairs were found in the facility table.
- The official iGeoCom IDs, MTR station IDs, and pedestrian terminal IDs are distinct
  identifier systems. Do not join them merely because their values are numeric.
- Bus records repeat stops for route/direction/service memberships. Preserve those
  memberships. Do not call the 56,209 records 56,209 bus stops.
- `stopPickDrop` codes 0–3 were observed but not authoritatively decoded in the audit.
  Verify them before deciding whether boarding is allowed.
- Nearest bus-stop examples in `audit_summary.json` use haversine distance from estate
  map pins. They measure proximity only, not path distance or wheelchair access.

### 4.1 Official MTR entrance supplement

The original MTR facilities CSV has **zero populated `Exit_Coordinate_X_Y` cells**.
The separately downloaded official iGeoCom dataset supplies location information;
it has not automatically populated or repaired that CSV.

Artifacts are in `data/official_igeocom/`, and unchanged selected copies are in
`data/organized/core/mtr/official_igeocom/`:

| File | Contents |
|---|---|
| `source_geojson.zip`, `source_csv.zip` | Original official community-point downloads |
| `data_dictionary_v5.pdf` | Publisher field, category and coordinate dictionary |
| `mtr_access_points.geojson` | 611 `TYPE=MTA` railway access-point features, original properties preserved |
| `mtr_access_points.csv` | Same 611 source access rows, with WGS84 longitude/latitude added by matched `GEONAMEID` |
| `railway_stations.geojson` | 98 `TYPE=RSN` railway-station point features |
| `source_manifest.json` | Source URLs, retrieval timestamp, source hashes, counts, coordinate conventions and limits |

The full source contains 37,379 community points. Access subcategory counts are:
119 `MTRLIF` (lift), 56 `MTRRAM` (ramp), 61 `MTRSLV` (same level), 11 `MTRSTL`
(stair lift), 2 `MTRWCA` (wheelchair aid), and 362 blank/unspecified.
Blank means unknown/unspecified, **not inaccessible**. Counts are records, not a
verified inventory of unique physical exits or station complexes.

Access records have 98 distinct nonblank English site names. One Diamond Hill Exit D
record lacks its site-name attribute. Station/exit names need reviewed reconciliation
with MTR CSVs; retain original names and categories rather than replacing them with
unreviewed inferred matches.

GeoJSON point coordinates are WGS84 `[longitude, latitude]`; `EASTING`/`NORTHING`
attributes use Hong Kong 1980 Grid. Record revision dates vary; some access records
have 2021 dates despite the archive being downloaded in October 2026.

The investigation found that a CEDD exit-layer bulk query failed, and a direct CSDI
FeatureServer request required a token. Public official archives were used instead.
No OSM entrance extract was downloaded for the entrance investigation. See
[mtr_coordinate_sources.md](mtr_coordinate_sources.md) for those findings and sources.

### 4.2 Older reference bundle

`data/2020 data github public set/` contains older station/line/fare and map files.
The organised collection retains the appended station-coordinate CSV for comparison.
It has 94 distinct station codes and lacks Exhibition Centre, Sung Wong Toi, and
To Kwa Wan relative to the main station file. Its coordinates are station-level,
not entrance-level. Appended Central–Hong Kong walking rows do not establish a
verified accessible connection. Prefer the official entrance supplement for targets.

## 5. Pedestrian-network geometry and schema

### 5.1 How the paths are represented

The spatial layer `PedestrianRoute` is declared **`MultiLineString Z`**. In this local
snapshot, every feature has a single constituent polyline, despite the layer allowing
multipart geometry. Each vertex contains `(X, Y, Z)`.

- 465,892 path features.
- 294,080 features have two vertices: one straight segment.
- 171,812 have more than two vertices: several segments describe bends or height changes.
- The maximum observed feature has 1,666 vertices.
- The precise maps retain **1,963,912 vertices** in total.
- No separate point/node layer is exposed in this geodatabase.

A polyline's vertices are embedded geometry; they are not necessarily routing
junctions. A future graph can use edges and compatible endpoints, but it must verify
actual connections. Crossing XY lines may be a footbridge over a road or paths on
different floors. Never connect them simply because the top-down projections intersect.

All rendered pedestrian maps are top-down views: **Z is flattened**. A lift can be
vertical or nearly vertical and therefore disappear as a line. Feature maps add
visible point markers at exact XY polyline midpoints to make those connectors visible.
These markers are enlarged for display and do not indicate the physical footprint.

### 5.2 Coordinate conventions

Horizontal coordinates are **Hong Kong 1980 Grid, EPSG:2326**, in metres. The stored
compound CRS includes HKPD height vertically. Heights are relative to the Hong Kong
Principal Datum, not a generic altitude reference inferred from WGS84 latitude/longitude.

For geographic source points and district polygons, the map scripts use:

```python
from pyproj import Transformer
project = Transformer.from_crs("EPSG:4326", "EPSG:2326", always_xy=True)
easting, northing = project.transform(longitude, latitude)
```

`always_xy=True` explicitly uses longitude first. Do not feed latitude first, calculate
metre distances in degrees, or treat grid coordinates as longitude/latitude.
Preserve height, floors and related IDs separately when constructing topology.

Many decimal digits in geometry do not imply survey accuracy. The local metadata
states approximately 1 m XY and 2 m Z accuracy. Near-vertical gradients on centimetre-long
XY segments can be dominated by geometry/source effects; those records need review.

### 5.3 Layers and relationship tables

| Layer/table | Records | Geometry / purpose |
|---|---:|---|
| `PedestrianRoute` | 465,892 | 3D polylines and route fields |
| `PedRouteRelTerminalPoly` | 669 | Nonspatial terminal ID/name/type table |
| `PedRouteRelFloorPoly` | 2,596 | Nonspatial floor/building associations |
| `PedRouteRelBldgPoly` | 9,084 | Nonspatial building IDs and names |
| `PedRouteRelSitePoly` | 3,363 | Nonspatial site IDs and names |
| `PedRouteRelDistancePost` | 3,431 | Route-to-distance-post associations |
| `AccessTime` | 2,413 | Schedule IDs, OPEN/CLOSE interpretation and descriptions |
| `AccessTimeDetails` | 3,483 | Schedule IDs, day codes, FromTime and ToTime |

Names ending in `Poly` do **not** mean the archive supplies polygon geometry for
those tables. They cannot directly supply terminal boundaries or entrance footprints.

Route relationship fields include `FloorID`, `BuildingID_1`, `BuildingID_2`, `SiteID`,
`TerminalID`, and `AccessTimeID`. Match them to their documented related-table keys.
Routes have 46,276 non-null access-time references and 10,485 non-null terminal references.

Access schedules require both tables. `AccessTimeType=OPEN` and `CLOSE` have opposite
meanings. Times are encoded as HHMM, not elapsed minutes. A future router must handle
day groups, holidays, overnight intervals, and the arrival time at the passage.
Neither a missing schedule nor `Enabled=True` establishes live, unrestricted availability.

### 5.4 Important fields and coded values

The complete recovered dictionaries are in `audit_summary.json` under `gdb_domains`.
They were extracted from embedded XML in `.gdbtable` files, rather than invented from
the numeric values. That binary/XML extraction is useful for this snapshot but not
guaranteed to work on every future geodatabase release.

| Field | Meaning / handling |
|---|---|
| `PedestrianRouteID` | Stable source route identifier for these outputs; distinct from GDAL FID / OBJECTID |
| `FeatureType` | Explicit walkway or connector class; use this even if another access flag disagrees |
| `Gradient` | Stored segment steepness angle, interpreted in radians; see conversion and caveats below |
| `Location` | 1 Outdoor, 2 Indoor, 3 Paid in the domain; only 1 and 2 occur here |
| `WeatherProof` | 1 Covered, 2 NonCovered, 3 Unclassified |
| `WheelchairAccess` | 1 True, 2 False; describes accessible entrance connections, not general walkway usability |
| `WheelchairBarrier` | 1 True, 2 False; field name and embedded description are ambiguous together—see below |
| `ObstaclesType` | Named potential obstruction, or missing; does not measure available clear width |
| `Enabled` | 1 True, 2 False; 26 routes are disabled in the territory-wide snapshot |
| `Direction` | 1 forward, -1 backward, 0 both; domain describes moving connectors, not a universal traffic rule |
| `PositionCertainty` | 0 Uncertain, 1 Certain; particularly relevant to country-park/rural geometry |
| `AliasNameEN/TC`, `StreetNameEN/TC` | Names and context; optional and not reliable unique join keys |
| `DataSource`, `LevelSource` | Provenance of horizontal/path and level information; retain for evidence review |
| `Shape_Length` | Publisher length attribute; do not assume its exact 2D/3D meaning without checking |

FeatureType domain:

| Code | Meaning | Code | Meaning |
|---:|---|---:|---|
| 1 | Footway | 15 | M_Footway |
| 2 | Footbridge | 16 | M_Escalator |
| 4 | Subway | 17 | M_Travelator |
| 5 | Service Lane | 18 | M_Lift |
| 6 | Traffic Island | 19 | M_Ramp |
| 7 | RunIn | 20 | M_Staircase |
| 8 | Escalator | 21 | M_Stairlift |
| 9 | Travelator | 22 | M_Others |
| 10 | Lift | 23 | Generalized Walkway inside Park |
| 11 | Ramp | 24 | Footpath |
| 12 | Staircase | 25 | Village |
| 13 | Stairlift | 26 | Track |
| 14 | Other | 30 | Crossing — Signalized |
| 31 | Crossing — Zebra | 32 | Crossing — Cautionary |
| 33 | Crossing — Others | | |

The renderers group regular and corresponding `M_` classes. No meaning beyond the
source dictionary's names is inferred for the `M_` prefix. The audited snapshot's
observed connector counts are 22,012 staircases, 1,773 escalators, 1,911 lifts,
3,146 ramps, 44 travelators and 5 stairlifts.

Obstacle codes: 1 Accessible; 2 BridgePier; 3 BusStop; 4 FireHydrant; 5 LightPole;
6 RoadSign; 7 TrafficLight; 8 TrafficSign; 9 SignPole; 10 Bollard; 11 Tree;
12 ElectricBox; 13 ParkingMeter. A nearby tree/pole is not automatically an impassable
barrier; the data does not say how much clear space remains.

### 5.5 Wheelchair flags: do not misinterpret them

`WheelchairAccess=True` explicitly refers to an accessible entrance connection to
a public facility, building, or site. Only 4,177 routes have that value. **Requiring
True on every edge would incorrectly discard ordinary paths.** False is not evidence
that an ordinary path is inaccessible.

`WheelchairBarrier` has a name suggesting a barrier indicator, but its domain description
says it indicates whether a segment is suitable for mobility-aided users. The dictionary
assigns 1=True and 2=False without resolving that wording conflict. Observed associations
support reading True as barrier present: 21,645 stairs and 1,742 escalators carry True,
while all 1,911 lifts carry False. However, **367 staircase records carry False**.

Earlier assessment notes describe the likely barrier interpretation; the later mobility
analysis intentionally preserves raw True counts rather than claiming verified semantics.
For production filtering, obtain an authoritative clarification and still exclude stairs
explicitly for a step-free profile. Never use False alone to certify an accessible edge.

## 6. Gradients: units, conversions, and what was actually measured

The analyses use the source `Gradient` value per route; they do **not** calculate path
steepness from the DTM. Raw values range from 0 to approximately 1.57065, consistent
with angles in radians approaching 90 degrees.

The radians interpretation was also checked against actual two-vertex 3D geometry:
among 742 two-vertex features in a 1,000-feature sample, 687 matched
`atan2(abs(dz), horizontal_distance)` within 0.0001 radians; median absolute error
was approximately 2.66e-9 radians. This is corroboration, not a claim that every stored
gradient can be recreated from endpoint geometry. Source geometry/gradient discrepancies
exist, and one whole-route value need not describe every local change within a polyline.

```python
angle_radians = abs(gradient)
angle_degrees = angle_radians * 180 / pi
grade_percent = 100 * tan(angle_radians)
```

| Quantity | Approximate equivalent | Use here |
|---|---|---|
| 5% grade | 2.8624°; 1:20 rise/run | Lower mobility-screening band |
| 8.3333% grade | 4.7636°; 1:12 | Upper reference mobility-screening band |
| 5° angle | 8.7489% grade | Slope-map highlighting cutoff |
| 10° angle | 17.6327% grade | District angle-distribution comparison |

**5% and 5° are different.** The teal slope maps use 5°. The mobility statistics use
5% and 8.33% grade. Do not compare those percentages as if they used the same threshold.

Analyses take absolute gradient. They quantify magnitude, not whether a particular
journey is uphill or downhill. Geometry orientation and travel direction need further
work before directional ascent/descent costs can be applied.

Do not interpret a lift's near-vertical gradient as a ramp that is too steep. Equipment
edges need a separate model. Likewise, a district median does not identify a continuous
route or the hardest section along a journey.

## 7. Whole-network and combined feature maps

All map scripts use the same official district polygons and OSM-derived land geometry,
projected into the route grid. District bounds are padded by 1,600 m for map framing.
District polygons include marine areas; a separate coastline makes land and harbour visible.

### 7.1 Overview versus precise

| Output pair | Geometry / styling | PNG size |
|---|---|---|
| `maps/hong_kong_paths_overview.svg` and `.png` | All 465,892 routes; Douglas–Peucker simplification with 35 m tolerance; broader strokes; 937,867 displayed vertices | 3520 × 2640 |
| `maps/hong_kong_paths_precise.svg` and `.png` | All 465,892 routes and 1,963,912 original XY vertices; no simplification; finer strokes | 6400 × 4800 |

Generator: [maps/render_maps.py](maps/render_maps.py).
Counts and sizes: [maps/render_summary.json](maps/render_summary.json).

“Precise” means original coordinate geometry is retained and aligned in the correct
grid. It does not improve the source's positional accuracy, account for current
construction changes, or reveal levels that overlap in the top-down view.

The SVG network group is named **`pedestrian-path-overlay`**. It contains vector path
geometry, not an embedded screenshot. The map title, legend and labels are SVG text.
The map SVG is a presentation artifact, not a GIS exchange format: page coordinates
are SVG units, not the source grid. Use FGDB/GeoJSON for spatial analysis.

### 7.2 Combined feature map

Outputs:

- [maps/hong_kong_paths_precise_features.svg](maps/hong_kong_paths_precise_features.svg)
- [maps/hong_kong_paths_precise_features_preview.png](maps/hong_kong_paths_precise_features_preview.png)
- [maps/feature_render_summary.json](maps/feature_render_summary.json)

Generator: [maps/render_feature_map.py](maps/render_feature_map.py).
Additional notes: [maps/FEATURE_MAP_README.md](maps/FEATURE_MAP_README.md).

Explicit connectors take priority over the slope classification. Non-connector routes
with `abs(Gradient) >= radians(5)` are teal slopes. The mutually exclusive category
counts are:

| Category | Routes | Display |
|---|---:|---|
| Other paths / lower gradients | 382,098 | Grey |
| Other slopes ≥5° | 54,903 | Teal |
| Ramps | 3,146 | Gold |
| Stairs | 22,012 | Red |
| Escalators | 1,773 | Orange |
| Travelators | 44 | Blue |
| Stairlifts | 5 | Pink |
| Elevators / lifts | 1,911 | Purple |

Every route is assigned exactly one category; the script asserts coverage and vertex
totals. Lift circles and stairlift diamonds mark exact XY midpoints without jitter.
Because showing all connector classes together is crowded, separate maps were created.

## 8. Individual feature maps

Generator: [maps/render_terrain_and_series.py](maps/render_terrain_and_series.py),
with the optional `series` argument. Additional notes:
[maps/TERRAIN_AND_SERIES_README.md](maps/TERRAIN_AND_SERIES_README.md).

Every SVG contains the complete precise network, styled in muted grey, plus **one**
highlighted category. All 465,892 background routes and 1,963,912 vertices remain.
The SVG background path data was compared with the original precise SVG and matched
exactly; only the background's style is subdued.

| Category / highlighted records | SVG | Preview |
|---|---|---|
| Escalators — 1,773 | [SVG](maps/feature_series/hong_kong_paths_precise_escalators.svg) | [PNG](maps/feature_series/hong_kong_paths_precise_escalators_preview.png) |
| Elevators — 1,911 | [SVG](maps/feature_series/hong_kong_paths_precise_elevators.svg) | [PNG](maps/feature_series/hong_kong_paths_precise_elevators_preview.png) |
| Ramps — 3,146 | [SVG](maps/feature_series/hong_kong_paths_precise_ramps.svg) | [PNG](maps/feature_series/hong_kong_paths_precise_ramps_preview.png) |
| Travelators — 44 | [SVG](maps/feature_series/hong_kong_paths_precise_travelators.svg) | [PNG](maps/feature_series/hong_kong_paths_precise_travelators_preview.png) |
| Stairlifts — 5 | [SVG](maps/feature_series/hong_kong_paths_precise_stairlifts.svg) | [PNG](maps/feature_series/hong_kong_paths_precise_stairlifts_preview.png) |
| Other slopes ≥5° — 54,903 | [SVG](maps/feature_series/hong_kong_paths_precise_slopes.svg) | [PNG](maps/feature_series/hong_kong_paths_precise_slopes_preview.png) |

There is no dedicated staircase map, as requested. Staircases still exist in the full
grey background because it preserves the original complete precise network.

The slope map excludes explicit connector classes, including stairs and ramps. Thus
it is not a map of **all** geometries with gradient ≥5°. The combined/series slope
definition excludes codes `[8,9,10,11,12,13,16,17,18,19,20,21]`.

For non-slope categories, exact midpoint location markers help short connectors remain
visible at city scale. Slopes use lines without dots. Marker sizes and stroke widths
are enlarged for visibility; lines retain their original coordinates. Zoom to inspect
precise line shapes. Do not derive equipment dimensions from symbol size.

SVG groups:

- `pedestrian-path-overlay`: complete background.
- `pedestrian-<category>`: selected precise linework.
- `pedestrian-<category>-location-markers`: midpoint symbols, where supplied.

All these SVGs are vector-only. Each PNG preview is 2880 × 2160.
Counts are recorded in [maps/feature_series/render_summary.json](maps/feature_series/render_summary.json).

## 9. Terrain visualisation

Outputs:

- [maps/hong_kong_dtm_districts.svg](maps/hong_kong_dtm_districts.svg)
- [maps/hong_kong_dtm_districts_preview.png](maps/hong_kong_dtm_districts_preview.png)
- [maps/dtm_render_summary.json](maps/dtm_render_summary.json)

Generator: `maps/render_terrain_and_series.py`, with optional `terrain` argument.

### 9.1 Native ASCII raster

The ZIP entry is dated 2019-03-11. This is archive metadata, not proof of every cell's
survey date. The file has this header:

```text
ncols         12751
nrows         9601
xllcorner     799997.5
yllcorner     799997.5
cellsize      5
NODATA_value  -9999
```

There are 122,422,351 cells. Every row was parsed and checked for the declared column
count. Observed elevation values range from **-26 to 958 m**. No cell equalled the
declared NoData value in this snapshot. Many sea/background cells contain zero;
zero must not be universally treated as missing elevation.

ASCII rows run north to south; lower-left corner values locate **cell edges**, not
their centres. Cell centre coordinates are:

```python
x = xllcorner + (column + 0.5) * cellsize
y = yllcorner + (nrows - row - 0.5) * cellsize
```

Native extent is west 799997.5, east 863752.5, south 799997.5, north 848002.5.
The ASCII header embeds no CRS identifier. Hong Kong 1980 Grid is used consistently
with the Lands Department product and coordinate range; preserve that CRS information
externally if converting to another raster format. Confirm the vertical datum against
the product documentation before using terrain heights for an engineering comparison.

### 9.2 Display processing

To keep the SVG manageable, the script averages 4 × 4 native cells into **20 m display
cells**. This is a visualisation reduction, not a change to the source raster.
NoData, if present, is excluded from averages.

- Display grid: 2,400 rows × 3,187 columns.
- Display extent: west 799997.5, east 863737.5, south 800002.5, north 848002.5.
- The last native row and three native columns are trimmed to make complete blocks:
  5 m south and 15 m east, outside the relevant Hong Kong land area.
- Elevation colours span 0–1000 m. Negative elevations receive the lowest colour.
- Shaded relief uses northwest illumination at 45° altitude, no vertical exaggeration,
  and 20 m derivative spacing. Shade modulates colours; the legend describes elevation.
- OSM-derived coastline geometry clips the elevation image to land. District boundaries
  still include their administrative marine areas.

The terrain SVG is **hybrid**: the elevation image is embedded raster imagery, while
district outlines, coastline clip, labels, scale and other annotation remain vector.
It is standalone and needs no external linked PNG. It is not a vector contour map.
Its PNG preview is 2880 × 2160.

Lands Department describes the DTM as including some non-ground information such
as elevated roads and bridges. It should not be assumed to be a perfectly bare-earth
surface. A 5 m source grid cannot reliably determine small kerbs, cross-slopes or short
ramps; the 20 m visual display is even less suited to that purpose. Use the pedestrian
dataset's explicit feature types and checked route information for access analysis.

## 10. Numbered estate and hospital map

Outputs:

- [maps/hong_kong_estates_hospitals_numbered.svg](maps/hong_kong_estates_hospitals_numbered.svg)
- [maps/hong_kong_estates_hospitals_numbered_preview.png](maps/hong_kong_estates_hospitals_numbered_preview.png)
- [maps/hong_kong_estates_hospitals_index.csv](maps/hong_kong_estates_hospitals_index.csv)

Generator: [maps/render_estates_hospitals.py](maps/render_estates_hospitals.py).

This reads the existing precise SVG, retains its line geometry, mutes the path colour,
removes its district-number labels, and places numbered circles at the projected
original estate/hospital coordinates. Green estates and red hospitals have separate
alphabetical numbering: **244 estates and 44 hospitals**. The name legend is below
the map; the index CSV has `kind`, `number`, `name`, `latitude`, and `longitude`.
Numbers are display indices, not stable source IDs. They can change if names or records change.

Source field handling:

- Estates: `Estate Name.en`, `Estate Map Latitude`, `Estate Map Longitude`.
- Hospitals: `institution_eng`, `latitude`, `longitude`.
- Coordinates are transformed from WGS84 into the same grid/extent as the precise map.
- Finite coordinates and map bounds are asserted. Circles are centred on the actual
  source point without visual displacement; dense clusters can overlap.
- SVG point groups are `estate-<number>` and `hospital-<number>` inside
  `exact-location-points`, with `<title>` labels containing names and coordinates.

These are map points, **not verified accessible entrances**. The renderer depends on
the existing precise SVG structure; its label-removal logic uses Matplotlib-generated
text IDs and may need adjustment if the base layout changes.

The current script creates **SVG and index CSV only**. A PNG preview exists, but its
rasterisation is a separate step not implemented in that script. Do not claim running
the script alone refreshes the PNG. Use an SVG renderer to regenerate it, and verify
the full map and below-map legend are included.

## 11. Yuen Long and North: district steepness analysis

Generator: [maps/analyse_district_gradients.py](maps/analyse_district_gradients.py).
Outputs:

- [maps/district_gradient_summary.json](maps/district_gradient_summary.json)
- [maps/district_18_yuen_long_gradients.csv](maps/district_18_yuen_long_gradients.csv)
- [maps/district_7_north_gradients.csv](maps/district_7_north_gradients.csv)

### 11.1 District numbering

Map numbers are created by sorting the 18 English district names alphabetically after
removing the suffix ` District`. They are **map legend indices**, not official district
codes and not Hong Kong-wide standard numeric identifiers.

| Map number | District | Map number | District |
|---:|---|---:|---|
| 1 | Central and Western | 10 | Sham Shui Po |
| 2 | Eastern | 11 | Southern |
| 3 | Islands | 12 | Tai Po |
| 4 | Kowloon City | 13 | Tsuen Wan |
| 5 | Kwai Tsing | 14 | Tuen Mun |
| 6 | Kwun Tong | 15 | Wan Chai |
| 7 | North | 16 | Wong Tai Sin |
| 8 | Sai Kung | 17 | Yau Tsim Mong |
| 9 | Sha Tin | 18 | Yuen Long |

The district-analysis script selects English district names, then records map numbers
7 and 18 explicitly. If the map sorting or names change, update those recorded numbers.

### 11.2 Membership, clipping, and denominator

The script projects official district polygons into EPSG:2326, applies `make_valid`,
builds a Shapely STRtree over the source route geometries, and selects features with
the `intersects` predicate.

A route crossing a boundary can appear in both districts. Count summaries include
each matching route record once per district; length summaries use only its **clipped
horizontal XY length inside that district**. Counts across districts are therefore
not necessarily additive to territory-wide route counts. Boundary-touching records
are in the all-intersecting set, but the walking subset requires positive clipped length.

The walking subset includes ramps and other paths, but excludes:
`[8,9,10,12,13,16,17,18,20,21]` — escalators, travelators, lifts, stairs and stairlifts.
It does **not** additionally filter every barrier, obstacle, entrance flag or equipment
condition, and it is not a verified wheelchair-route subset. `Enabled` is loaded but
not used as a walking-subset filter. The later mobility analysis reports disabled counts;
both districts have zero disabled records in this snapshot.

The same stored per-route gradient is used even for the clipped part. Local steepness
within that part is not recalculated. Quantiles ignore nonfinite gradients; all walking
gradients in these two districts are finite.

### 11.3 Results

| Metric | Yuen Long (18) | North (7) |
|---|---:|---:|
| All intersecting route records | 54,996 | 30,505 |
| Walking-subset route records | 54,140 | 29,719 |
| Walking-subset clipped XY length | 1,390.87 km | 803.85 km |
| Per-record median angle | 0.5158° | 0.6389° |
| Per-record 90th percentile | 3.7321° | 4.3153° |
| Per-record 95th percentile | 6.1763° | 7.0013° |
| Per-record 99th percentile | 17.7082° | 18.6312° |
| Records with angle ≥5° | 6.7418% | 8.3179% |
| Records with angle ≥10° | 2.5231% | 2.8366% |
| XY length with angle ≥5° | 4.1098% | 7.3023% |
| XY length with angle ≥10° | 1.1420% | 1.4939% |
| Maximum recorded walking-subset angle | 88.3810° | 81.5318° |

These show generally gentle recorded paths, with a steeper tail in North. They do
not mean every neighbourhood or journey is flat.

The maxima are not sensible descriptions of district walkability. For example, the
88.381° Yuen Long record is a Tin Yiu Estate footway with only about 0.039 m of in-district
XY length; the 81.532° North record has about 0.110 m of XY length. These tiny horizontal
lengths and source accuracy justify reviewing such records instead of trusting a raw maximum.

JSON fields distinguish per-record and length-weighted quantiles. Per-record quantiles
use NumPy's default interpolated quantile. Length-weighted quantiles sort angles and
take the first angle at which cumulative clipped length reaches the requested fraction.
The definitions differ, so exact values need not coincide.

Histogram bins are `[0,2,5,10,15,30,90.001]` degrees; NumPy uses half-open bins except
the last. The summary also stores the 20 steepest walking records, names and clipped lengths.

CSV fields:

| Column | Meaning |
|---|---|
| `PedestrianRouteID` | Source route ID, for joining back to the FGDB |
| `FeatureType` | Source coded feature class |
| `Gradient_radians` | Absolute stored gradient |
| `Slope_degrees` | Converted angle |
| `Grade_percent` | `100*tan(angle)`; can be extremely large near 90° |
| `Within_district_XY_length_m` | Horizontal length after clipping to this district |
| `Included_in_walking_summary` | Text `True` / `False` for the subset described above |
| `AliasNameEN`, `StreetNameEN` | Context names; can be empty or missing |

## 12. Mobility and wheelchair screening

Generator: [maps/analyse_district_mobility.py](maps/analyse_district_mobility.py).
Output: [maps/district_mobility_summary.json](maps/district_mobility_summary.json).
Detailed notes: [maps/DISTRICT_MOBILITY_README.md](maps/DISTRICT_MOBILITY_README.md).

The script uses the two district CSVs for membership and clipped lengths, joins source
attributes by `PedestrianRouteID`, and calculates grade bands. Therefore **run the
district gradient analysis first**, and regenerate both if the source FGDB changes.

### 12.1 Grade-band results

The following percentages are of walking-subset **horizontal length**, including ramps
and excluding the connector classes defined above:

| Grade band | Yuen Long | North |
|---|---:|---:|
| ≤5% grade | 90.4847% | 85.3105% |
| >5% and ≤8.3333% grade | 4.9252% | 6.8388% |
| >8.3333% grade | 4.5902% | 7.8507% |

The equivalent per-record percentages are 86.4093 / 6.3077 / 7.2830 for Yuen Long,
and 84.0641 / 7.1133 / 8.8226 for North. Clearly identify which denominator you use.

These bands are informed by Hong Kong's Buildings Department barrier-free ramp manual,
not by a claim that all paths under 5% are independently usable. The manual normally
limits ramps to 1:12, with specified exceptions for minor rises and short lengths.
It also addresses width, landings, handrails and surfaces. A source ramp above 8.33%
is not automatically a legal violation: short-rise exceptions and source-data effects
must be considered. The manual is a building design reference, not an automatic
classification rule for every outdoor path or every person's mobility capabilities.

### 12.2 Equipment, entrances, and raw flags

| Records intersecting district | Yuen Long | North |
|---|---:|---:|
| Stairs | 720 | 692 |
| Escalators | 61 | 34 |
| Lifts | 74 | 59 |
| Ramps | 381 | 187 |
| Travelators | 0 | 0 |
| Stairlifts | 1 | 1 |
| `WheelchairAccess=True` entrance connections | 308 | 149 |
| Raw `WheelchairBarrier=True` | 1,224 | 1,243 |
| Raw barrier=True within walking subset | 594 | 518 |
| Named-obstacle records | 407 | 157 |
| Not-enabled records | 0 | 0 |

These are **route records**, not unique devices or facilities. Multiple lines can
describe one installation. More lifts or ramps does not necessarily mean better access:
the important question is where they connect and whether they serve the required journey.

Ramp grade counts in Yuen Long are 198 / 102 / 81 in the three bands; in North they
are 80 / 55 / 52. Raw obstacle counts require a finite `ObstaclesType` other than 1;
they do not measure obstruction severity. The barrier ambiguity is deliberately retained.

### 12.3 Practical interpretation

Yuen Long has a gentler recorded slope profile than North. **Overall wheelchair
accessibility has not been ranked or established.** A journey requires a continuous
usable connection from the actual origin to the actual destination/boarding point.

For a future mobility-aware route, assess:

- Unavoidable stairs and steps; escalators are not ordinary wheelchair links.
- Dropped kerbs and crossing approaches, clear widths, surfaces and cross-slopes.
- Running grade **and length** of sloping sections, rests and individual endurance.
- Lift compatibility, approach geometry, opening hours, management and current operation.
- Stairlift equipment type and wheelchair compatibility; some arrangements need assistance.
- Estate block-to-network and entrance-to-platform connectors, not just central pins.
- Bus boarding direction, kerb/ramp clearance and service/vehicle compatibility.

A single unusable link can invalidate an otherwise gentle route. No district median,
average flag or facility count should conceal that. A manual-wheelchair, powered-wheelchair,
walker or assisted user can require a different profile; obtain their requirements
rather than assume one universal mobility score.

## 13. Python environment and reproduction

### 13.1 Working directory and dependencies

Commands below are run from the **project root**, currently:
`/Users/pidge/projects/hacksdg_homecoming`.
Scripts generally resolve source paths relative to their own location, but the relative
arguments passed to `extract_mtr_access.py` depend on your working directory.

The existing `.venv` uses Python 3.9 on macOS. It is ignored by Git. The audit requirements
file contains only:

```text
numpy==2.0.2
pyogrio==0.11.1
pypdf==6.20.0
```

**Installing `analysis/requirements.txt` alone is insufficient for the map scripts.**
Additional packages used in the existing environment are:

```text
matplotlib==3.9.4
pyproj==3.6.1
shapely==2.0.7
pillow==11.3.0
```

Create an environment only if one is not already available; do not replace an existing
working environment needlessly:

```sh
python3 -m venv .venv
.venv/bin/pip install -r analysis/requirements.txt
.venv/bin/pip install matplotlib==3.9.4 pyproj==3.6.1 shapely==2.0.7 pillow==11.3.0
```

These are the versions used here, not a guarantee every platform/Python version has
matching wheels. The existing setup does not need GeoPandas, Fiona, rasterio, SciPy,
the `osgeo` Python module, or a standalone `ogrinfo` executable. Pyogrio's bundled
GDAL/OpenFileGDB support reads this geodatabase.

Map scripts set `MPLCONFIGDIR=/tmp/hk-pedestrian-matplotlib` unless already configured,
to keep Matplotlib's cache writable. Initial font-cache warnings occurred in the local
sandbox; rendering completed. If your system cannot write default font caches, configure
a writable cache rather than assuming the source data is broken.

### 13.2 Read the FGDB directly from the ZIP

Extraction is unnecessary for most map/analysis scripts:

```python
from pathlib import Path
import pyogrio
from pyogrio.raw import read
import shapely

archive = Path("3D_Pedestrian_Network_FGDB.zip").resolve()
dataset = f"/vsizip/{archive}/3DPN_P2.gdb"
print(pyogrio.list_layers(dataset))
print(pyogrio.read_info(dataset, layer="PedestrianRoute"))

meta, fids, wkb, arrays = read(
    dataset,
    layer="PedestrianRoute",
    columns=["PedestrianRouteID", "FeatureType", "Gradient"],
    max_features=1000,
)
attributes = dict(zip(meta["fields"], arrays))
geometries = shapely.from_wkb(wkb)
```

Use `read_geometry=False` for attribute-only reads. Pyogrio can represent nullable
integer fields as floating arrays with NaN; check missingness before converting to integers.
The code does not require a DataFrame and avoids GeoPandas dependencies.

### 13.3 Audit and official entrance extraction

```sh
.venv/bin/python analysis/audit_data.py
.venv/bin/python analysis/extract_mtr_access.py data/official_igeocom/source_geojson.zip data/official_igeocom/source_csv.zip
```

`audit_data.py` extracts the geodatabase into a temporary directory to inspect its
embedded domain XML, reads input attributes, writes `audit_summary.json`, and extracts
PDF text to `metadata_extracted.txt`. Temporary extraction is cleaned up on exit.

**Audit PDF selection caveat:** it currently uses the first `*.pdf` found in the project
root. With the supplied single metadata PDF this worked. If more root PDFs are added,
change the selection to the intended metadata path before rerunning; otherwise it can
extract text from an unrelated document. Some encrypted PDFs need additional crypto
support for pypdf; the supplied original metadata PDF was successfully read.

`extract_mtr_access.py` does not download archives. It expects exact ZIP entry names
`iGeoCOM_POI.geojson` and `iGeoCOM_POI.csv`, filters TYPE codes, and writes into
`data/official_igeocom/`. It checks matching access ID sets across CSV/GeoJSON, unique
access feature IDs, point geometry and plausible Hong Kong coordinates. If source
schemas or ZIP names change, review the script. On a failed assertion, partial output
may have been written; do not treat that run as successful.

Its manifest `retrieved_utc` is populated with the **extraction run time**, not an
independently recovered original download time. The existing manifest documents the
initial session. When regenerating from old archives, preserve original provenance
and distinguish a new extraction timestamp from actual data retrieval.

### 13.4 Map and district-analysis commands

Run prerequisites before dependent commands:

```sh
# Reads root FGDB and the two saved map-context files.
.venv/bin/python analysis/maps/render_maps.py

# Combined feature map; also reads root FGDB and map context.
.venv/bin/python analysis/maps/render_feature_map.py

# Terrain and six individual feature maps. Omit arguments for both parts.
.venv/bin/python analysis/maps/render_terrain_and_series.py terrain
.venv/bin/python analysis/maps/render_terrain_and_series.py series

# Requires the precise SVG created by render_maps.py.
.venv/bin/python analysis/maps/render_estates_hospitals.py

# Creates district CSVs that the next command requires.
.venv/bin/python analysis/maps/analyse_district_gradients.py
.venv/bin/python analysis/maps/analyse_district_mobility.py
```

The renderers use saved district/coastline files and **do not download them themselves**.
If those are missing, recover the exact snapshot from the organised copies or fetch
the source URLs below, recording new provenance and reviewing changes.

Reproduction overwrites generated artifacts with the same names:

| Script | Outputs overwritten |
|---|---|
| `audit_data.py` | `audit_summary.json`, `metadata_extracted.txt` |
| `extract_mtr_access.py` | Official entrance/station extracts and source manifest in `data/official_igeocom/` |
| `render_maps.py` | Both whole-network SVG/PNG pairs, `render_summary.json`, `maps/README.md` |
| `render_feature_map.py` | Combined feature SVG/PNG, `feature_render_summary.json`, `FEATURE_MAP_README.md` |
| `render_terrain_and_series.py terrain` | Terrain SVG/preview and `dtm_render_summary.json` |
| `render_terrain_and_series.py series` | Six feature SVG/preview pairs and `feature_series/render_summary.json` |
| `render_estates_hospitals.py` | Numbered SVG and index CSV; **not** its PNG preview |
| `analyse_district_gradients.py` | Two district CSVs and `district_gradient_summary.json` |
| `analyse_district_mobility.py` | `district_mobility_summary.json` |

This top-level handoff and the standalone terrain/mobility notes are not generated by
those render scripts. If you edit generated map READMEs, update their generating code
or the next run can discard your edits. Regeneration does not automatically refresh
the organised copies or their manifest.

Allow time and memory for parsing millions of vertices and writing large SVG path
attributes. The terrain renderer streams ASCII rows and accumulates a reduced grid
rather than loading the full native elevation grid into Python objects. Every individual
feature SVG still contains a full background; that repetition is intentional.

## 14. Sources, dates and attribution

| Source | Purpose / provenance |
|---|---|
| [Official pedestrian dataset](https://data.gov.hk/en-data/dataset/hk-landsd-openmap-3d-pedestrian-network) | Root source ZIP and publisher context; local metadata revised 2026-09-16 |
| [Pedestrian metadata](https://portal.csdi.gov.hk/csdi-webpage/metadata/landsd_rcd_1637222018065_52265/html) | Source of the supplied saved metadata PDF/text |
| [Official district catalogue](https://data.gov.hk/en-data/dataset/hk-had-json1-hong-kong-administrative-boundaries) | Home Affairs Department district polygons |
| [District JSON download](https://www.had.gov.hk/psi/hong-kong-administrative-boundaries/hksar_18_district_boundary.json) | Saved as `maps/district_boundaries.json` during 2026-10-12 work |
| [OSM-derived land geometry](https://github.com/bmkor/hk_osm_map/blob/master/Hong_Kong.geojson) | Saved as `maps/hong_kong_land.geojson`; historical coastline context |
| [OpenStreetMap attribution](https://www.openstreetmap.org/copyright) | Retain credit to OpenStreetMap contributors for the coastline layer |
| [Official DTM catalogue](https://data.gov.hk/en-data/dataset/hk-landsd-openmap-5m-grid-dtm) | Terrain product description; source was the user's local ZIP |
| [Official DTM download](https://www.landsd.gov.hk/landsd_psi_data/SMO/data/Whole_HK_DTM_5m.zip) | Product URL; map work used the local snapshot, not a replacement download |
| [Official iGeoCom catalogue](https://data.gov.hk/en-data/dataset/hk-landsd-openmap-development-hkms-digital-geocom) | Railway access-point supplement; archive URLs/hashes in its manifest |
| [Lands Department iGeoCom description](https://www.landsd.gov.hk/en/survey-mapping/mapping/other-products/iGeoCom.html) | Publisher context for entrance dataset |
| [Buildings Department barrier-free manual](https://www.bd.gov.hk/doc/en/resources/codes-and-references/code-and-design-manuals/BFA2008_e.pdf) | 2008 manual, 2025 edition; printed pages 27–31 provide ramp guidance |

The coastline and pedestrian/terrain data have different vintages. Reclamation and
new construction can produce mismatches; do not warp path coordinates to fit an older
coastline. The coastline affects the map background and terrain clip, not path positions.

The barrier-free manual was downloaded for inspection to
`/tmp/hk_barrier_free_access_2025.pdf`, and extracted with `pdftotext` to a temporary
text file. Those temporary files are **not permanent project artifacts** and may no
longer exist. The URL above is the reference. pypdf could not read that AES-encrypted
manual in the existing environment because its optional cryptographic dependency was
absent; local `pdftotext` succeeded. This did not affect the original metadata audit.

Do not infer a publisher/licence for estate, bus or hospital files beyond documented
provenance. Consult their original sources before redistributing. Preserve government
source attribution and OSM attribution in derivative maps.

## 15. Checks completed and what they do not establish

Checks performed during this work include:

- Enumerating all geodatabase layers and inspecting schemas and feature counts.
- Reading the complete route geometry to count constituent parts and vertices.
- Recovering field domains and comparing wheelchair flags with explicit feature types.
- Checking the radians conversion against a sample of simple 3D route geometries.
- Verifying PNG files open and their expected dimensions for the main path maps.
- Parsing generated SVGs, confirming named overlay groups, and checking that pedestrian
  feature SVGs contain no embedded raster image.
- Checking the combined feature masks cover every route exactly once and preserve the
  original total vertex count; assertions remain in its renderer.
- Comparing each series SVG's background path data hash with the original precise
  map: identical geometry, despite changed colour/opacity.
- Checking finite exact midpoint markers and selected-record cardinality in the series.
- Visually inspecting terrain, combined paths/features, and representative separate maps.
- Parsing the full terrain ASCII with a column-count assertion for each row; recording
  source bounds, range and NoData count; checking the terrain SVG embeds its image.
- Checking projected estate/hospital coordinates are finite and within map bounds.
- Checking mobility grade-band route counts sum to the walking denominator, length
  percentages sum to 100%, and ramp-band counts sum to ramp records.
- Checking official entrance CSV/GeoJSON ID consistency, uniqueness, geometry and bounds.
- Checking copied selected source files against their original SHA-256 values, as
  recorded in the organised-data manifest.

Some checks were run as one-off inspection commands and are described here for
reproducibility; not every check exists as a standalone committed test script.
These are data/render consistency checks, **not field validation**. No graph connectivity,
live lift status, legal compliance, or end-to-end wheelchair journey was verified.

## 16. Future implementation: build on the data without overstating it

For a useful routing prototype, the next substantive work is:

1. Preserve/reconcile source identities, feature types, levels, schedules, and provenance.
2. Construct a level-aware directed multigraph from the 3D paths; distinguish actual
   junctions from overlaps and parallel alternatives such as stairs beside a lift.
3. Add reviewed estate block/entrance origins and official transit entrance targets.
   A straight line from a map pin to the nearest path can cross a wall or wrong level.
4. Verify entrance-to-concourse-to-platform links and boarding conditions, not just
   reaching the station/stop point.
5. Apply hard constraints for the selected person's equipment, assistance requirements,
   permissible connectors, slope/length limits, and access time before ranking preferences.
6. Keep unknown evidence distinct from verified usability and confirmed barriers.
   Do not average away a decisive unusable link.
7. Rank remaining journeys by meaningful distance/effort/crossing/equipment costs,
   with calibrated user preferences. Proposed formulas are in the accessibility report.
8. Validate a small pilot with intended users before expanding coverage. Inspect source
   gradient anomalies and flag disagreements as regression cases.

No graph library is currently required by the completed analyses. NetworkX or another
backend would be a future implementation choice; evaluate memory and runtime at this
scale before adopting a city-wide Python-object graph.

The older accessibility report contains statements about packages and unresolved units
from the initial audit stage. This handoff records the later installed map packages,
gradient interpretation and district work. Also, its original “missing MTR coordinates”
finding applies to the original CSV; the official supplement now exists, while matching
and platform access remain unresolved.

### Agent handoff checklist

Before continuing work, read this file and the specific script you intend to run.
Check whether inputs, code lists, district labels and snapshots still match the
recorded counts. Treat generated SVGs as presentation, source data as analysis inputs,
and proposed routing mathematics as unimplemented until an actual engine exists.
Preserve root originals and provenance. Regenerate dependent outputs together after
source changes. Update this handoff with new results, methods, dependencies, limitations
and verification so the next reader does not need the conversation history.


Data paths were consolidated on 13 October 2026. Former root filenames above describe the original inputs; current paths and SHA-256 checks are recorded in [the reorganization manifest](../data/reorganization_manifest.json). Analysis scripts use the current organized paths.
