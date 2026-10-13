# Explanation of all fourteen Step 1 warning groups

Reviewed 13 October 2026 for run `20261013T121410Z-c823aaf9`. Preparation has **zero blocking errors**. All 31 tests passed again in the final check. Source hashes, modelling policy, registry links and SQLite integrity were rechecked. Earlier full read-back checks covered every geometry/attribute/null and all sixteen reference tables; the independent audit additionally compared all 69,364 original service records.

Warnings preserve missing or limited evidence. They do not mean the records were lost or that the pipeline failed. Several groups overlap, so their affected-record counts must not be added as distinct defects. Routing and final ranking are later stages; a gap matters when a later operation requires the missing relationship.

## 1. Estate allocation boundaries are geographic proxies

The estate-category lookup was derived in earlier project analysis using documented allocation categories and geographic town-area proxies, rather than an official HA boundary polygon dataset. All 244 current estates have one category and their names/coordinates match the source. This warning records the derivation limit; it is not a failed assignment.

For new estates or a disputed boundary case, verify the actual allocation category against suitable HA information. Do not assign it merely from the administrative district or extend the proxy uncritically.

## 2. Facility station IDs 70 and 888 are absent

The facility CSV has 36 rows for each ID, giving 72 rows without a corresponding station in the station CSV. These are two unknown station identities, not 72 stations. The dictionary explains the ID column but does not identify those values. All rows are preserved with null physical station links.

A compatible station reference or documented publisher mapping is needed to attach them. ID 70 includes a stair lift described as Middle Bridge; that description does not establish a station identity. Do not guess from a nearby station or infer that 888 is a placeholder without evidence.

## 3. 335 MTR access points lack mobility evidence

Of 362 blank iGeoCom categories, 27 now have positive named-exit facility evidence and 335 still do not. Their coordinates and physical station matches are known. Blank evidence does not establish either accessibility or inaccessibility.

These records remain general-mode starting candidates. They are outside the wheelchair mobility candidate list unless supported evidence is added. Entrance-specific equipment/access information can resolve relevant cases; no complete survey of all unknown points is required to retain/use the supported records.

## 4. Ten access points have no named exit code

The source identifies a station and access point but supplies no exit label such as A1. All ten points retain their original coordinates, native access identities and matched physical station IDs, with exit_code null.

They can still be identified by access ID. Obtain a supported exit label if a later display or relationship needs one; do not invent codes. The ten records are listed in mtr_match_review.csv. This is not unresolved station matching.

## 5. Nine positive facility rows have no matched station and named exit

These facility descriptions cannot be mapped to an explicit external access coordinate. They include arrival/departure halls at Lo Wu/Lok Ma Chau, Airport side walkways, blank descriptions for Tin Hau/Ngau Tau Kok/AsiaWorld-Expo, and the unidentified ID 70 Middle Bridge stair lift.

They remain preserved facility evidence. Resolve the missing station or exact equipment/exit location where needed. A station centre must not be substituted as the equipment position. This group overlaps the unidentified ID 70 warning.

## 6. Twenty-two facility rows have at least one exit without an exact point match

A description can name several exits; some may match and others may not. The review reports each missing code while retaining the supported matches. A general label such as A has not automatically been equated with numbered sub-exits such as A1/A2, and some named exits have no supplied coordinate record.

Review the particular exit/sub-exit relationship or obtain its location from suitable provider information. Preserve exact named matches and do not merge labels or invent coordinates. These are 22 facility rows, not necessarily 22 distinct missing exits.

## 7. Three equipment descriptions differ between sources

The remaining differences are Tin Shui Wai C (ramp versus lift), Diamond Hill A2 (lift versus ramp), and LOHAS Park B (same-level access versus lift).

Different equipment can coexist at an exit, so these are not proven contradictions. Both sources are retained. Check exact equipment scope/location if a connector or eligibility choice needs it; do not overwrite one description with the other.

## 8. Three stations have no mapped mobility access point

Heng Fa Chuen, Racecourse and Ngau Tau Kok have no access point with usable mobility evidence in the current master selection. Their physical stations and mapped general access points are retained. This means mobility coverage is missing in these sources, not that the stations are physically inaccessible.

Obtain/locate suitable entrance evidence where wheelchair coverage is needed. Until then, keep the lack of mapped evidence visible; do not insert station-centre coordinates as accessible entrances. Other supported stations remain available as candidate targets.

## 9. Two Castle Peak Hospital site-reference versions share one SiteID

The network's supporting site table contains two records for SiteID 1503020249, differing in dates and name capitalisation. Both have distinct source-record IDs and are preserved. This is separate from the hospital map-point target dataset.

No version choice is required merely to store the records. If later processing needs one canonical site description, use a documented version-selection rule after checking the relevant source evidence. Do not silently discard either version.

## 10. Nine terminal references are missing, affecting eleven paths

These paths carry TerminalID values absent from the supporting terminal table. Their path geometry and original IDs are retained.

Check compatible source versions or required terminal information if a graph connection depends on those IDs. A missing supporting row does not by itself establish that the path geometry is unusable.

## 11. Three floor references are missing, affecting thirty-four paths

These paths carry FloorID values absent from the floor table. Floor information can matter when deciding whether nearby paths are on the same level.

Use the preserved XYZ and available relationship evidence, and obtain/resolve the missing floor records where needed. Do not join every XY crossing as a junction or discard all affected paths automatically.

## 12. 107 site references are missing, affecting 280 paths

The source paths reference site identities absent from the supporting site table. Their geometry remains available; the absent site description/relationship has not been invented.

Investigate source-version compatibility or additional reference information only where a later operation needs the site relationship. This is a source relationship gap, not a coordinate conversion failure.

## 13. Forty-four building references are missing, affecting 248 paths

These are missing BuildingID_1 references to the building table. BuildingID_2 has no missing-reference finding in this snapshot. Building/site/floor warning groups can affect the same path.

Resolve the required building identities or supporting source version where an entrance/building connection depends on them. Preserve geometry and unknowns rather than inventing an association.

## 14. Nine distance-post records reference absent paths

The distance-post table has nine PedestrianRouteID references absent from the loaded network. The distance-post records are retained with their original references.

Check compatible path/reference snapshots or additional source coverage if these posts are used later. The absent references do not add missing network paths automatically and do not invalidate otherwise preserved walking geometry.

## Final check and publication scope

The final checks passed for **Step 1 preparation**: 476,153 spatial records; actual GeoDataFrame outputs; all 1,963,912 network vertices retained; all original service records preserved; derived unknown code 99; appropriate mode candidates; all MTR station/access points matched physically; all configured source hashes checked; zero rejection records; and a valid, unchanged estate/hospital identity registry.

These source limitations remain open and documented. Publishing the prepared data to the project repository does not claim that production routes, wheelchair speeds, equipment locations or the final ranking are complete. The context and human-readable plan retain unfinished items unchecked.
