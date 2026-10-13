# Housing allocation districts

Housing district means the four PRH allocation choices in HD300 Part 5: Urban, Extended Urban, New Territories, Islands.
Source: https://www.housingauthority.gov.hk/en/common/pdf/global-elements/forms/flat-application/HD300.pdf

`estate_housing_district_crosswalk.csv` maps all 244 organized estate records. The original JSON District Name remains an administrative district field.

Urban: Hong Kong Island and Kowloon.
Extended Urban: Tung Chung, Sha Tin, Ma On Shan, Tseung Kwan O, Tsuen Wan, Kwai Chung, Tsing Yi.
New Territories: Tuen Mun, Yuen Long, Tin Shui Wai, Sheung Shui, Fanling, Tai Po.
Islands: excluding Tung Chung.

All ten Sai Kung-labelled estates in this dataset are in Tseung Kwan O and are classified Extended Urban. This does not classify the entire Sai Kung administrative polygon as Extended Urban.
Seven Islands-labelled estates in Tung Chung are classified Extended Urban; the other five are Islands.

Counts: Urban 109; Extended Urban 70; New Territories 60; Islands 5.
## Maps

- `hong_kong_housing_districts.svg`: housing district overlay only, without estate/hospital points or pedestrian routes.
- `hong_kong_estates_hospitals_numbered.svg`: the existing numbered map updated to use the housing overlay. Administrative district lines and badges are removed; all 244 estate and 44 hospital points retain their original coordinates and numbering.
- Both maps have a corresponding `_preview.png`.
- `housing_district_boundaries.geojson`: four derived housing polygons in WGS84.

## Boundary construction

Whole administrative districts use the existing official HAD district polygons:
https://www.had.gov.hk/psi/hong-kong-administrative-boundaries/hksar_18_district_boundary.json

Urban merges Central and Western, Eastern, Southern, Wan Chai, Kowloon City, Kwun Tong, Sham Shui Po, Wong Tai Sin, and Yau Tsim Mong.
New Territories merges Tuen Mun, Yuen Long, North, and Tai Po.
Extended Urban merges Sha Tin, Tsuen Wan, Kwai Tsing, and the two smaller town-area selections below.
Islands is the official Islands polygon minus the Tung Chung selection.

The smaller-area selections use official **2019 Electoral Affairs Commission constituency geometry** (HK1980 / EPSG:2326), downloaded on 2026-10-12:
https://www.eac.hk/datagovhk/dc2019/DCCA2019.json
Catalogue: https://data.gov.hk/en-data/dataset/eac-eacpsi01-dcca-boundaries-2019

- Tung Chung: T02 Mun Yat, T03 Yat Tung Estate North, T04 Tung Chung South, T05 Tung Chung Central, T06 Tung Chung North.
- Tseung Kwan O: Q06 through Q29, excluding the rural Sai Kung and Hang Hau constituencies Q01 through Q05.
- Selected source records, original names, CRS, date, and URL are preserved in `data/organized/supplementary/map_context/housing_subdistricts_eac_2019.json`.

The town selections are **geographic proxies built from official smaller-area boundaries**, not Housing Authority-issued allocation boundaries. Constituency geometry can include surrounding undeveloped land, water, and airport areas. The source year is 2019, even though all current estate coordinates are covered. The form does not establish an exact boundary for every location in Hong Kong. Rural Sai Kung outside the Tseung Kwan O selection is therefore left unclassified and shown grey, rather than assigned to a housing district without evidence.

Merged polygons retain only outer rings and holes; internal member-district lines are not drawn. Marine boundaries are retained, while colour fills are clipped to the existing OpenStreetMap land layer. Historical coastline differences can affect reclamation fills without changing boundary geometry or estate coordinates.

## Reproduce and validate

Run from the repository root:

```sh
.venv/bin/python analysis/maps/render_estates_hospitals.py
.venv/bin/python analysis/maps/render_housing_previews.py
```

The renderer spatially checks all 244 estates against the derived polygons, requires exactly one housing district per estate, and verifies that it agrees with the estate crosswalk. Result: Urban 109, Extended Urban 70, New Territories 60, Islands 5. Original estate JSON fields remain unchanged; housing district is a separate crosswalk field.
The PNG previews use the same projected geometries and full original pedestrian route vertices, with Matplotlib rasterisation; SVGs retain the original vector routes.
