# Official MTR entrance coordinate source found

Checked and downloaded on 12 October 2026.

## Finding

The official Lands Department **GeoCommunity Database (iGeoCom)** provides named railway entrance/access points, station points, coordinates, and barrier-free access subcategories. It addresses the missing exit-coordinate field in the original MTR facilities CSV by providing a separate source that can be joined and reconciled. It does not fill that CSV automatically, prove every exit is present, or establish a continuous usable journey.

Dataset: https://data.gov.hk/en-data/dataset/hk-landsd-openmap-development-hkms-digital-geocom

Publisher description: https://www.landsd.gov.hk/en/survey-mapping/mapping/other-products/iGeoCom.html

The dataset listing says quarterly updates. Individual records retain their own revision dates; many access records have 2021 dates. Downloading the latest archive does not mean every point was recently surveyed.

## Downloaded and inspected

The official CSV and GeoJSON downloads contain 37,379 community points. Filtering by `TYPE = MTA`, defined by the official dictionary as Railway Station Entrance, gives **611 access records**. Filtering by `TYPE = RSN`, Railway Station, gives **98 station records**.

The access records have 98 distinct nonblank `E_SITENAME` values. One Diamond Hill Exit D record has no site-name value, although its English name clearly identifies the station. These counts are not a completeness certificate or necessarily counts of unique physical entrances/station complexes.

| SUBCAT | Official definition | Access records |
|---|---|---:|
| MTRLIF | MTR Barrier-free Access with Lift | 119 |
| MTRRAM | MTR Barrier-free Access with Ramp | 56 |
| MTRSLV | MTR Barrier-free Access at Same Level | 61 |
| MTRSTL | MTR Barrier-free Access with Stair Lift | 11 |
| MTRWCA | MTR Barrier-free Access with Wheelchair Aid | 2 |
| Blank | No subcategory supplied | 362 |

Blank subcategory is unknown/unspecified; it is not a negative accessibility label. Equipment categories require further checks of suitability, availability and assistance conditions.

The official version 5 dictionary confirms that GeoJSON point geometry is **WGS84**, ordered longitude then latitude. The `EASTING` and `NORTHING` attributes are **Hong Kong 1980 Grid**. This is particularly useful because the supplied pedestrian network uses Hong Kong 1980 Grid horizontally.

Examples copied from downloaded GeoJSON, presented in latitude/longitude order for readability:

| Entrance | Latitude | Longitude | Category |
|---|---:|---:|---|
| Olympic C3 | 22.31812 | 114.16072 | Lift |
| To Kwa Wan C | 22.31628 | 114.18715 | Lift |
| Sung Wong Toi A | 22.32615 | 114.19193 | Lift |
| Exhibition Centre B3 | 22.28123 | 114.17458 | Lift |

The last three stations were absent from the old GitHub coordinate file. They are present here with named access points.

## Other sources checked

**MTR station location maps and layouts:** https://www.mtr.com.hk/en/customer/services/system_map.html

This official page provides station-by-station map/layout PDFs. These are useful for checking entrance labels and internal access arrangements. I did not establish a documented bulk numeric exit-coordinate download from MTR's own pages. The PDFs should complement, rather than replace, machine-readable entrance coordinates.

**CEDD government MTR EXIT layer:** https://ginfo.cedd.gov.hk/server/rest/services/BasemapBlack/MapServer/416

Its downloaded ArcGIS schema identifies point geometry, Hong Kong Grid coordinates, `RAILWAYENTRANCEID`, `ENTRANCENAME`, and a query capability. However, the attempted bulk GeoJSON query returned `Failed to execute query`. The schema does not provide a station-name field or accessibility flags. Treat this as an additional official mapping lead, not the downloaded usable source.

**CSDI iGeoCom FeatureServer:** the attempted direct FeatureServer metadata request returned `Token Required`. Public CSV and GeoJSON archives were accessible through the government's published download links, so those were used. No attempt was made to bypass access controls.

**OpenStreetMap fallback:** https://download.geofabrik.de/asia/china/hong-kong.html

The full Hong Kong OSM PBF extract is available from Geofabrik. OSM documents entrance nodes with `railway=subway_entrance`, exit labels using `ref`, and optional wheelchair attributes: https://wiki.openstreetmap.org/wiki/Tag:railway=subway_entrance

OSM's Hong Kong mapping page warns that not all exits are mapped: https://wiki.openstreetmap.org/wiki/Hong_Kong/Transport/Routes/MTR

OSM is a useful supplementary source for comparisons and missing details. No OSM exit extract was downloaded or its coverage measured in this task because a suitable official open source was successfully obtained. Use the full PBF when all original tags are needed; do not assume simplified exports preserve all entrance/accessibility attributes. Follow OSM attribution/licensing requirements when using it.

## Saved artifacts

In `data/official_igeocom/`:

- `source_csv.zip` and `source_geojson.zip`: downloaded source archives.
- `data_dictionary_v5.pdf`: official dictionary.
- `mtr_access_points.csv`: 611 original access rows with WGS84 longitude/latitude added from matching GeoJSON feature IDs.
- `mtr_access_points.geojson`: the same access features, preserving source properties and geometry.
- `railway_stations.geojson`: 98 railway-station features.
- `source_manifest.json`: source URLs, retrieval time, source hashes, counts and limitations.

Reproduce extraction using:

```sh
.venv/bin/python analysis/extract_mtr_access.py data/official_igeocom/source_geojson.zip data/official_igeocom/source_csv.zip
```

The extraction checks unique access IDs, identical access-ID sets across CSV/GeoJSON, point geometry and plausible Hong Kong coordinate bounds. It does not verify positional accuracy in the field.

## How to use this in the ranking program

Create an entrance table keyed by the source `GEONAMEID`. Match station names to the project's station codes using a reviewed mapping, then extract and normalize exit labels. Preserve the original name and access subcategory. Reconcile multiple records or multiple access mechanisms without collapsing distinct nearby facilities.

Join MTR facility descriptions by station and exit label, using free-text parsing followed by review. Station IDs from different systems are not interchangeable. Connect entrance points to the pedestrian network using level-aware geometry and validated approach paths.

The official coordinates resolve the main **location-data gap**. Remaining work is coverage reconciliation, entrance-to-network connectivity, current equipment conditions, and entrance-to-platform access. The program must still distinguish reaching an entrance from reaching or boarding a train.
