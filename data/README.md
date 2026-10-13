# Data guide for estate-to-transit accessibility

Organized on 12 October 2026. Useful files have been **copied**, not moved, into [`organized/`](organized/). Original files remain in their original locations. Copied contents are unchanged; a few filenames were clarified. [`copy_manifest.json`](organized/copy_manifest.json) records all 20 originals, copies, sizes and SHA-256 hashes. Copies were checked against their originals.

## Folder structure

```text
organized/
  core/
    estates/             Estate origins
    bus/                 Bus stop locations and route memberships
    mtr/                 Station identities, facilities and official access points
      official_igeocom/  Entrance coordinates, station points and source documents
    pedestrian/          Routing network and its metadata
  supplementary/
    terrain/             Broader terrain analysis
    hospitals/           Optional future destinations
    map_context/         District boundaries and land outline for maps
  reference/
    legacy_2020/         Older station coordinates for comparison
  copy_manifest.json
```

## Core data: use these for the first routing prototype

| File | Why it is useful | Important limits and handling |
|---|---|---|
| [Estate records](organized/core/estates/prh-estates.json) | Contains 244 estates with names, districts, map coordinates and block information. Provides estate lookup and approximate starting locations; 199 entries link to barrier-free documents that could help identify entrances. | Estate pins are representative map points, not verified block entrances. Validate the path from the resident's actual starting point. Linked document contents are not included in this file. |
| [Bus route-stop records](organized/core/bus/route_stop_records.geojson) | Contains bus stop coordinates, stop IDs/names, route memberships, direction/sequence and boarding codes. Enables nearby-stop searches and checking whether a stop serves the required route. | 56,209 records represent 4,488 distinct stop IDs, not 56,209 stops. Separate stops from memberships. This is a renamed copy of `JSON_BUS.json`, not a conversion. No explicit boarding clearance or wheelchair-compatible vehicle fields. |
| [MTR lines and stations](organized/core/mtr/mtr_lines_and_stations.csv) | Provides station codes/IDs, multilingual names, lines and station order. Supplies the station identity table for connecting facilities and entrances. | Remove three blank rows. Preserve repeated line/direction memberships. `Sequence` is order within a line and direction, not distance or accessibility. IDs require reconciliation between datasets. |
| [MTR barrier-free facilities](organized/core/mtr/barrier_free_facilities.csv) | Gives 3,564 station-facility records, including yes/no indicators and descriptions naming exits or access arrangements. Useful for checking lifts, ramps, wide gates and other required facilities. | All exit-coordinate cells are empty. Supplement with iGeoCom; do not invent coordinates. A station-level facility does not guarantee every exit or platform is accessible. |
| [Facility category dictionary](organized/core/mtr/barrier_free_facility_category.csv) | Defines all 36 facility keys used above. Converts keys such as `AJ3` into readable meanings, allowing profile-specific filtering. | Join `Key` to `Item_Code`. Different facilities serve different needs; do not combine them into a generic facility count and call that accessibility. |
| [3D pedestrian geodatabase](organized/core/pedestrian/3D_Pedestrian_Network_FGDB.zip) | Main routing input: 465,892 3D segments with walkway types, stairs, ramps, lifts, crossings, barrier flags, gradients, directions and access schedules. Related tables identify terminals, buildings, floors and sites. | Preserve levels when building connections. Check feature type as well as barrier flags: some staircase records disagree with their barrier flag. `WheelchairAccess` identifies accessible entrances; it is not a requirement for every ordinary walkway. Verify gradient semantics before numerical slope filtering. |
| [Pedestrian network metadata](organized/core/pedestrian/network_metadata.pdf) | Documents coverage, reference system, stated accuracy and update information. Helps avoid coordinate errors and unsupported precision. | Metadata says approximately 1 m XY and 2 m Z accuracy, insufficient to measure small kerbs. Verify archive release provenance rather than assuming the metadata revision date is the date of every route record. |

## Official iGeoCom data: use for MTR entrances and coordinates

Source: [Lands Department iGeoCom on DATA.GOV.HK](https://data.gov.hk/en-data/dataset/hk-landsd-openmap-development-hkms-digital-geocom). Downloaded during this project on 12 October 2026. The public dataset listing specifies quarterly updates; individual record revision dates vary.

| File | Why it is useful | Important limits and handling |
|---|---|---|
| [Entrance CSV](organized/core/mtr/official_igeocom/mtr_access_points.csv) | 611 official railway entrance/access records with named exits and WGS84 latitude/longitude added from matching official GeoJSON IDs. Convenient for Python loading and joining to MTR facility text. | Contains source revision dates and access categories. Count is records, not a guarantee of all unique exits. One record lacks a site-name value, although its name identifies Diamond Hill Exit D. |
| [Entrance GeoJSON](organized/core/mtr/official_igeocom/mtr_access_points.geojson) | Same 611 access features with original official geometry and attributes. Useful for spatial joins, nearest-entrance searches and maps. | Coordinates are `[longitude, latitude]` in WGS84. `EASTING`/`NORTHING` attributes use Hong Kong 1980 Grid. CSV and GeoJSON are alternative views of the same records; do not count both. |
| [Railway station GeoJSON](organized/core/mtr/official_igeocom/railway_stations.geojson) | 98 official railway-station point records for station lookup, general proximity and coverage comparisons. | Station points are distinct from entrance points and are not sufficient targets for accessible directions. Reconcile names/codes before joining; record count is not a completeness guarantee. |
| [Official dictionary](organized/core/mtr/official_igeocom/data_dictionary_v5.pdf) | Defines coordinate systems, fields, source codes and access categories. Necessary to interpret the data correctly. | Keep it with the records and consult it when implementing filters. |
| [Source manifest](organized/core/mtr/official_igeocom/source_manifest.json) | Records source URLs, retrieval time, hashes, extraction counts and limitations. Makes the download and derivation traceable. | This is the existing provenance file copied unchanged. Use this guide's copy manifest to trace the newly organized copies. |
| [Original CSV archive](organized/core/mtr/official_igeocom/source_csv.zip) | Preserves the downloaded full community dataset, allowing extraction to be reproduced and other useful points to be examined later. | Includes many unrelated community facilities. Filter by documented feature type, rather than searching addresses for “MTR.” |
| [Original GeoJSON archive](organized/core/mtr/official_igeocom/source_geojson.zip) | Preserves the full official spatial source and original geometries. Supports reproducing the entrance/station extracts and future updates. | Includes the same underlying community dataset in another format. Keep for provenance; use filtered extracts for the initial program. |

The official access subcategories are:

| Code | Meaning | Records |
|---|---|---:|
| `MTRLIF` | Barrier-free access with lift | 119 |
| `MTRRAM` | Barrier-free access with ramp | 56 |
| `MTRSLV` | Barrier-free access at same level | 61 |
| `MTRSTL` | Barrier-free access with stair lift | 11 |
| `MTRWCA` | Barrier-free access with wheelchair aid | 2 |
| Blank | Unspecified | 362 |

Blank does not mean inaccessible. Equipment categories do not establish current availability, independence from assistance or continuous access to the required platform.

## Supplementary data: useful after core connectivity is working

| File | Why it is useful | Important limits and handling |
|---|---|---|
| [5 m terrain archive](organized/supplementary/terrain/Whole_HK_DTM_5m.zip) | Contains a territory-wide terrain grid. Useful for terrain maps, comparing hilly areas and investigating broad elevation patterns. | A 5 m grid cannot reliably determine kerbs or short ramp slopes. The ASCII file does not embed a CRS definition. Confirm product metadata before integration; use explicit pedestrian-network features for route access decisions. |
| [Hospital records](organized/supplementary/hospitals/facility-hosp.json) | 44 hospital records with coordinates and A&E indicators. Supports a later extension from nearby transit access to hospital journeys. | Optional for the initial task. Hospital pins and A&E labels do not identify accessible hospital entrances. |
| [District boundaries](organized/supplementary/map_context/district_boundaries.json) | Useful for district-based summaries, grouping estates geographically and drawing maps. Existing map notes identify the Home Affairs Department boundary source. | Geographic context, not evidence of pedestrian connections or accessibility. Retain source provenance from the map notes. |
| [Land outline](organized/supplementary/map_context/hong_kong_land.geojson) | Provides land/coastline context for maps and terrain displays. | Existing notes identify an OSM-derived GitHub source. Not a walkway network, and coastline vintage may differ from other data. Preserve OSM attribution. |
| [Original map notes](organized/supplementary/map_context/original_map_notes.md) | Preserves source links, attribution, terrain handling and assumptions for the map-context files. | Copied unchanged from `analysis/maps/`. Its relative links describe the original map directory and may not resolve here; consult the original directory for those rendered outputs. |

## Older reference data: comparison only

| File | Why it is useful | Important limits and handling |
|---|---|---|
| [2020-era appended station coordinates](organized/reference/legacy_2020/station_coordinates_APPENDED.csv) | Provides an older station-coordinate table for comparison and spotting changes. Retains the appended Central–Hong Kong walking rows from the supplied GitHub bundle. | Has 94 distinct station codes and lacks Exhibition Centre, Sung Wong Toi and To Kwa Wan compared with the main station file. Coordinates are station-level, not exit-level. The walking rows do not prove an accessible connection. Prefer official iGeoCom for routing targets. |

The other files in `data/2020 data github public set/` remain in place. They were not copied into this selected collection: older fares are outside the immediate pedestrian-access task; line speeds cannot establish walking accessibility; schematic-map coordinates/images do not supply exit locations; and the remaining CSVs are older overlapping tables or transformation inputs superseded by the selected copies.

## Recommended use together

1. Find an estate using the estate records, then establish its actual entrance/start connector.
2. Use bus stop records or official iGeoCom access points as candidate transit targets.
3. Resolve MTR station identities and exit labels; combine entrance categories with station facility descriptions.
4. Route over the 3D pedestrian network with the user's hard mobility constraints, including time restrictions.
5. Rank valid routes by distance, slope/effort, crossings, equipment reliance and user preferences.
6. Report missing evidence and distinguish reaching an entrance/stop from reaching a platform or boarding.

The [main assessment](../analysis/accessibility_report.md) and [coordinate-source investigation](../analysis/mtr_coordinate_sources.md) provide the detailed model and source checks. This organization does not modify source data, compute routes or certify access.
