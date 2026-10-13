# MTR physical-station and mobility-access masters

Created on 13 October 2026 using the supplied MTR dictionary ZIP and local data. The two main files contain no line or route fields.

## What the two files mean

[mtr_station_master.json](../mtr_master/mtr_station_master.json) contains **98 physical stations**, with English/Chinese names, latitude, longitude and one unique `station_id`. A station serving several lines appears once. Hong Kong station's old CSV IDs `39` and `44`, for example, both map to `MTR-S-550143`. Coordinates come from the station's original iGeoCom point. A station map point is not an entrance.

[mtr_mobility_exit_master.json](../mtr_master/mtr_mobility_exit_master.json) contains **276 mobility access records across 95 stations**. Each has an `access_id`, the physical `station_id`, an exit code where supplied, its own latitude/longitude, mobility types and the evidence supporting those types. These coordinates come from iGeoCom access points, never from the station centre.

The station ID is `MTR-S-` followed by the station's original iGeoCom `GEONAMEID`. The access ID is `MTR-A-` followed by the access point's original `GEONAMEID`. Changing CSV row order or line membership does not change these IDs.

An **access record** is one point recorded by the source. Several points can refer to the same named exit. They remain separate because sharing a name or coordinates does not prove they are the same physical entrance or piece of equipment. The 276 records should therefore not be described as 276 verified distinct exits.

Ten mobility access records have no named exit code in the source. They retain their real coordinates and have `exit_code: null`; no exit label has been invented.

## How the dictionary was used

The following PDFs inside [mtr DataDictionary.zip](../../original_data/mtr%20DataDictionary.zip) were read directly:

1. `mtr_lines_and_stations_dataspec.pdf`: station IDs, station codes, names, UTF-8 encoding and name-entity decoding.
2. `barrier_free_facilities_dataspec.pdf`: `Station_No` means the station CSV's ID; `Key` identifies a category; `Y` means available and `N` unavailable; English/Chinese text describes the location or exit. **`Exit_Coordinate_X_Y` is “not in use.”** It supplies no usable location evidence here. Facility information describes static provision, rather than live equipment operation.
3. `barrier_free_facility_category_dataspec.pdf`: `Key` is joined to `Item_Code` to decode the category and equipment descriptions.

The extracted definitions and PDF text are retained in [mtr_dictionary_decoded.json](../mtr_master/mtr_dictionary_decoded.json). All **3,564 facility rows** are preserved and decoded in [mtr_facilities_decoded.json](../mtr_master/mtr_facilities_decoded.json), including unavailable and unlocated records.

## Which access points were included

A point is included when its iGeoCom category explicitly identifies a lift, ramp, same-level access, stair lift or wheelchair aid, or when a positive external-access facility description names its exact station and exit.

There are **249 points with an explicit iGeoCom mobility category**, plus **27 otherwise unspecified points with linked named-exit facility evidence**, giving 276 records. Paid-area lifts and general station facilities, such as wide gates or toilets, do not turn a street entrance into a mobility access point.

Each evidence entry identifies its scope. An iGeoCom subcategory describes its source point. A facility description naming “Exit A” establishes equipment at that exit; it does not locate that equipment at every map point carrying “Exit A.” Equipment location within the exit still needs care when constructing network connections. Both descriptions are retained when sources mention different equipment.

`assistance_related` flags stair lifts and wheelchair aids. `exit_only_evidence` records an explicit exit-only description. Neither field considers opening hours: the project's always-open assumption applies. The master stores evidence separately from later routing eligibility. The latest parameter rules are in [the project context](../../instructions/project_context_and_decisions.md): all 611 access records are general-mode candidates; the 276 mobility-evidence records are wheelchair candidates. Lifts, stair lifts and wheelchair aids are allowed for wheelchair mode; wheelchair aids and stair lifts are excluded generally. The candidate lists still need equipment/path filtering and connections; they do not certify a complete street-to-platform journey.

## What is resolved and what remains

- [X] All **611** source access points link to a physical station. Racecourse and the Diamond Hill record with a missing site name now match through their full source names.
- [X] All **100** station IDs in the station CSV map to physical stations, including the separate Airport Express/Tung Chung Line IDs for Hong Kong, Kowloon and Tsing Yi. Lines/routes do not enter the main masters.
- [X] Available/unavailable facility codes and equipment categories are decoded. All original facility records and categories remain available.
- [X] Coordinates, identity uniqueness, station references, record counts and saved JSON preservation are checked. Tests also check row-order independence and prevent station-level equipment from spreading to every entrance.
- [ ] **Station IDs `70` and `888`:** each has 36 facility rows, but neither is in the station CSV. The dictionary explains the ID field without identifying these two values. Their 72 rows retain `station_id: null`. No identity has been guessed.
- [ ] **335 points without mobility evidence:** these remain in the full access-to-station map and the review file, rather than being called inaccessible or silently discarded. Their equipment/accessibility is unknown in the supplied sources.
- [ ] **Ten unnamed mobility points:** their locations and station links are known; their exit codes are not supplied. Keep the codes null unless supported information becomes available.
- [ ] **Nine positive facility rows without a matched station and named exit:** descriptions include arrival/departure halls, blank locations and the unidentified ID `70` “Middle Bridge” stair lift. They cannot be placed at an invented exit coordinate.
- [ ] **22 facility rows have at least one named exit without an exact coordinate match.** Some descriptions name a general exit such as A while the point source names A1/A2; the builder does not invent that relationship. Matched exits within the same description are retained, and only missing codes are reported.
- [ ] **Three equipment-description differences:** Tin Shui Wai C (ramp/lift), Diamond Hill A2 (lift/ramp), and LOHAS Park B (same-level/lift). Different facilities may coexist; both sources remain visible.
- [ ] **Three stations lack a mapped mobility point:** Heng Fa Chuen, Racecourse and Ngau Tau Kok. This means the supplied data does not locate suitable access evidence for them; it does not establish that the stations are physically inaccessible.

All remaining cases are in [mtr_master_review.json](../mtr_master/mtr_master_review.json). Further work should target the specific missing identity, exit label or equipment-location relationship, rather than repeat the now-resolved line-ID matching.

## Explanation of all eight files

| File | What it contains and why we keep it |
|---|---|
| [mtr_station_master.json](../mtr_master/mtr_station_master.json) | The main station list: 98 physical stations, each with one unique station ID, English/Chinese names and coordinates. Several old line-specific IDs can point to this one physical station. |
| [mtr_mobility_exit_master.json](../mtr_master/mtr_mobility_exit_master.json) | The main mobility-access list: 276 original access points linked to station IDs, with exit codes where supplied, coordinates, equipment types and supporting evidence. Stair lifts/wheelchair aids and explicitly exit-only descriptions are flagged. Ten points have no supplied exit code. |
| [mtr_legacy_station_id_map.json](../mtr_master/mtr_legacy_station_id_map.json) | A translation table connecting all 100 old station CSV IDs to our physical station IDs. It lets original facility records attach to the right station. For example, Hong Kong's old IDs 39 and 44 both map to MTR-S-550143. |
| [mtr_access_station_map.json](../mtr_master/mtr_access_station_map.json) | The complete list of all 611 original access points and their matched stations. It includes the 335 points without mobility evidence, keeping their locations and identities available without assigning unsupported equipment types. |
| [mtr_facilities_decoded.json](../mtr_master/mtr_facilities_decoded.json) | All 3,564 original facility rows, with codes translated to equipment descriptions, Y/N translated to available/unavailable, location text, extracted exit codes and station IDs where known. It retains original records and category definitions. The 72 rows for IDs 70/888 keep null station links. Internal/general facilities also remain here even when they do not qualify for the mobility-access master. |
| [mtr_dictionary_decoded.json](../mtr_master/mtr_dictionary_decoded.json) | Text extracted from the three relevant PDFs in the supplied MTR ZIP, plus the field definitions used by the builder. It records what Station_No, Key and Y/N mean and why the unused facility coordinate field is not location evidence. |
| [mtr_master_review.json](../mtr_master/mtr_master_review.json) | The unresolved-case list: unidentified station IDs, unknown mobility evidence, unnamed exits, unlocated facility references, equipment-description differences and stations without mapped mobility access. Retaining a case here does not resolve it. |
| [mtr_master_manifest.json](../mtr_master/mtr_master_manifest.json) | The build record: creation time, exact source paths, file hashes, record counts, coordinate system and identity/selection rules. A hash is a file fingerprint used to check that an input has not changed. |

The first two files supply the intended station and mobility-access targets for later routing. The remaining files explain the source relationships, retained evidence, unresolved cases and how to reproduce the result.

## Source location and reproduction

The input folder is now `work/original_data`, renamed from `work/data` at the user's request. The current master manifest uses the new paths. Historical saved runs and gradient examples retain the source paths recorded when they were created; resolve an old `work/data/` prefix through `work/original_data/` when checking them. Source contents are unchanged, and the separate repository-root `data/` folder retains its name.

Inputs are `work/original_data/railway_stations.geojson`, `mtr_access_points.geojson`, `data_dictionary_v5.pdf`, `mtr DataDictionary.zip`, and the three CSVs in `work/original_data/reference/`: `mtr_lines_and_stations.csv`, `barrier_free_facility_category.csv`, `barrier_free_facilities.csv`.

From `work/`, using the existing local virtual environment:

```sh
PYTHONPATH=src ../.venv/bin/python -m estate_ranking.mtr_master
PYTHONPATH=src ../.venv/bin/python -m unittest discover -s tests -v
```

Step 1 rebuilds and checks all eight files in its successful snapshot at `precomputed/outputs/current/mtr_master/`. The original `precomputed/mtr_master` bookmark points there. The standalone command writes `precomputed/outputs/mtr_master/`, with versions under `outputs/mtr_master_runs/`. Successful outputs remain trackable in Git.

The full Step 1 rerun now incorporates these physical station IDs and evidence into its GeoPackage/SQLite outputs and embeds the masters in the same snapshot. All access/station points match; the new review CSV retains ten genuinely unnamed codes. Old saved runs retain their historical 45-case review and older relationships. Later routing uses the integrated current snapshot.
