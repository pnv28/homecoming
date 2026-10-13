# Estate-to-transit accessibility: data assessment and proposed ranking model

Prepared 12 October 2026 from the files in this project folder.

**Later source update:** An official open iGeoCom download now supplies 611 railway access points, including named exits and barrier-free subcategories. See [the coordinate-source investigation](mtr_coordinate_sources.md). References below to missing exit coordinates describe the original MTR CSV, whose coordinate column remains empty; the new dataset provides a separate source for reconciliation.

## 1. Recommendation

Build a **user-specific, constrained pedestrian routing system**. First determine whether a continuous route meets the person's mobility requirements; then rank the routes that remain by distance, effort, crossing difficulty, reliance on lifts, and other preferences.

The supplied data is a strong foundation for this. Its most valuable component is the 3D pedestrian network: it contains 465,892 route segments with feature types, gradients, wheelchair barrier indicators, entrance-access indicators, and access schedules. This makes it possible to investigate actual journeys rather than simply compare distances between points.

However, the files alone cannot establish that every estate-to-transit journey is independently usable today. Estate entrance positions, MTR exit coordinates, continuous platform access, bus boarding conditions, and current lift availability need further work. The system should distinguish **supported by checked data**, **conditionally reachable**, **not reachable under the selected constraints**, and **insufficient evidence**.

The key design principle is that an impossible segment cannot be compensated for by a good score elsewhere. A short staircase is still a barrier to a wheelchair user even if the rest of the route is flat and covered.

This report proposes a future routing program. The accompanying Python script audits the data; it does not yet calculate or certify accessible routes.

## 2. What was actually inspected

I read all supplied JSON and CSV files, extracted the metadata PDF, and inspected every layer in the zipped File Geodatabase using Python in `.venv`. I also recovered the geodatabase's embedded coded-value domains to interpret its numeric fields. The machine-readable results are in `audit_summary.json`.

| Supplied file | Observed contents | Proposed role |
|---|---|---|
| `prh-estates (1).json` | 244 estates, all with map latitude/longitude | Estate search, approximate origins, district summaries, links to estate access documents |
| `JSON_BUS.json` | 56,209 route-stop records; 4,488 distinct stop IDs | Bus stop locations, routes, direction/sequence, boarding-policy information after code verification |
| `mtr_lines_and_stations.csv` | 273 rows, including 3 entirely blank rows; 100 distinct nonblank station IDs | Station identifiers, names, lines, directions and sequence |
| `barrier_free_facilities.csv` | 3,564 facility records for 99 station numbers | Station facilities and text descriptions of accessible entrances |
| `barrier_free_facility_category.csv` | 36 facility definitions | Translate facility keys into meaningful access requirements |
| `3D_Pedestrian_Network_FGDB.zip` | 465,892 3D route features plus 7 related tables | Main routing graph, barriers, vertical connections, schedules and terminal associations |
| Metadata PDF | Coverage, reference system, update information, stated coordinate accuracy | Provenance, coordinate handling and limits on interpretation |
| `facility-hosp.json` | 44 hospital records with coordinates and A&E indicators | Optional later destination analysis; not necessary for the initial transit-access task |

Counts describe these local snapshots, not a guarantee of current territory-wide inventory. A station ID is also not necessarily equivalent to one unique physical station complex.

### 2.1 Estate data: useful starting points, incomplete first metres

Estate entries contain multilingual names, districts, regions, map coordinates, block names/counts, intake years and descriptive management information. There are 244 unique English estate names. None are missing map coordinates. I found barrier-free document links in 199 entries.

Use these records to let the user choose an estate, locate its general area and find supplementary access documentation. The linked estate PDFs could be particularly useful for identifying ramps, lifts and block access, but their contents are not included in this audit and have not been validated.

An estate map pin should not be treated as a verified accessible entrance. A person starting at one block may face a different journey from someone at another block. Snapping the map pin directly to a nearby road can omit an internal staircase or invent a connection through a wall.

For an initial prototype, label the result as an **estate map-point estimate**. For useful personal directions, collect block/entrance origins and verify their connectors to the pedestrian network. If the user supplies a starting point, its connector still needs validation.

The rental-flat field is descriptive text, sometimes including an as-of date. It can support later estate-level planning after parsing, but flat counts do not measure the number of residents with mobility needs.

### 2.2 Bus data: route memberships must be separated from stops

`JSON_BUS.json` is a GeoJSON FeatureCollection of point features. Coordinates are stored as longitude, latitude. Properties include `stopId`, names, operator, route identifiers, `routeSeq`, `stopSeq`, `stopPickDrop`, route endpoints, fare, route journey time and `lastUpdateDate`.

The 56,209 records are not 56,209 physical stops. They represent repeated stop appearances in different route/direction/service contexts. There are 4,488 distinct stop IDs and 4,487 distinct coordinate pairs. No stop ID has multiple coordinates in this snapshot, but two IDs share a coordinate pair.

Create a physical-stop table keyed by the source stop ID, and a separate route-stop table preserving every membership. Check whether the publisher guarantees ID uniqueness across operators before combining future sources. Do not merge stops purely because they have identical coordinates: different platforms or directions may share a mapped point.

For a useful journey, retain the bus direction and boarding rules. Reaching a nearby alighting-only stop would not meet a request to board a bus. `stopPickDrop` has values 0, 1, 2 and 3 in this file; verify their official meanings before using them as filters. I have not assumed a decoding.

The records' update dates range from 6 May 2020 to 29 September 2026. These dates are provenance signals; an old route-level date does not by itself establish that a physical stop is obsolete.

The file has no explicit wheelchair boarding, kerb height, pavement width, ramp deployment clearance or vehicle accessibility fields. Therefore report **pedestrian access to a stop** separately from **ability to board the required service**. `journeyTime` is a route attribute, not the walking time from an estate, a current waiting time, or necessarily an arbitrary stop-to-stop travel time.

### 2.3 MTR station and facility files: valuable but not a complete entrance map

Station rows repeat stations across lines and directions, as expected. Remove the three blank rows and preserve line memberships in a separate table rather than counting every row as a station.

The facility table joins to the category dictionary through `Key = Item_Code`. A provisional station join is `Station_No = Station ID`, represented consistently as strings. It needs reconciliation:

- Facility station numbers `70` and `888` have no exact counterpart in the supplied line file.
- Station IDs `44`, `45` and `46` have no exact counterpart in the facility file; the line file identifies them as Airport Express Hong Kong, Kowloon and Tsing Yi entries. Investigate whether facilities are represented under other IDs for the same complexes before treating them as missing access.
- There are no duplicate `(Station_No, Key)` pairs.
- Every `Exit_Coordinate_X_Y` value is empty: **zero entrance coordinate records**.

Important facility definitions include:

| Keys | Meaning | Use |
|---|---|---|
| `AJ1`, `AJ2` | Same-level access, ramp | Identify possible step-free entry arrangements |
| `AJ3`, `AJ4` | Unpaid-area lift, including non-MTR-managed lift | Street-to-concourse access candidates; management and availability matter |
| `AJ5`, `AJ7`, `AJ9` | Stair lifts and vertical lifting platforms | Check equipment suitability, operating rules and assistance requirements |
| `AJ6` | Wheelchair aid | Assistance-dependent access; not automatic proof of independent access |
| `AJ8` | Paid-area lift | Evidence relevant to concourse/platform movement |
| `MJ1`, `MJ2` | Wide gates; portable/movable ramps | Passage and boarding support |
| `MJ4`–`MJ6` | Accessible toilets in different areas | Optional user requirements; staff-area access may need assistance |
| `MJ7` | Accessible-car service arranged through staff | A separate access arrangement rather than an ordinary walking connector |
| `MJ8` | Powered-wheelchair charging socket | Optional destination preference |

`AJTextEn` and `AJTextZh` identify exits or access arrangements in free text. Parse them into provisional entrance records and retain the original text for review. A station-level `Y` does not prove that the nearest entrance has that facility or that every platform is reachable from it. A station-level `N` applies to that particular facility category, not to all possible access arrangements.

Use the pedestrian network's MTR terminal associations to find candidate station access areas, then reconcile those with entrance text and verified coordinates. Treat unclear matches as unresolved. Do not silently manufacture exit locations from station centres.

### 2.4 The 3D pedestrian network: the central dataset

The geodatabase contains:

| Layer/table | Records | Role |
|---|---:|---|
| `PedestrianRoute` | 465,892 | 3D line geometry and route attributes |
| `PedRouteRelTerminalPoly` | 669 | Terminal IDs, names and types |
| `PedRouteRelFloorPoly` | 2,596 | Floor/building associations |
| `PedRouteRelBldgPoly` | 9,084 | Building IDs and names |
| `PedRouteRelSitePoly` | 3,363 | Site IDs, names and types |
| `PedRouteRelDistancePost` | 3,431 | Trail/distance-post associations |
| `AccessTime` | 2,413 | Whether linked schedules represent opening or closing hours |
| `AccessTimeDetails` | 3,483 | Day codes and time intervals |

Despite several names ending in `Poly`, the related layers in this archive are **nonspatial tables**, not supplied polygon geometries. Their identifiers can join to route features; they cannot directly provide terminal boundaries or entrances.

The main route layer is `MultiLineString Z`. Its horizontal reference system is Hong Kong 1980 Grid, EPSG:2326, with HKPD heights. Transform longitude/latitude source points into the network's horizontal CRS before measuring metres or snapping. Use an explicit longitude/latitude axis convention and preserve Z/floor information separately.

Notable observed attributes and counts:

- 440,108 outdoor and 25,784 indoor segments.
- 22,012 staircase segments, 1,773 escalators, 1,911 lifts, 3,146 ramps and 5 stair lifts.
- Crossing types distinguish signalized, zebra, cautionary and other crossings.
- `WheelchairBarrier = 1` on 34,928 segments; `2` on 430,964.
- `WheelchairAccess = 1` on 4,177 segments; `2` on 461,715.
- 46,276 segments have a non-null `AccessTimeID`.
- 10,485 segments have a non-null `TerminalID`.
- 26 segments have `Enabled = 2`, the disabled code.
- 80,043 segments are covered; 381,005 noncovered; 4,844 unclassified.
- The terminal table includes 99 MTR station entries and 68 Light Rail entries, alongside other terminal types. These are not automatically identical to the IDs/counts in the MTR CSV.

The embedded domain for `WheelchairAccess` explicitly describes accessible entrances connecting to facilities, buildings or sites. **Do not require `WheelchairAccess = 1` on every route edge.** That would wrongly remove ordinary walkways.

For `WheelchairBarrier`, the domain names 1 as True and 2 as False. Its description is awkwardly worded. Observed cross-tabulation strongly supports interpreting 1 as barrier present: 21,645 staircase segments and 1,742 escalators carry that value, while all 1,911 lifts carry 2. Confirm intended semantics against the authoritative dictionary before production deployment.

There are also 367 staircase segments with barrier value 2. A strict step-free profile must still exclude them based on feature type. Agreement between fields increases confidence; disagreement should produce a review flag rather than a convenient interpretation.

`Gradient` is populated for every segment. Raw median, 90th percentile and maximum are approximately 0.01258, 0.15176 and 1.57065. The last value is close to π/2, suggesting an angular representation. The local metadata PDF does not establish its units or signed-direction semantics. **Verify these before converting to percentage slope.** If the field is an angle in radians, grade is `tan(angle)`, and percent grade is `100*tan(angle)`, not `100*angle`. Near-vertical lift edges must be handled as equipment transitions, not steep walkways.

The supplied metadata states approximately 1 m XY accuracy and 2 m Z accuracy. This is useful for network mapping but cannot resolve centimetre-scale kerbs or precisely measure short-ramp gradients. Prefer the supplied gradient after verifying its definition; do not turn noisy height differences into authoritative ramp measurements.

The metadata identifies a 16 September 2026 revision and quarterly maintenance, while some distribution filenames refer to June 2026. Preserve both observations and verify which release the actual archive represents rather than assigning its contents a date solely from the metadata page.

The official [Lands Department open-data page](https://www.landsd.gov.hk/en/spatial-data/open-data.html) describes wheelchair accessibility and obstacle attributes in this network. The underlying [government dataset listing](https://data.gov.hk/en-data/dataset/hk-landsd-openmap-3d-pedestrian-network) is the appropriate starting point for authoritative specifications and updates. These sources support the dataset's intended use; local counts and defects above come from the supplied files.

## 3. Precisely define what the program answers

The input should be:

`origin + mobility profile + departure time + target type + optional required service/platform`.

Provide three separately labelled answers:

1. **Geographically nearest:** straight-line proximity. Useful as context and for searching candidates.
2. **Nearest reachable:** shortest valid pedestrian route under the selected constraints.
3. **Recommended reachable:** lowest effort/preference cost among valid routes.

The nearest reachable option may differ from the recommended one. A 600 m flat route can be preferable to a 450 m route with a difficult incline and several crossings.

For MTR, distinguish reaching an entrance, entering the concourse, reaching a required platform, and boarding. For buses, distinguish reaching the stop from boarding a particular service. The current files support investigation of the pedestrian portion most directly. Do not present entrance reachability as proof of boarding access.

If a user only asks for transit nearby, return MTR and bus results separately so unlike services are easy to compare. If they specify a destination or bus route, filter for relevant services: a nearby stop serving the wrong direction is not useful.

## 4. Mobility parameters

Use named profiles as editable defaults, rather than treating everyone with mobility issues identically.

| Parameter | Reason | Current support |
|---|---|---|
| Require step-free travel | Exclude stairs/escalators for wheelchair or step-free users | Feature types plus barrier flags |
| Maximum uphill/downhill grade | Climbing effort and descent control differ | Gradient present; units/direction need verification |
| Maximum total distance/time | Personal endurance limit | Route lengths; time requires a calibrated model |
| Maximum continuous movement before rest | Fatigue may depend on uninterrupted travel | Rest locations are missing |
| Minimum clear width | Device clearance and passing room | Missing |
| Maximum kerb/step height | Small discontinuities can be decisive | Missing |
| Allow lifts / lifting platforms / assistance | Equipment dependence and autonomy preferences | Some feature/facility evidence; operating details incomplete |
| Avoid certain crossings | Crossing difficulty varies by person | Crossing categories present; timing/kerbs incomplete |
| Prefer covered routes | Rain and heat exposure | Coverage categories present |
| Strict handling of unknowns | Determines whether uncertain connectors can be suggested | Requires explicit evidence tracking |
| Need toilet/charging access | Some users have additional requirements | Station categories present; locations/hours need checks |

Possible starting profiles include manual wheelchair, powered wheelchair, walking aid, and limited endurance. Let users set the underlying capabilities. An assistant's presence should be explicit rather than inferred.

Numeric grade, speed and distance defaults should be labelled **prototype assumptions** until calibrated with intended users. Device limits and individual abilities differ. This report does not treat a chosen threshold as a building-standard or medical definition of accessibility.

## 5. Mathematical model

### 5.1 Model the real pedestrian connections

Represent the network as a directed multigraph `G = (V, E)`. Nodes represent valid connections at compatible levels; edges represent walkways and equipment transitions. Preserve parallel alternatives such as a staircase and a nearby lift.

Do not connect lines merely because their XY projections intersect: a footbridge can cross a road without connecting to it. Split multipart geometry carefully, preserve direction, and use endpoints, Z, floors and building/terminal relationships when constructing topology. Reconcile small genuine gaps with a documented tolerance and review, rather than blanket snapping.

Connect an origin or target to a nearby edge only through a valid approach. Split the edge at the access point where appropriate. A short artificial straight line across a road, wall or inaccessible level is not a valid connector.

### 5.2 Apply hard constraints first

Define `F(e, u, t)` as whether edge `e` can be used by profile `u` at its expected traversal time `t`. Requirements include enabled/public access, permissible direction, permitted feature type, no disallowed barrier, acceptable grade for walkway edges, and an available access schedule. Add verified width/kerb and equipment restrictions when those become available.

If a required condition is unknown, mark the edge uncertain. In strict mode, exclude it from supported routes. An exploratory mode may show a conditional route with its unresolved requirements clearly identified.

For a route `P`, require:

`F(e, u, arrival_time(e)) = true for every edge e in P`.

Also require route-level distance/time limits. If continuous-distance or rest requirements are enabled, track distance since the last verified rest opportunity; ordinary edge filtering alone cannot enforce that constraint.

Access schedules require a join through `AccessTimeID`. `AccessTimeType = OPEN` and `CLOSE` have opposite meanings. Decode day groups, public holidays, overnight intervals and HHMM values correctly: 700 means 07:00, not 700 minutes. Evaluate availability when the user reaches the edge and ensure the entire traversal is allowed. A missing schedule does not prove unrestricted access.

### 5.3 Rank usable routes with an additive cost

A practical first model expresses burden in **equivalent metres**:

`C(P, u) = Σe [d_e * (1 + α_u * φ(g_e)) + β_u * x_e + γ_u * lift_e + δ_u * uncovered_metres_e]`.

Here:

- `d_e` is the segment's travel length in metres, after checking the meaning of `Shape_Length` against geometry.
- `g_e` is the verified grade; equipment edges use a separate cost model.
- `φ(g_e) = max(0, |g_e| - g_comfort,u) / g_scale,u` is one interpretable slope-penalty option, with positive `g_scale,u`.
- `x_e` is a crossing burden indicator based on type; group contiguous segments belonging to one crossing to avoid counting it several times.
- `lift_e` counts an equipment transition, grouped so one lift is not charged multiple times.
- `uncovered_metres_e` is the exposed part of the edge; unclassified coverage remains unknown.
- All coefficients are nonnegative and user-adjustable. `α` and `δ` are dimensionless; `β` and `γ` convert events into equivalent metres.

The grade term can later distinguish ascent and descent after direction semantics are verified. Lift waiting time can be represented directly in a calibrated time model instead of a preference penalty. Do not infer it from vertical line length alone.

This model is useful because it is explainable, its costs can be optimized by standard graph algorithms, and users can understand why a slightly longer route ranks higher. Report actual metres and estimated minutes alongside equivalent burden; never label the cost itself as walking distance.

Use a bounded display score only if the interface needs one:

`Score(P, u) = 100 / (1 + C(P, u) / C_reference,u)`.

`C_reference,u` is a fixed positive, documented reference burden for the selected profile, for example 500 equivalent metres in a prototype. Higher scores mean lower burden. This is a monotonic transformation of the routing cost, **not a probability of success or an accessibility certification**. Infeasible routes receive a blocked status; unknown routes receive an evidence status rather than an apparently reassuring numeric score.

Avoid normalizing against whichever stations happen to be in the current candidate list: adding an irrelevant destination should not change an existing route's score.

### 5.4 Illustrative comparison

The following is an invented example explaining the mathematics, not a result for any supplied estate. Assume flat routes, crossing cost 30 equivalent metres per event, and lift cost 80 equivalent metres per transition.

| Route | Distance | Stairs | Crossings | Lifts | Result for step-free profile |
|---|---:|---|---:|---:|---|
| A | 180 m | Yes | 0 | 0 | Excluded before ranking |
| B | 420 m | No | 1 | 0 | Cost 450; score 52.6 with reference 500 |
| C | 350 m | No | 2 | 1 | Cost 490; score 50.5 with reference 500 |

Route C is shorter than B, but B ranks higher under these preferences. A user comfortable with lifts and crossings can reduce those penalties, changing the recommendation. Neither choice is universally correct.

### 5.5 Keep uncertainty separate

Store provenance, verification dates and unresolved attributes for each edge and connector. Route explanations should identify critical unknowns, especially at the origin, terminal entrance and boarding point.

Do not average evidence across a route: one unknown entrance can invalidate an otherwise well-documented journey. A useful summary is the weakest critical evidence state, accompanied by the number and location of unresolved checks.

For sensitivity analysis, calculate a best plausible case and a conservative case for uncertain sections. If no path is found, distinguish a confirmed constraint conflict from network disconnection, missing connectors or insufficient evidence. Say **no route found in this data under these constraints**, rather than claiming physical impossibility without supporting evidence.

## 6. Python architecture and algorithm choices

Use separate ingestion, normalization, graph, profile, routing and explanation components. Suggested normalized tables are estates, origins/connectors, stops, route-stop memberships, stations, line memberships, entrances, station facilities, route edges, access schedules and verification records.

Keep a stable source identifier on every normalized record. Station and network terminal IDs are different identifier systems: join through a reviewed mapping table. Name matching can generate candidates, but spelling differences and station complexes make automatic name joins unreliable.

Suitable Python tools are `pyogrio` for the geodatabase, `shapely` for geometry, `pyproj` for CRS transformations, and a graph package such as `networkx` for a local prototype. These routing libraries beyond the audit requirements have not yet been installed. Profile a city-wide implementation before choosing its final graph backend; several hundred thousand features can consume substantial memory once converted into Python objects.

Use Dijkstra for additive nonnegative costs after filtering edges. For route-level resource constraints such as total distance plus effort minimization, retain multiple nondominated labels or use another constrained shortest-path algorithm. Simply finding the lowest-cost route and rejecting it when too long can miss a shorter, slightly higher-cost feasible route.

For time-dependent schedules, use time-aware search with documented waiting rules. For an early pilot, routes can instead be computed within a verified interval where access remains constant; disclose that simplification. Full-day routing must handle closures encountered partway through a journey.

Do not inspect only the three closest stations or stops: nearby targets can all be inaccessible. Search all compatible targets in the bounded reachable graph, or expand candidate searches with an explicit termination bound. For the nearest-distance objective, geographic distance provides a lower bound; it does not itself establish route validity.

For all-estate planning, a reverse multi-source search from validated entrances can efficiently find nearest targets for a fixed profile and stable time scenario. Personalized burden, assistance requirements and changing schedules may need separate computations.

Return several useful alternatives: shortest reachable, lowest burden, and an option avoiding lifts or difficult crossings when one exists. Avoid near-identical route variants.

Every result should include destination and entrance/stop ID, service direction where relevant, route geometry, distance, estimated time and assumptions, maximum grade where verified, crossing/equipment counts, access conditions, and a plain-language reason for its ranking.

## 7. What a simple proximity query already shows

The audit computed nearest bus points for five estate map pins using haversine distance. Examples from the actual files:

| Estate | Nearest stop point | Straight-line distance |
|---|---|---:|
| Tak Long Estate | Kai Tak – Victoria Skye, Muk On Street; ID 13325 | 161.5 m |
| Kai Ching Estate | KAI TAK (KAI CHING ESTATE); ID 13106 | 112.2 m |
| Choi Fook Estate | CHOI FOOK; ID 13034 | 67.5 m |

These demonstrate that approximate geographic lookup is readily achievable. They do not establish usable paths, correct boarding directions, or wheelchair access. Names shown are taken from one route-stop record; a physical stop may have naming variants across memberships.

No actual estate-to-MTR or estate-to-bus accessible route was computed in this assessment. Numerical ranking examples in section 5 are illustrative.

## 8. Missing information, in priority order

| Gap | Why it matters | Next action |
|---|---|---|
| Verified estate block/entrance connectors | The first part of the journey can contain decisive barriers | Review estate barrier-free documents and check entrances |
| Accessible MTR entrance coordinates and terminal mapping | CSV coordinates are entirely empty | Reconcile network associations, facility text and authoritative entrance maps |
| Street-to-concourse-to-platform chain | Reaching the station is not reaching the train | Validate platform-specific access and staff-dependent arrangements |
| Kerbs, clear widths, surfaces and cross slopes | A mapped walkway can still be unusable | Add surveys or authoritative detailed attributes |
| Bus-stop approach and boarding compatibility | Reaching a stop is not boarding a service | Verify kerb/clearance conditions and operator vehicle/ramp policies |
| Equipment availability and temporary works | Static lift data can become unusable | Add verified status feeds where available and dated reports |
| Calibrated speed/effort parameters | Generic walking assumptions can mislead | Pilot with intended users and record actual journeys |
| Rest opportunities and crossing timing | Endurance and safe crossing depend on them | Add verified rest locations and crossing details |

Hospital points can later extend the project to hospital access, but they should not distract from fixing origin and transit access first. An A&E indicator is not evidence of an accessible hospital entrance.

## 9. Validation and implementation sequence

Begin with a small set of estates representing different districts and terrain, including estates with internal level changes. Audit their origins and nearby transit entrances with intended users or accessibility assessors.

Then:

1. Normalize data, reconcile IDs, verify code meanings and gradient units, and record snapshot dates.
2. Build and inspect graph topology, including floors, lifts, bridges and connector placement.
3. Implement conservative step-free routing with evidence states and explainable distance results.
4. Add calibrated slope/effort and preference ranking, followed by schedules and service-specific boarding checks.
5. Expand coverage once the pilot's failures have been understood and corrected.

Meaningful validation includes disconnected networks, a short staircase versus a longer ramp, an elevated route crossing a ground route, closed passages, reverse directions, and missing entrance connectors. Include the observed staircase/barrier disagreement as a regression case. Test that assistance-dependent equipment is excluded when assistance is not permitted and that an arrival near closing time is handled correctly.

Compare predictions against inspected journeys. Track the rate of routes labelled usable that prove unusable, missed usable routes, distance/time errors, connector failures and rank sensitivity to user parameters. Optimizing a mathematically tidy score is insufficient if the route chain is wrong.

For estate-level planning, summarize the distribution across verified origins: for example the fraction of sampled block entrances with a supported route to a transit target within a specified distance. Report the denominator and distinguish missing evidence from confirmed lack of access. Do not derive an estate-wide score from one central map pin or assume flat counts represent mobility-impaired populations.

## 10. Reproducing this assessment

The audit uses the original files without modifying them. From the project directory:

```sh
python3 -m venv .venv
.venv/bin/pip install -r analysis/requirements.txt
.venv/bin/python analysis/audit_data.py
```

Outputs are `analysis/audit_summary.json` and `analysis/metadata_extracted.txt`. The archive is extracted into a temporary directory for inspection. Dependencies are pinned to the versions used here. This environment used Python 3.9 on macOS; other systems may require compatible package versions.

The proposed constrained graph model is a good fit because it directly represents the physical route, separates barriers from preferences, adapts to different users, and can explain each recommendation. The immediate next step is a validated pilot with reliable origin/entrance connectors—not assigning accessibility scores to every estate before those connections are established.
