# Project context, agreed instructions, and agent handoff

Last updated: 13 October 2026.

## Read this first

This file records the user's decisions and the work completed in this conversation. A future agent should read it before planning, implementing, or interpreting the estate-ranking algorithm.

**Latest user instructions take precedence. This handoff takes precedence over older discussion and proposed defaults where they disagree.** Earlier design documents and the resolution register contain some questions that the user has since settled through explicit modelling assumptions. Historical validation reports describe their saved data snapshot; do not rewrite them to imply that later assumptions were publisher-confirmed facts.

Distinguish these statuses:

- **Agreed instruction:** implement or retain it; do not repeatedly ask the user to confirm it.
- **Provider-confirmed fact:** supported by a supplied dictionary, metadata, or checked source content.
- **Accepted assumption:** the user deliberately accepts it for this model, even when source documentation is incomplete.
- **Open decision or suggested implementation:** do not present it as agreed or completed.

**Latest work request:** update this context, both Step 1 plans and the original design, then rerun and verify all of Step 1. Spatial outputs must be real **GeoPandas GeoDataFrames**, persisted in a GeoPackage under **`work/precomputed/outputs/`**. `outputs/runs/` contains successful snapshots and `outputs/current/` selects the latest validated one. Use `estate_ranking.export.read_outputs()` or `read_geodataframe(directory, layer)` to obtain the actual GeoDataFrames. GeoPandas/pandas were installed in the local `.venv` through the approved installation request. Historical outputs outside this new folder remain historical snapshots.

The MTR physical-station and mobility-access masters are implemented as separate outputs described below. The source-folder rename to **`work/original_data`** is complete. Historical saved-run manifests retain their original paths: resolve their old `work/data/` or work-relative `data/` prefix through `work/original_data/` or `original_data/`. The repository-root `data/` directory is unchanged.

**Latest policy update:** retain stairs for general journeys; introduce a future wheelchair parameter that excludes stairs, escalators and travelators and excludes GMB services. Bus scope is KMB/CTB/GMB only. Unknown boarding codes become derived code 99 and are assumed to allow both pickup and drop-off. If no hospital is selected, consider all 44 institutions. Each estate has three subcosts (MTR, bus, hospital); their final combination is deliberately undecided. Standard Tobler is adopted for walking; wheelchair speed is deferred. Equal endpoint heights use at most two rounds of four random internal samples, with repeatable sampling and separately summed uphill/downhill interval times. These are recorded decisions/research, not a claim that production routing is implemented.

## 1. Project goal

Build a Python algorithm that lets a user select one of four Hong Kong Housing Authority public-rental-housing allocation categories and optionally a preferred hospital. Return a ranked list of estates in the selected category according to access to hospitals and public transport.

The four allocation categories are **Urban, Extended Urban, New Territories, and Islands**. They differ from the administrative districts in the estate JSON.

Use the pedestrian network for journeys. Hospitals use pedestrian-network distance; public transport uses gradient-adjusted walking time. Straight-line distances are not the ranking metric. District filtering applies to candidate estates; do not restrict the walking network or targets to that district merely because the user selected it.

The latest instruction supersedes the original universal no-stairs requirement: retain stairs in the general network. A future `wheelchair` parameter will select the relevant eligibility rules. With `wheelchair=true`, exclude stairs, escalators and travelators. Further equipment and cost rules remain to be specified where listed below.

**Final-output terminology:** an estate's final **cost** combines three separate **subcosts**: MTR, bus and hospital. The transport subcost algorithms use gradient-adjusted walking time; the hospital subcost algorithm uses pedestrian-network distance. The method of combining or scaling these three subcosts into the final cost has **not been decided**. Do not silently adopt a weighted sum, illustrative weights or a single minimum across MTR/bus/hospital.

## 2. Workspace, dependencies, and communication

- The working area is `work/` within the repository. Keep new program code and project outputs there.
- Prefer inputs in `work/original_data`. If something is absent, inspect the repository parent/root, `data`, or `data/organized`; these areas contain older and duplicate material.
- Use the existing repository-root `.venv` for Python. From `work`, the interpreter is `../.venv/bin/python`.
- The checked environment is Python 3.9.6 with Pyogrio 0.11.1, NumPy 2.0.2, Shapely 2.0.7, PyProj 3.6.1, pypdf 6.20.0, **GeoPandas 1.0.1 and pandas 2.3.3**. The latter two and their missing dependencies were installed with approval in the project's `.venv` to meet the GeoDataFrame requirement. PyArrow/Fiona/rasterio remain unnecessary. Preparation uses a columnar internal container; the public spatial outputs are actual GeoDataFrames with restored nullable types and height metadata.
- Do not install Homebrew packages. Further dependency installations still need an explanation and permission. The current rerun uses the now-installed local environment without another installation.
- Preserve original data. Keep exact source selections, hashes, source-record references, and assumptions visible.
- The team has project ideas but is less familiar with technical terminology. Explain terms and why a step matters, then state the implementation actions separately. Do not skip the intermediate steps in an explanation.
- In the human-readable plan, use actual Markdown task lists: `- [X]` for completed actions and `- [ ]` for unresolved or unfinished actions. Do not use emoji ticks. Do not tick an unresolved issue merely because it has been saved or mentioned.
- **Successful precomputed outputs must not be excluded from Git.** Temporary extraction, staged/failed runs, and local cache artifacts stay in `work/cache`, which is ignored. Precomputed outputs being trackable is not an instruction to push or commit without a task to do so.

## 3. Agreed coordinate and location assumptions

### 3.1 WGS84 for estate, hospital, and bus inputs

**Accepted assumption:** use WGS84 for estate, hospital, and bus/GMB longitude/latitude inputs.

The user downloaded the publisher specifications and explicitly accepted WGS84 despite those documents not naming a datum. Their reasoning was that the government datasets would be consistent with the documented iGeoCom format. Treat this as a deliberate model assumption, not independent proof of all publishers' conventions.

**Do not keep further datum confirmation as a required task or blocker for these three inputs.** Preserve the assumption and its rationale in metadata. Only revisit it if actual contradictory evidence or a failed location check is found.

The current Step 1 config already transforms them as EPSG:4326 and records assumptions. Its historical warnings predate the user's acceptance; the current resolution register now closes further certification as a required task without labelling the assumption a provider-confirmed fact.

### 3.2 Common grid and heights

Provider-confirmed facts:

- Pedestrian network: horizontal **HK1980 Grid, EPSG:2326**; vertical **HKPD height, EPSG:5738**, in metres.
- iGeoCom point geometry: **WGS84 longitude/latitude**. Its easting/northing attributes are **HK1980 Grid**.

Working X/Y coordinates use EPSG:2326, with X=easting and Y=northing. Direct PyProj transformations use `always_xy=True`. Preserve original coordinates. Do not overwrite network Z values or imply that an XY conversion also transforms height datums.

### 3.3 Estate and hospital map-point approximation

**Accepted assumption:** use the supplied estate/hospital map coordinates as the representative location. The user explicitly chose map-point approximation.

Do not require collection of verified gates, entrances or block coordinates before proceeding. Label these points honestly as map points rather than certified entrances. Heights are unknown for those point inputs; do not manufacture Z=0.

Later snapping still needs to connect each approximate point to an appropriate pedestrian path. Connector distance and implausible connections should remain visible. A maximum snap distance and detailed connector rule have not been agreed.

## 4. Always-open routes

**Agreed instruction:** assume every route is always open, at every time of day and on every date. Ignore access schedules entirely.

- Do not load or export the network's `AccessTime` or `AccessTimeDetails` records.
- Do not join/check schedule references, evaluate opening/closing hours, or request journey date/time for schedule handling.
- Any original `AccessTimeID` is retained solely as an unused source attribute.
- Source publication/update dates concern provenance, not route opening or closing.

This instruction is implemented in Step 1. It does not settle physical suitability, stairs, barriers, or how to interpret the separate `Enabled` field during graph filtering. Do not silently use those fields as a back door for access-schedule processing.

## 5. Gradient and distance: confirmed facts and agreed rule

### 5.1 Provider definitions

The supplied `3DPN_DataDictionary_v2.2.pdf` confirms:

- **PDF page 12:** `Gradient` is a segment angle in **radians**.
- **PDF page 14:** `SHAPE_Length` is **horizontal feature length in metres**. The GDB field is named `Shape_Length`.
- **PDF page 8:** grid/height references and stated accuracy, including vertical accuracy of ±2 m.

Every one of the 465,892 selected path lengths exactly matches its calculated XY polyline length. Original gradients are all nonnegative in this snapshot, although vertex order includes both rising and falling paths. The provider dictionary does not explicitly specify the gradient sign or within-path aggregation method.

Those omissions do not require us to invent another magnitude definition: the user has now chosen the following rule.

### 5.2 User's signed-gradient rule

**Agreed instruction:** use the supplied gradient magnitude `n` as it is. Determine uphill/downhill from the ordered height change:

```text
height_change = next_point_height - current_point_height

if height_change > 0:
    signed_gradient = +n
if height_change < 0:
    signed_gradient = -n
```

- Preserve the original value in `Gradient`/`gradient_raw`; signed values are derived separately.
- Do not replace the supplied magnitude with `atan(height_change / distance)` or another recomputed magnitude unless the user later changes this instruction.
- When comparing points belonging to the same provider polyline, retain that polyline's supplied `n` for each comparison. This was explicitly demonstrated with five more widely spaced vertices on a single path.
- Reverse the sign for reverse travel where the compared height change is nonzero.
- **Do not use `2*pi - n` for downhill slope.** The discussion corrected that proposal to `-n`, and the user subsequently explicitly adopted `-n`.
- The source `Direction` field means permitted travel relative to the drawn line, primarily for escalators/travelators. It is not an uphill/downhill sign.

**New agreed equal-height rule, including the user's follow-up:** when A and B have equal heights despite a nonzero/differing gradient indication, perform at most **two sampling rounds** on the actual A-to-B path:

1. Select four random internal positions, interpolate their heights along the existing XYZ polyline, and compare them with A and B. Use a fixed seed so repeated runs reproduce the same samples.
2. If the first round finds a height difference, treat the interval as non-flat, order the points along the path, and calculate local uphill/downhill interval times using the supplied magnitude and height-based sign. Sum those interval times. Do not run the flat-confirmation round unnecessarily.
3. If A, B and all first-round samples are level, select four additional internal positions between the same A and B, distinct from the first four.
4. There are now ten points: A, B and eight internal samples. Order them along the path and compare their heights. If they remain level, classify the portion as relatively flat for the model and use derived zero slope for its walking cost. Preserve the original gradient unchanged.
5. If the second round finds a difference, retain the local uphill/downhill classifications and sum their interval times. Stop after the second round in either case. Do not recursively sample each new subinterval or start a third round to seek confirmation.

**Explanation:** equal endpoint heights can hide a climb followed by a descent. A sequence of heights `10, 12, 14, 13, 11, 10` is uphill and then downhill in A-to-B travel; it has no single uphill/downhill sign. The two-round check is the user's flat-classification approximation; an unsampled height change can still exist. The earlier example's null signs are historical; production must implement the newer rule.

**Sampling/interpolation, fixed-seed repeatability and summing separately signed interval times are agreed** through the user's reply. Interpret “same height” as exact equality for now; no nonzero height tolerance has been selected. Preserve original vertices and use their local Z interpolation, not a straight interpolation between equal A/B endpoint heights that would erase intermediate bends/heights. Reuse the same canonical sample locations in reverse travel, reversing their order/signs. These technical details and derived classifications must be recorded and tested when routing is implemented.

Tiny Z differences should not be described as physically precise measurements. The examples classify stored values; they do not establish real-world millimetre accuracy.

### 5.3 Two cost models

**Agreed instruction:** use two different optimisation costs on the pedestrian network:

| Target | Agreed cost kind |
|---|---|
| Public transport, including MTR and eligible bus stops | Walking time adjusted for gradient |
| Hospitals | Plain pedestrian-network distance, without a gradient penalty |

The discussion interprets the hospital distance using the documented horizontal path lengths in metres. Do not substitute straight-line estate-to-hospital distance or transport walking time for this metric.

“Walking time + gradient” means gradient influences the travel-time calculation. Do not add a raw radian value directly to seconds. A conceptual form is `base_walking_time * slope_time_multiplier(signed_gradient)`.

**Agreed after research:** adopt standard **Tobler's hiking function for walking**. Decide wheelchair speed separately later; do not automatically reuse hiking speeds for wheelchair mode. Use **30 seconds of lift travel time per lift use and zero waiting time**, as an arbitrary accepted model assumption. Apply **no maximum ramp-slope cutoff for now**. Negative slope values must not become negative travel costs. Keep graph weights nonnegative for shortest-path algorithms.

The two models can choose different optimal paths. Label outputs with their actual units, such as metres for hospitals and seconds/minutes for transport. Retain three separate subcosts. Final combination/scaling is deliberately undecided, so do not combine raw metres and seconds or choose weights automatically.

### 5.4 Tobler research and adopted walking model

Read the [Wikipedia page supplied by the user](https://en.wikipedia.org/wiki/Tobler%27s_hiking_function) and [Tobler's original 1993 report](https://escholarship.org/uc/item/05r820mz.pdf). The function estimates hiking/walking speed from slope; the original report describes converting terrain slope to walking velocity for minimum-time journeys.

```text
slope_ratio = tan(signed_gradient_radians)
speed_kmh = 6 * exp(-3.5 * abs(slope_ratio + 0.05))
time_seconds = horizontal_length_metres * 3.6 / speed_kmh
```

Converting the preserved signed angle with `tan` supplies the function's rise/run input; it does not replace the provider's gradient magnitude with an angle recalculated from heights. The user has adopted this standard walking function for the transport model. Hospitals retain plain distance costs. Wheelchair speed is explicitly deferred.

Calculated examples: flat speed is about 5.04 km/h; using the earlier example magnitude 0.05129629 radians gives about 4.21 km/h uphill and 5.97 km/h downhill. Gentle downhill can be faster than flat; sufficiently steep downhill slows the function again. The standard function does not specify lift waiting/travel times or a wheelchair speed model. The user supplies a separate lift assumption: 30 seconds travel, zero wait; wheelchair speed remains deferred. Do not present hiking-speed output as measured wheelchair travel time.

The lift cost applies to the transport walking-time model, rather than applying Tobler to a vertical lift or giving it zero time because its horizontal length is zero. Do not charge 30 seconds separately for each polyline vertex. Hospital cost remains horizontal distance in metres; do not add 30 seconds to that distance. No hard ramp-slope exclusion is applied for now, though slope still affects walking time through Tobler. Timing for stair lifts/wheelchair aids or moving equipment has not been separately specified.

## 6. Wheelchair parameter, transport scope and boarding codes

### 6.1 Mode/operator eligibility

**Latest user instruction:** the bus subcost considers **KMB, CTB and GMB only**. General calculations retain all three. A future `wheelchair` parameter removes GMB services when true; KMB and CTB remain eligible under the user's accepted wheelchair-accessibility assumption. MTR remains the separate third transport category/subcost and retains its accepted mode-accessibility assumption.

- Do not reopen general vehicle accessibility certification as a mandatory prerequisite for using these accepted mode/operator assumptions.
- Preserve operator information and source evidence.
- A stop served by GMB and KMB/CTB can remain eligible in wheelchair mode through its KMB/CTB services. Filter service/operator evidence before deciding stop eligibility.
- Joint codes such as `KMB+CTB` are split into their operator memberships.
- Other bus operators, including LWB/NLB, are outside the selected bus scope. Preserve their original records, but do not include them in this bus subcost or reclassify them as KMB/CTB. Joint services can qualify through an included operator.

This mode policy does not mean every connecting footpath is wheelchair suitable. The pedestrian network's physical barriers remain separate from transport eligibility.

### 6.2 MTR access selection

**Agreed:** general mode starts with all **611 mapped access points** as candidate targets. Wheelchair mode starts with the **276 access records with mobility evidence**. Both then apply their equipment/path rules; accepting the general candidate pool does not override the general-mode wheelchair-aid exclusion. Do not discard either source list; apply the selection before deriving the estate's MTR subcost. Candidate counts are not guaranteed final counts after point/equipment filtering or connectivity checks.

**Agreed equipment eligibility, including the clarification:** lifts, stair lifts and wheelchair aids can be valid routes when `wheelchair=true`. In general mode (`wheelchair=false`), exclude **both wheelchair aids and stair lifts**; ordinary lifts remain eligible. This does not reverse the separate wheelchair exclusion of ordinary stairs, escalators and travelators. Keep equipment types distinct in the data and apply their mode-specific rules. Ordinary lift timing is 30 seconds travel plus zero wait; other equipment timing remains unspecified.

Unknown iGeoCom categories remain unknown evidence, even though the user accepts their points as general-mode candidates. Mapped equipment at an exit must still connect to the appropriate path; an exit-level description does not certify every piece of equipment at each nearby point.

### 6.3 Pickup/drop-off codes

Provider-confirmed meanings from `ptroutefare_geojson_dataspec.pdf`, PDF page 1:

| stopPickDrop | Meaning |
|---|---|
| 1 | Drop-off only |
| 2 | Pick-up only |
| 3 | Pick-up and drop-off |
| 0 | Not defined in the supplied specification |

Code 0 occurs in 25 raw bus rows at two stop IDs.

**New accepted assumption:** map an unknown/undefined pickup-drop-off value (including source code 0) to **derived code 99**, and assume it permits **both pickup and drop-off**. Keep the original source code and an assumption flag for traceability. Do not rewrite original input files or call code 99 a publisher-defined value. Codes 1/2/3 retain their documented meanings.

For future boarding-target selection, an included service with derived code 2, 3 or 99 supplies pickup permission; code 1 alone does not. Apply the operator/wheelchair selection before aggregating services at a stop. The rerun retains raw codes, implements derived code 99, and prepares mode-specific boarding candidates. Actual graph reachability/cost filtering remains later work.

### 6.4 Future wheelchair parameter

| Selection | Pedestrian paths/equipment | Bus services | MTR candidate pool |
|---|---|---|---|
| General / `wheelchair=false` | Retain ordinary stairs, escalators, travelators and lifts; exclude wheelchair aids and stair lifts | Include KMB, CTB and GMB | All 611 mapped access records, subject to path/equipment rules |
| `wheelchair=true` | Exclude ordinary stairs, escalators and travelators; allow lifts, stair lifts and wheelchair aids | Include KMB and CTB; exclude GMB | 276 mobility-evidence records, subject to path/equipment rules |

Keep the complete source/prepared data so both selections can be computed later. Do not permanently delete stairs or GMB from the shared data. The parameter must affect routing/target selection before calculating **all three subcosts**, since the optimal route and nearest eligible stop may change. General mode excludes wheelchair aids and stair lifts; wheelchair mode allows them. **Latest answer: when wheelchair=true, exclude paths with WheelchairBarrier=1.** Source code 2 means false; missing/unknown values remain explicitly unknown. MTR selection, ordinary lift timing and the absence of a hard ramp-slope limit are settled. Timing for other equipment remains open.

### 6.5 Hospital scope

**Agreed:** if no hospital is selected, consider **all 44 supplied institutions**, without an A&E-only filter. If a hospital is selected, use that institution as the hospital target. A&E information remains descriptive data, not an automatic eligibility requirement.

### 6.6 How targets produce the three subcosts

**Agreed through the user's reply:** use the **minimum reachable route cost within each eligible target group**:

| Estate subcost | Target selection and route metric |
|---|---|
| MTR | Minimum walking-time cost to an eligible access point under the selected mode's path/equipment rules |
| Bus | Minimum walking-time cost to an eligible boarding stop/service under the selected operator/wheelchair rules |
| Hospital, selected | Pedestrian-network distance to the selected hospital |
| Hospital, no selection | Minimum pedestrian-network distance to any of the 44 supplied institutions |

“Closest” therefore means minimum eligible network cost, not straight-line distance. Preserve the selected target ID, route metric/units and reachability alongside each subcost. Hospital and transport can use different optimal routes because they minimise different metrics. Treatment in the final ranking when an entire target group is unreachable remains to be decided with the final combination. Do not assign a zero cost to unreachable journeys. Keep MTR, bus and hospital subcosts separate; the final combining/scaling function is deliberately undecided.

## 7. Estate allocation lookup: what “crosswalk” means here

In data processing, a **crosswalk** is a lookup linking records or labels between sources. Here it connects estate names to allocation categories. It does **not** mean a pedestrian crossing or crossing coordinates.

The project-derived table already existed at:

- [analysis/maps/estate_housing_district_crosswalk.csv](../../analysis/maps/estate_housing_district_crosswalk.csv)
- Its selected working copy: [work/original_data/reference/estate_housing_district_crosswalk.csv](../original_data/reference/estate_housing_district_crosswalk.csv)

The lookup coordinates are copies of estate map points from the estate JSON. All 244 match exactly. The estate JSON is the location source; the lookup supplies the allocation category. Coordinate comparison checks estate identity/source consistency, not pedestrian distance or entrance usability.

Keep administrative district and allocation category as separate fields. Current counts are Urban 109, Extended Urban 70, New Territories 60, Islands 5.

The lookup was derived by earlier project analysis using documented HA categories and geographic proxies for named towns. It is not an HA-issued allocation-boundary dataset. Current records are assigned; verify categories if new estates are added. See [the derivation notes](../original_data/reference/HOUSING_DISTRICTS_README.md).

## 8. Current implementation and outputs

**Implemented for the rerun:** Step 1 ingestion, coordinate/type harmonisation, stable identities, estate allocation assignment, physical MTR masters linked into the spatial layers/SQLite tables, raw bus reconciliation, derived boarding code 99 and mode-specific boarding candidates, network/MTR mode-candidate flags, saved modelling policy, and staged export with actual GeoDataFrame read-back checks. Candidate flags do not establish network reachability and remove no source rows.

**Not implemented:** production graph construction, access-policy filtering, snapping/connector construction, either routing cost model, distance/time caches, or ranking. The local gradient demonstrations are examples, not completion of these later stages.

The latest successful full Step 1 snapshot is **`20261013T121410Z-c823aaf9`**, selected through `work/precomputed/outputs/current/`. It passed with **zero errors, 14 warning groups and 31 passing tests**. All six GeoDataFrames, sixteen reference tables, eight embedded MTR JSON files and the policy snapshot passed full read-back checks. All 23 source hashes were rechecked before publication. The old `20261013T081016Z-b7e527bb` run remains historical with its 93 row-level warnings. Lower warning count reflects resolved physical matching, accepted assumptions recorded as assumptions, and grouped retained source gaps; it does not mean all missing evidence was resolved.

| Spatial layer | Records |
|---|---:|
| Pedestrian network | 465,892 |
| Estates | 244 |
| Hospitals | 44 |
| MTR access records | 611 |
| Railway station reference points | 98 |
| Bus/minibus stops | 9,264 |

Total spatial records: 476,153. All exported geometries/attributes and reference-table values were checked after reopening. The network retains all 1,963,912 vertices and original Z coordinates. Only five non-schedule network supporting tables are loaded.

Code is in [work/src/estate_ranking](../src/estate_ranking). Configuration is [work/config/step_1.json](../config/step_1.json). Outputs are selected through [work/precomputed/outputs/current](../precomputed/outputs/current). The saved [validation report](../precomputed/outputs/current/validation_report.md) and [independent rerun audit](../precomputed/outputs/current/step_1_recheck.json) record the checks.

Run from the repository root:

```sh
cd work
PYTHONPATH=src ../.venv/bin/python -m estate_ranking.step_1 --config config/step_1.json
```

Tests from `work`:

```sh
PYTHONPATH=src ../.venv/bin/python -m unittest discover -s tests -v
```

Read [work/README.md](../README.md) for the storage/consumer API. In brief:

- Spatial outputs: six GeoDataFrames persisted as layers of `harmonised.gpkg`; support/relationship tables: `reference_tables.sqlite`. Use `read_outputs()` for the dictionary of all six GeoDataFrames or `read_geodataframe(directory, layer)` for one. Nullable integer/boolean/string fields are restored from the schema; original network Z/HKPD metadata remain intact.
- `model_policy.json` snapshots [routing_policy.json](../config/routing_policy.json), including policies for later routing and explicit unimplemented statuses. The source manifest records its hash and the GeoDataFrame output interface.
- `mtr_master/` within the same selected run contains all eight rebuilt MTR JSON files. Spatial `station_id` now means the physical MTR-S identity, with CSV IDs retained in a separate translation table. The new review CSV has unnamed exit-code cases, not the historical line-ID ambiguities.
- Field definitions/types/CRS: `schema.json`; provenance/hashes/assumptions: `source_manifest.json`.
- Checks: `validation_report.md`/`.json`; unresolved MTR cases: `mtr_match_review.csv`.
- Candidates and failures stay in cache; successful run directories live under `precomputed/outputs/runs`.
- A current-run symlink publishes data and its identity snapshot together. The local `config/entity_ids.json` link points to that snapshot. A fresh checkout restores identities/aliases from the published snapshot if the local link is absent.
- Original iGeoCom `EASTING`/`NORTHING` fields are named `source_grid_easting`/`source_grid_northing` to avoid case-insensitive collisions with working coordinate fields. Original properties remain in `raw_json`.
- Geodatabase FIDs identify records in their selected source snapshot; do not treat them as guaranteed persistent entity IDs across new source versions. Persistent path IDs and the estate/hospital ID registry serve different purposes.
- Coded booleans must be decoded explicitly: several fields use 1=true and 2=false, so ordinary Python truthiness would misread 2. WheelchairBarrier=1 indicates a segment assessed as unsuitable; WheelchairAccess=1 describes an accessible entrance/exit connection and is not a universal flag that every usable path must have. Keep codes, labels, nulls, and source definitions separate.
- Use `utf-8-sig` for JSON/CSV inputs where a BOM may be present. Do not turn nullable integer identifiers into strings such as `"117.0"`, or merge different stop IDs merely because their coordinates coincide.

## 9. Source files and provider evidence

### Physical MTR masters added after the original Step 1 export

**User instruction:** create one file with a unique ID, name and coordinates per physical station, ignoring lines/routes, and another with station ID, mobility exits/access points and their own coordinates. Use the supplied MTR dictionary to decode the CSVs.

**Implemented:** [mtr_station_master.json](../precomputed/mtr_master/mtr_station_master.json) has 98 stations; [mtr_mobility_exit_master.json](../precomputed/mtr_master/mtr_mobility_exit_master.json) has 276 mobility access records across 95 stations. IDs are `MTR-S-<station GEONAMEID>` and `MTR-A-<access GEONAMEID>`, independent of row order and line membership. Original iGeoCom WGS84 points supply coordinates. Ten mobility points have no named exit code and retain null codes. Distinct source points remain distinct even when coordinates/exit names coincide.

All 611 access points now match physical stations, including Racecourse and the Diamond Hill record. All 100 CSV station IDs map to these stations through a separate legacy-ID table. Hong Kong 39/44, Kowloon 40/45 and Tsing Yi 42/46 now each share one physical identity.

The ZIP's station, facility and category PDFs confirm `Station_No` refers to station CSV ID, `Key` to `Item_Code`, and `Y/N` to available/unavailable. The facility coordinate field is explicitly **not in use**. Decode all 3,564 facility rows; do not use that field as coordinate evidence. Use point-level iGeoCom mobility categories or positive external facility descriptions linked to the exact station/exit. Paid-area/general station facilities do not generate street entrance coordinates. Exit-level evidence does not locate equipment at each associated map point; its scope is recorded.

The selected 276 comprise 249 explicitly categorised points plus 27 otherwise unspecified points with named-exit facility evidence. All other 335 points remain in the full access map and review file. Assisted types, exit-only evidence and equipment differences are retained. The master itself does not implement routing filtering; later mode-specific eligibility now follows Section 6.

Run from `work/`: `PYTHONPATH=src ../.venv/bin/python -m estate_ranking.mtr_master`. The standalone output is staged/checked and published through `precomputed/outputs/mtr_master`. Step 1 embeds the same prepared records in `outputs/current/mtr_master/`; the original MTR bookmark points to that integrated snapshot. The full suite passes 31 tests. See [the master guide](../precomputed/docs/mtr_master_readme.md), [review](../precomputed/mtr_master/mtr_master_review.json) and [manifest](../precomputed/mtr_master/mtr_master_manifest.json).

**Integration status:** the new rerun incorporates the physical masters into its GeoPackage, SQLite relationships and embedded `mtr_master/` folder under `outputs/current`. Old saved runs retain their old relationships/reports. The standalone MTR command produces the separate `precomputed/outputs/mtr_master` output; the embedded version is the authoritative MTR snapshot for its corresponding Step 1 run.

### Input sources

| Source under work/original_data | Purpose |
|---|---|
| `3D_Pedestrian_Network_FGDB.zip` | `3DPN_P2.gdb`, paths, XYZ geometry, Gradient, Shape_Length, feature/barrier/direction fields and supporting references |
| `3DPN_DataDictionary_v2.2.pdf` | Field definitions: units/length/CRS, provider accuracy and coded-field semantics |
| `portal.csdi.gov.hk_csdi-webpage_metadata_landsd_rcd_1637222018065_52265_html.pdf` | General network metadata/CRS; does not supply the gradient field definition |
| `prh-estates (1).json` | Estate names, map locations, administrative districts and block information |
| `ha_hahdweb_dataspec.pdf` | Estate field definitions; does not explicitly name the coordinate datum |
| `facility-hosp.json` | Supplied hospital/institution points and A&E information |
| `Data-Specification-for-List-of-HA-Hospitals-Institutions-SOPCs-FMCs-en.pdf` | Hospital field definitions; does not explicitly name the coordinate datum |
| `mtr_access_points.geojson` | iGeoCom entrance/access points, native GEONAMEID and access subcategories |
| `railway_stations.geojson` | Station reference points; not a substitute for entrances |
| `data_dictionary_v5.pdf` | iGeoCom geometry/grid coordinate definitions and access subcategory meanings |
| `mtr DataDictionary.zip` | MTR station/facility/category field definitions; decoded for the new physical-station and mobility-access masters |
| `bus_stops.json` | Prepared unique stop list and operator flags; 9,264 stops including 4,776 GMB-labelled stops |
| `JSON_BUS.json`, `JSON_GMB.json` | Raw route-stop/service evidence: 56,209 bus rows and 13,155 GMB rows |
| `ptroutefare_geojson_dataspec.pdf` | Transport fields and pickup/drop-off code definitions |
| `reference/` | Selected MTR CSVs, allocation lookup, provenance and existing derivation notes copied from older project directories |

Exact source paths and hashes are in the current manifest. If a copied reference and its selected origin differ, inspect the change and explicitly select the intended snapshot; do not silently overwrite changed evidence. A bus-notes update during this work added only a reorganisation note; the previous copy was preserved in cache before the new copy was selected.

Do not use the DTM to overwrite elevated-path Z values. DTM use for later terrain/connector work is optional and has not been selected.

## 10. Outstanding source relationships and remaining decisions

These remain open unless the user later changes their status:

- [ ] **Equal-height implementation:** repeatable random positions along the XYZ path, at most two rounds of four samples, and separately summed uphill/downhill interval times are agreed. Use exact height equality for now. Implement and test the bounded ten-point flat check, retaining raw gradients and sampling evidence.
- [ ] **Time-model implementation:** standard Tobler for walking, summed local interval times and lift travel/wait of 30/0 seconds are agreed. Implement them; wheelchair speed is explicitly deferred and other equipment timing is unspecified. Hospital cost stays distance.
- [ ] **Physical graph implementation:** the type/equipment rules, wheelchair exclusion of WheelchairBarrier=1, and no maximum ramp-slope cutoff are agreed. Step 1 prepares base candidates without deleting rows. Actual directed connections, height compatibility and any use of Enabled still need graph-stage implementation; do not reintroduce schedules.
- [X] **MTR candidate preparation/integration:** all 611 points are retained, physical identities/evidence are integrated and base mode/equipment candidate flags are prepared. Actual graph connections and executable route filtering remain later work.
- [ ] **Unnamed MTR access codes:** physical station matching is resolved in the new masters. Of the old 12 parsing cases, two alternate name formats now parse; ten source points genuinely supply no named exit code. Retain their coordinates and null codes unless supported exit labels are obtained. The old 45-case report has not been rewritten.
- [ ] **Facility IDs 70/888:** 72 facility rows refer to these station IDs absent from the station CSV. These are two missing station identities, not 72 stations. Identify/document them without guessing.
- [ ] **Three access-evidence differences in the new master:** Tin Shui Wai C, Diamond Hill A2 and LOHAS Park B have different equipment descriptions. Both facilities may coexist. The older export reported five; improved facility parsing retains additional coexisting evidence. Check equipment/exit scope where routing needs it.
- [ ] **Unspecified MTR categories:** 362 blank iGeoCom categories; the new master links 27 to positive named-exit CSV evidence, leaving 335 unknown. The old export had 23 supplemented/339 unknown. Do not infer physical facts from a blank category or treat an exit-level description as exact equipment coordinates.
- [ ] **Unlocated MTR facilities/coverage:** nine positive facility rows lack a matched station and named exit; 22 rows have at least one named exit without an exact coordinate match. Heng Fa Chuen, Racecourse and Ngau Tau Kok lack mapped mobility points. Do not invent coordinates or equate missing mapped evidence with physical inaccessibility.
- [ ] **Missing network references where needed:** 9 terminal IDs affect 11 path rows, 3 floor IDs affect 34 rows, 107 site IDs affect 280 rows, and 44 BuildingID_1 values affect 248 rows. Nine distance-post records refer to missing path IDs. Investigate source compatibility or needed iB1000/reference data; do not discard valid geometries automatically.
- [ ] **Castle Peak Hospital preferred version, only if needed:** two site-reference records share a SiteID with different dates/capitalisation. Both are preserved; choosing one is not required for current ingestion or necessarily for the separate hospital point targets.
- [X] **Bus candidate preparation:** derive unknown code 99 with assumed pickup/drop-off permission, retain raw values and derive KMB/CTB/GMB general candidates plus KMB/CTB wheelchair candidates. Actual route reachability/cost calculation is unfinished.
- [ ] **Hospital-scope implementation:** all 44 institutions are included when none is selected. Implement the settled rule; do not reopen A&E-only scope as an unanswered question.
- [ ] **Snapping/connectivity:** construct and test real network connections, tolerances and connector rules using the accepted map-point approximation. Step 1 integrity checks do not establish reachability.
- [ ] **Subcost/ranking implementation:** minimum reachable route cost within each eligible target group is agreed. Implement the three separate subcosts and retain target IDs/units/reachability. Combining/scaling them into final cost and handling wholly unreachable target groups in that final ranking are deliberately deferred; original recommended weights are not agreed settings.
- [ ] **Optional later checks:** DTM use, new-estate allocation verification, dataset-currency review and interpretation of co-located records where relevant. Do not turn these into unnecessary prerequisites for accepted assumptions.

Closed as modelling decisions: always-open routes; WGS84 and map-point assumptions; supplied gradient magnitude with height-based sign and the two-round/four-points-per-round equal-height fallback; repeatable interpolated path samples and summed local interval times; standard Tobler for walking with wheelchair speed deferred; 30/0-second lift travel/wait and no hard ramp-slope cutoff; general retention of stairs with wheelchair exclusion of stairs/escalators/travelators; wheelchair allowance of lifts/stair lifts/wheelchair aids with general exclusion of stair lifts/wheelchair aids; KMB/CTB/GMB-only bus scope with wheelchair exclusion of GMB; 611/276 MTR candidate pools; unknown derived boarding code 99 treated as both; all 44 hospitals when none is selected; minimum reachable route cost within each target group; two cost-model kinds and three separate estate subcosts. Final combination remains deliberately undecided. Implementation status varies as described above.

## 11. Gradient demonstrations already performed

The user asked for five points on Pok Fu Lam Road from HKU C1 toward Queen Mary, then asked for points farther apart.

Sources used: MTR access points for C1 (`GEONAMEID 559800`, longitude 114.13456, latitude 22.28449), hospital points for Queen Mary (longitude 114.13117, latitude 22.2704), original network XYZ/Gradient data, and the two relevant provider dictionaries.

- [Initial five-point sample](../precomputed/docs/hku_c1_pokfulam_gradient_sample.json): first sampled road-side point about 10.3 m from C1's 2D map point; four intervals covering 13.2 m. Two had equal endpoint heights with positive raw gradients; two had decreases. Equal-height signs were left unassigned. Two links have wheelchair-barrier flags. It was a slope demonstration, not a validated accessible route.
- [Farther sample](../precomputed/docs/hku_c1_pokfulam_gradient_farther_sample.json): five existing vertices across source path `250002139`, horizontal length 228.157334 m, supplied gradient `0.05129629` radians. Heights toward Queen Mary: **62.7974, 65.3262, 68.7189, 71.1355, 74.5113 m above HKPD**. All four sampled comparisons rise, so all use `+0.05129629`; reverse travel uses the negative value. The first point is about 117.8 m from C1 in straight-line position; that location offset is not the ranking metric.

The farther points belong to one source polyline. The same magnitude is therefore retained for every sampled interval; it was not recalculated from the sampled height difference. Full coordinates, source hashes and intervals are in the JSON/CSV artifacts. The initial example script is [work/examples/hku_c1_pokfulam_gradient_demo.py](../examples/hku_c1_pokfulam_gradient_demo.py).

## 12. Documents to consult next

1. This handoff for the latest user decisions and remaining choices.
2. [Step 1 human-readable plan](step_1/step_1_implementation_human_readable.md) for detailed explanations and checklists. Its older resolution entries must be interpreted with the later accepted assumptions above.
3. [Step 1 technical plan](step_1/step_1_implementation_plan.md) for implementation structure.
4. [Original estate-ranking design](estate_ranking_design.md) for the overall pipeline; later decisions here override earlier suggestions, notably the hospital distance model and ignored schedules.
5. [Earlier chat export](whole_chat_export.md) for historical context; it does not contain all decisions made after it was prepared.
6. [Provider-document review](../precomputed/docs/step_1_provider_documentation_review.md), [latest validation report](../precomputed/outputs/current/validation_report.md), and [MTR review CSV](../precomputed/outputs/current/mtr_match_review.csv) for evidence and snapshot details.

When a future decision is made, update this handoff and affected checklist items. Record whether the change is a modelling assumption, a source-confirmed fact, or implemented behaviour. Keep unresolved items unchecked and do not claim that a discussion or demonstration completed production routing.
