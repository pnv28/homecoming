# Project context, agreed instructions, and agent handoff

Last updated: 2026-10-16 16:22:13 HKT (UTC+08:00)

## Read this first

This file records the user's decisions and the work completed in this conversation. A future agent should read it before planning, implementing, or interpreting the estate-ranking algorithm.

**Latest user instructions take precedence. For pedestrian graph construction and route costs, the current [Step 2 plan](step_2/step_2_plan.md) supersedes older statements in this handoff and earlier design documents. This handoff records those current decisions; it takes precedence over older discussion and proposed defaults for other project matters.** Earlier design documents and the resolution register contain some questions that the user has since settled through explicit modelling assumptions. Historical validation reports describe their saved data snapshot; do not rewrite them to imply that later assumptions were publisher-confirmed facts.

Distinguish these statuses:

- **Agreed instruction:** follow it; do not repeatedly ask the user to confirm it.
- **Provider-confirmed fact:** supported by a supplied dictionary, metadata, or checked source content.
- **Accepted assumption:** the user deliberately accepts it for this model, even when source documentation is incomplete.
- **Open decision or suggested implementation:** do not present it as agreed or completed.

**Completed request — 16 October 2026:** rebuilt all of Steps 2 and 3 from unchanged frozen Step 1 **`20261014T090829Z-20d0139c`**. The user confirmed **6 seconds per metre uphill / 2 seconds per metre downhill**, also for wheelchair-eligible paths as an explicit approximation. All existing direction, Enabled, wheelchair and equipment restrictions remain. No commit or push is requested or performed.

**Selected verified pair:** Step 2 **`20261016T075559Z-119a5636`** and Step 3 **`20261016T080509Z-4c604c82`**, recorded in [the atomic pair registry](../precomputed/outputs/rebuild/current.json). Public readers use this registry, and Step 3 pins its exact upstream run. Both candidates passed before selection; publication rollback is tested. Older successful runs remain retained and inspectable by explicit directory.

**Current results:** Step 2 has **397,225 nodes / 466,406 pieces**, preserving all **465,892** original source rows and **465,861 general / 430,496 wheelchair eligible sources**. Reviewed fallback covers **26 source records / 27 intervals / 26 physical pieces**; original profile evidence is byte-identical to the previous run, all original source/node fields match, and every healthy directional time is unchanged. Step 3 preserves all **10,163 source points**, with **20,814 primary + 20,238 baseline attachment records**, and **406,561 nodes / 475,742 pieces**. Both stages save six graphs: four primary mode/metric graphs and two baseline time graphs excluding estimates. **134 tests pass**, plus full-data spatial/null/matrix/profile reopen checks, source-ID lift/endpoint regressions, saved-artifact/code/upstream hashes and public-reader checks. Step 2 runtime: **543.38 seconds**, peak **1,990.672 MiB**; Step 3 runtime: **430.851 seconds**.

**Interpretation:** fallback is now implemented in selected primary time graphs. Baseline graphs retain original exclusions; original geometry, provider gradients and failure diagnostics are preserved separately. This does not repair source defects or establish measured wheelchair speeds. Actual estate subcost caching and journey comparison reporting remain Step 4; final score combination remains undecided. See [Step 2 implementation](step_2/step_2_implementation.md), [Step 3 implementation](step_3/step_3_implementation.md), [test evidence](../precomputed/docs/rebuild_test_report.json) and [preservation audit](../precomputed/docs/rebuild_source_preservation.json).

**Attachment coverage and warnings:** all eligible points attach: MTR **598 general / 276 wheelchair**, buses **8,848 general / 4,130 wheelchair**, all 244 estates and 44 hospitals for applicable metrics. These are attachment counts, not proof of estate-to-target reachability. Per time scenario, **36 general / 34 wheelchair bus records** exceed 50 m; maxima **5,209.271 m / 5,161.979 m**. Flagged straight connectors follow the accepted expanded-search assumption and may not represent actual walkable passages. Unknown entrance/level evidence remains visible.

**Step 3 connector assumptions for the rebuild:** one closest suitable connection per point/mode/metric. Search ordinary outdoor paths within **200 m** for estates/hospitals/MTR and **50 m** for buses, then ordinary indoor paths within that threshold as a flagged fallback. If neither qualifies, allow a farther suitable connection using the expanded-search rules in the revised Step 3 plan; record its distance, threshold and reason. These are warning/search thresholds, not distance-only rejection limits. This supersedes the hard limits in the older saved Step 3 run and is implemented in the selected 16 October pair. Straight horizontal connectors count distance and flat Tobler time. Source-point heights remain unknown; only derived attachment points carry interpolated original HKPD height. Unknown levels, ties, near alternative levels, indoor fallback and non-bus connectors over 50 m are recorded. No automatic attachment to bridges, tunnels, stairs or equipment interiors. Estate terminals depart only, destination terminals arrive only (including lift states); terminals cannot form network shortcuts. Every excluded/unattached record remains visible. Attachment does not establish estate-to-target reachability; hospital preferences, subcosts and ranking remain later work.

**Historical cleanup result — 14 October:** cleaned old build artifacts. Removed the superseded Step 1 run `20261013T121410Z-c823aaf9`, Step 2 runs `20261014T092300Z-399fee39` / `20261014T101626Z-eaef8030`, and 14 failed staging directories, reclaiming **3.866 GiB**. Keep the selected Step 2 run `20261014T105436Z-8fe534aa`, its frozen Step 1 input `20261014T090829Z-20d0139c`, the active MTR output, original sources and verified network extraction. Compact historical reports/manifests are retained under `precomputed/history/`. This explicit cleanup request supersedes older instructions to retain complete historical builds; older test reports describe checks performed before cleanup. Do not restore removed bulky outputs merely to satisfy those historical statements. No commit or push requested. See [the cleanup inventory](../precomputed/history/cleanup_20261014.json).

**Historical post-cleanup verification:** all **30 retained Step 2 artifact hashes**, all **seven frozen Step 1 hashes**, selected links and archived metadata hashes passed verification. The public graph reader and the real source-ID lift/endpoint regressions also passed after deletion. Both staging directories are empty. The cleanup verification is recorded in the linked inventory; no build was regenerated for cleanup.

**Historical completed autonomous audit — 14 October:** investigated and fixed the remaining Step 2 cluster/time flags using parallel agents. The agent performed that work without committing or pushing. The completed audit fixes qualifying original-endpoint preference, exposes healthy intervals using isolated cost-boundary subdivisions, and fixes validation of entirely unavailable time columns. **89 tests pass**. New successful run **`20261014T105436Z-8fe534aa`** is selected locally after full save/reopen, source/routing audit and source-ID regression checks. Original geometry, attributes, gradients, samples, policy and frozen Step 1 input remain unchanged. Read [the autonomous audit](step_2/step_2_implementation.md#autonomous-audit--endpoint-preference-and-invalid-interval-boundaries) for evidence and remaining limitations.

**Superseding Step 2 decisions — 14 October 2026:** both modes use the same standard Tobler assumption on healthy eligible non-lift intervals, including moving equipment and stair lifts; the reviewed failures now use Section 5.6. The earlier deferral of wheelchair speed and other equipment timing is superseded; neither is an open decision for this model. Exclude `Enabled=false` from both modes. Use original `PedestrianRouteID` as lift identity: charge 30 seconds on entry; continuing pieces of the same identity adds zero; entering a different lift charges another 30 seconds; traversing a non-lift resets identity. Keep hospital costs in horizontal metres. Inferred junctions require horizontal separation ≤0.10 m and height separation ≤0.025 m, with every cluster member pair satisfying the rule. This height connection tolerance does not change exact equality in gradient sampling or establish source elevation accuracy. Access schedules remain ignored.

**Historical implementation update — 14 October (superseded by the selected pair above):** Step 1 remains the successful frozen run **`20261014T090829Z-20d0139c`**, with all 476,153 spatial records, zero errors and 14 retained warning groups. It preserves both Castle Peak Hospital versions and selects the site record amended 13 July 2026. Do not rebuild Step 1 merely because Step 2 changes. SciPy **1.13.1** was installed with approval in the local `.venv`; the autonomous audit installed nothing. Current Step 2 **`20261014T105436Z-8fe534aa`** contains **397,225 nodes / 466,406 pieces**, retaining 465,861 general / 430,496 wheelchair eligible sources. Runtime: 315.966 seconds; peak process memory: 2,212.844 MiB. Reports and manifests for the original run `20261014T092300Z-399fee39` and first repair `20261014T101626Z-eaef8030` remain unchanged under `precomputed/history/step_2/`; their superseded bulk artifacts were removed at the user's request.

**Historical autonomous audit result — 14 October:** explicitly include qualifying original receiving endpoints before checking traversal visits, then prefer an endpoint only after ruling out separate visits. This repairs the artificial height-conflict cluster for `250015300` / `250011610` without relaxing 0.10 m / 0.025 m limits. All 11 remaining rejected merge clusters already connect their eligible endpoints through original paths; one is wholly excluded in wheelchair mode. Add 29 single-source cost-boundary nodes after junction decisions, preserving 29 healthy pieces / 766.558511 m generally and 20 pieces / 362.718808 m for wheelchair routing, without adding cross-path junctions or making invalid gaps traversable. The 26 source-total time flags remain accurate (25 vertical, one numeric overflow), while 58 general / 40 wheelchair healthy directed piece costs are restored. Four invalid pieces per mode still have no finite endpoint-to-endpoint time route; source IDs and actual alternate-route evidence are recorded in the audit. Do not invent replacement heights, gradients or costs.

**Historical regression repair result — 14 October:** joint height/XY projection fixes both reported lift attachments; each is now a 30-second forward/reverse lift use in both reopened time graphs. Repeated visits are separated by intervening traversal geometry rather than vertex-index gaps, while ordinary bends/shared vertices remain valid. Healthy pieces use local interval costs/statuses and remain routable beside invalid intervals. Original source attributes, XYZ, gradients, samples and source diagnostics are unchanged. Active weak component counts are general distance **507**, general time **510**, wheelchair distance **8255**, wheelchair time **8257**. See [the regression review](step_2/step_2_implementation.md#regression-repair--joint-projections-visits-and-local-piece-costs) for counts, remaining ambiguities and unavailable time directions.

**Warning-review decisions — 14 October 2026:** accept the existing **276 mapped mobility access points as the complete wheelchair MTR target pool** for this model. These are entrances/access points, not stations; the 335 points without mobility evidence remain general-mode candidates and outside wheelchair targets. Accept the three ramp/lift/same-level description differences as mobility access points without requiring exact equipment reconciliation. Select the Castle Peak Hospital site version with the latest `LastAmendmentDate` (**13 July 2026**, SiteID 1503020249), preserving both original records. Ignore missing terminal, floor and building references as investigation tasks because they are non-blocking Step 1 warnings; preserve their paths, IDs and diagnostics. Missing site and distance-post/path references were not included in that instruction. Normal geometry, height, direction and connectivity checks still apply. The rebuilt Step 1 snapshot and current `routing_policy.json` now include these decisions and the canonical site selection. Earlier reports retain the policies and findings recorded at their original build time; superseded full snapshots were removed during the requested cleanup.

**Terminology:** use **Allow** for routing eligibility, **Exclude** for a routing prohibition in the selected mode, and **Preserve** for keeping source data even when routing excludes it. Allow does not mean the selected route must use it.

The MTR physical-station and mobility-access masters are implemented as separate outputs described below. The source-folder rename to **`work/original_data`** is complete. Historical saved-run manifests retain their original paths: resolve their old `work/data/` or work-relative `data/` prefix through `work/original_data/` or `original_data/`. The repository-root `data/` directory is unchanged.

**Other agreed policies:** allow stairs for general journeys; the implemented graph `wheelchair` parameter excludes stairs, escalators and travelators. Wheelchair bus candidates exclude GMB services. Bus scope is KMB/CTB/GMB only. Unknown boarding codes become derived code 99 and are assumed to allow both pickup and drop-off. If no hospital is selected, consider all 44 institutions. Each estate has three subcosts (MTR, bus, hospital); their final combination is deliberately undecided. Standard Tobler is adopted for all eligible non-lift paths in both modes under the Step 2 modelling assumption. Equal endpoint heights use at most two rounds of four random internal samples, with repeatable sampling and separately summed uphill/downhill interval times. Step 2 implements the pedestrian graph and cost rules; Step 3 implements estate/destination attachments. Journey subcosts and ranking remain later work.

## 1. Project goal

Build a Python algorithm that lets a user select one of four Hong Kong Housing Authority public-rental-housing allocation categories and optionally a preferred hospital. Return a ranked list of estates in the selected category according to access to hospitals and public transport.

The four allocation categories are **Urban, Extended Urban, New Territories, and Islands**. They differ from the administrative districts in the estate JSON.

Use the pedestrian network for journeys. Hospitals use pedestrian-network distance; public transport uses gradient-adjusted walking time. Straight-line distances are not the ranking metric. District filtering applies to candidate estates; do not restrict the walking network or targets to that district merely because the user selected it.

The agreed mode rules supersede the original universal no-stairs requirement: allow stairs in the general network. The implemented graph `wheelchair` parameter selects the relevant path eligibility rules. With `wheelchair=true`, exclude stairs, escalators and travelators. Both modes use Tobler for healthy eligible non-lift intervals, the reviewed fallback in Section 5.6, and the lift-entry rule in Section 5.5. Step 3 implements estate/destination attachment; journey subcosts remain Step 4.

**Final-output terminology:** an estate's final **cost** combines three separate **subcosts**: MTR, bus and hospital. The transport subcost algorithms use gradient-adjusted walking time; the hospital subcost algorithm uses pedestrian-network distance. The method of combining or scaling these three subcosts into the final cost has **not been decided**. Do not silently adopt a weighted sum, illustrative weights or a single minimum across MTR/bus/hospital.

## 2. Workspace, dependencies, and communication

- The working area is `work/` within the repository. Keep new program code and project outputs there.
- Prefer inputs in `work/original_data`. If something is absent, inspect the repository parent/root, `data`, or `data/organized`; these areas contain older and duplicate material.
- Use the existing repository-root `.venv` for Python. From `work`, the interpreter is `../.venv/bin/python`.
- The checked environment is Python 3.9.6 with Pyogrio 0.11.1, NumPy 2.0.2, Shapely 2.0.7, PyProj 3.6.1, pypdf 6.20.0, **GeoPandas 1.0.1 and pandas 2.3.3**, plus approved **SciPy 1.13.1** for Step 2. GeoPandas, pandas and their missing dependencies were installed with approval in the project's `.venv` to meet the GeoDataFrame requirement. PyArrow/Fiona/rasterio remain unnecessary. Preparation uses a columnar internal container; the public spatial outputs are actual GeoDataFrames with restored nullable types and height metadata.
- If any homebrew packages are needed, ask permission first to install. Further dependency installations still need an explanation and permission. The current rerun uses the now-installed local environment without another installation.
- Preserve original data. Keep exact source selections, hashes, source-record references, and assumptions visible.
- The team has project ideas but is less familiar with technical terminology. Explain terms and why a step matters, then state the implementation actions separately. Do not skip the intermediate steps in an explanation.
- In the human-readable plan, use actual Markdown task lists: `- [X]` for completed actions and `- [ ]` for unresolved or unfinished actions. Do not use emoji ticks. Do not tick an unresolved issue merely because it has been saved or mentioned.
- **Successful precomputed outputs must not be excluded from Git.** Temporary extraction, staged/failed runs, and local cache artifacts stay in `work/cache`, which is ignored. Precomputed outputs being trackable is not an instruction to push or commit without a task to do so.
- **Step 2 commit messages:** start with `step 2 vN`, where `N` starts at 1 and increments for each subsequent Step 2 commit. Include the successful precomputed builds in the requested commit; large artifacts use Git LFS.
- **Current repository history:** `809d612` records `step 2 v2`; `4b6683d` records the cleanup and move of Step 2 instructions into `work/instructions/step_2/`. Earlier reports saying the implementation was uncommitted describe the state before those later commits. The next requested Step 2 versioned commit should start with `step 2 v3`. This context update is uncommitted; commit/push still requires a separate request.

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

Step 3 connects each approximate point to a suitable ordinary path using inclusive 200 m/50 m search/warning thresholds, with flagged expanded search if no in-threshold candidate qualifies. Connector distance, level uncertainty, indoor fallback and unattached statuses remain visible. See the Step 3 result and plan above for the implemented rules.

### 3.4 Height-aware pedestrian junctions

**Explanation for the team:** a nearby map position can represent another floor or an overhead path. A connection requires an existing endpoint and compatible geometry/heights. The connection tolerance is a modelling rule, not a claim about source elevation accuracy.

**Steps we will take:**

- [X] Apply horizontal separation **≤0.10 m** and height difference **≤0.025 m** to inferred endpoint-to-endpoint and endpoint-to-interior connections and every pair of members in an accepted cluster. Prevent chained merges from exceeding either limit.
- [X] Leave ambiguous candidates disconnected and preserve their review evidence. Determine separate visits from intervening traversal geometry, not numeric vertex-index gaps. Preserve ordinary bends, shared vertices and closed-source seams. Several paths at one supported junction are valid.
- [X] Block inferred merges between differing known floor IDs in the same building unless an explicit vertical-transition path provides the connection. Missing floor/building references remain accepted limitations.
- [X] Split receiving paths at accepted interior connections using original XYZ interpolation. Minimise XY separation within each segment’s height-permitted parameter interval, including vertical, near-vertical and constant-height cases. Use original endpoint pairs and explicit endpoint-to-interior evidence to seed components; derived cuts are not additional independent endpoints. Preserve original geometry and record alignment corrections without separate travel cost.
- [X] Report middle-to-middle crossings without automatically connecting them. Respect provider direction codes `0`, `1` and `-1`, mode exclusions and disabled-path filtering.

## 4. Always-open routes

**Agreed instruction:** assume every route is always open, at every time of day and on every date. Ignore access schedules entirely.

- Do not load or export the network's `AccessTime` or `AccessTimeDetails` records.
- Do not join/check schedule references, evaluate opening/closing hours, or request journey date/time for schedule handling.
- Any original `AccessTimeID` is retained solely as an unused source attribute.
- Source publication/update dates concern provenance, not route opening or closing.

This instruction is implemented in Step 1. Physical suitability, stairs and barriers follow the separate mode rules. Step 2 explicitly excludes `Enabled=false` in both modes. Do not silently use those fields as a back door for access-schedule processing.

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

**Explanation:** equal endpoint heights can hide a climb followed by a descent. A sequence of heights `10, 12, 14, 13, 11, 10` is uphill and then downhill in A-to-B travel; it has no single uphill/downhill sign. The two-round check is the user's flat-classification approximation; an unsampled height change can still exist. The earlier example's null signs are historical; Step 2 implements and tests the newer rule.

**Sampling/interpolation, fixed-seed repeatability and summing separately signed interval times are agreed** through the user's reply. Interpret “same height” in gradient sampling as exact equality. The separate 0.025 m tolerance applies only to graph connections and must not be reused for flat classification. Preserve original vertices and use their local Z interpolation, not a straight interpolation between equal A/B endpoint heights that would erase intermediate bends/heights. Reuse the same canonical sample locations in reverse travel, reversing their order/signs. Step 2 records these technical details and derived classifications in its source profiles and tests them before publication.

Tiny Z differences should not be described as physically precise measurements. The examples classify stored values; they do not establish real-world millimetre accuracy.

### 5.3 Two cost models

**Agreed instruction:** use two different optimisation costs on the pedestrian network:

| Target | Agreed cost kind |
|---|---|
| Public transport, including MTR and eligible bus stops | Walking time adjusted for gradient |
| Hospitals | Plain pedestrian-network distance, without a gradient penalty |

The discussion interprets the hospital distance using the documented horizontal path lengths in metres. Do not substitute straight-line estate-to-hospital distance or transport walking time for this metric.

“Walking time + gradient” means gradient influences the travel-time calculation. Do not add a raw radian value directly to seconds. A conceptual form is `base_walking_time * slope_time_multiplier(signed_gradient)`.

**Agreed after research and the later Step 2 decision:** adopt standard **Tobler's hiking function for healthy eligible non-lift intervals in both modes**, with the reviewed fallback in Section 5.6 for accepted original failures. The shared wheelchair speed assumption supersedes the earlier deferral. Use **30 seconds of lift travel time per lift use and zero waiting time**, as an arbitrary accepted model assumption. Apply **no maximum ramp-slope cutoff for now**. Negative slope values must not become negative travel costs. Keep graph weights nonnegative for shortest-path algorithms.

The two models can choose different optimal paths. Label outputs with their actual units, such as metres for hospitals and seconds/minutes for transport. Retain three separate subcosts. Final combination/scaling is deliberately undecided, so do not combine raw metres and seconds or choose weights automatically.

### 5.4 Tobler research and adopted walking model

Read the [Wikipedia page supplied by the user](https://en.wikipedia.org/wiki/Tobler%27s_hiking_function) and [Tobler's original 1993 report](https://escholarship.org/uc/item/05r820mz.pdf). The function estimates hiking/walking speed from slope; the original report describes converting terrain slope to walking velocity for minimum-time journeys.

```text
slope_ratio = tan(signed_gradient_radians)
speed_kmh = 6 * exp(-3.5 * abs(slope_ratio + 0.05))
time_seconds = horizontal_length_metres * 3.6 / speed_kmh
```

Converting the preserved signed angle with `tan` supplies the function's rise/run input; it does not replace the provider's gradient magnitude with an angle recalculated from heights. The user has adopted this standard walking function for the transport model. Hospitals retain plain distance costs. Step 2 applies the same accepted Tobler assumption in wheelchair mode.

Calculated examples: flat speed is about 5.04 km/h; using the earlier example magnitude 0.05129629 radians gives about 4.21 km/h uphill and 5.97 km/h downhill. Gentle downhill can be faster than flat; sufficiently steep downhill slows the function again. The standard function does not specify lift waiting/travel times or a wheelchair speed model. The user supplies a separate lift assumption: 30 seconds on entry per original lift identity, zero wait. Step 2 explicitly adopts shared Tobler speeds for wheelchair mode. Do not present hiking-speed output as measured wheelchair travel time.

The lift cost applies to the transport walking-time model, rather than applying Tobler to a vertical lift or giving it zero time because its horizontal length is zero. Do not charge 30 seconds separately for each polyline vertex. Hospital cost remains horizontal distance in metres; do not add 30 seconds to that distance. No hard ramp-slope exclusion is applied for now, though slope still affects walking time through Tobler. Healthy eligible non-lift path intervals, including stair lifts and moving equipment, use Tobler under the Step 2 decision; accepted failed intervals use the reviewed estimate in Section 5.6.

### 5.5 Lift identity, source profiles and unavailable time costs

**Explanation for the team:** splitting one lift record does not create several lift uses. Different original lift records remain different lifts even when used consecutively. Three such lifts therefore cost **30 × 3 = 90 seconds**. Hospital journeys still minimise horizontal metres.

The checklist below preserves the lift and original-source cost rules. Section 5.6 describes the implemented fallback overlay; baseline time graphs retain the original exclusions.

**Steps we will take:**

- [X] Use each original `PedestrianRouteID` as its lift identity. Charge **30 seconds when entering** that identity; continuing its graph pieces adds zero. Entering another identity adds another 30 seconds, even without intervening walking.
- [X] Track the current lift identity in time-routing states. A non-lift edge resets it, so leaving and re-entering the same lift incurs another charge. Waiting time is zero. Add no lift seconds to distance costs.
- [X] Build gradient classification, samples and directional interval costs on the original source path before topology splitting. Use seed `20261013` with a stable per-source derivation; cuts and reverse travel reuse the source profile.
- [X] Preserve source-level time diagnostics and all horizontal-distance usability. Evaluate each piece using only overlapping intervals: an invalid overlap or an overflowing piece total makes that direction unavailable, while healthy pieces remain routable. These original exclusions remain in baseline time graphs; primary time graphs add only the separately reviewed estimates in Section 5.6. Do not cap costs or replace provider gradients.

### 5.6 Accepted distance-and-height fallback — 16 October 2026

**Status:** implemented and verified in the selected 16 October Step 2/Step 3 pair. Baseline graphs separately retain the original exclusions. Use **6 s/m ascent and 2 s/m descent** in both modes as an explicit approximation, with the existing flat Tobler pace. The source geometry and gradients are not corrected by this decision.

**Explanation for the team**

For a journey A→B→C→D, retain Tobler time on healthy A→B and C→D. If B→C has an unusable time calculation, first review whether it represents an accepted continuous connection for the selected mode and whether its distance and height information support an estimate. A failed time formula does not by itself establish either physical impassability or a usable connection.

Where that review supports the connection, estimate B→C using horizontal walking time plus separate allowances for climbing and descending. Preserve B→C's original failed time and source diagnostics, and label its derived routing time as an estimate. Do not make B→C free, average neighbouring gradients as a replacement rule, or automatically force a detour.

```text
fallback_seconds = horizontal_distance_metres / flat_speed_metres_per_second
                 + uphill_seconds_per_metre * total_ascent_metres
                 + downhill_seconds_per_metre * total_descent_metres

flat_speed_metres_per_second = (6 * exp(-3.5 * 0.05)) / 3.6
```

Use accumulated ascent and descent along the affected section's usable original vertices, rather than cancelling a rise and fall through net endpoint height change. Calculate the reverse direction with ascent and descent exchanged. Height contributions prevent a vertical or nearly vertical section from receiving almost zero time merely because its horizontal length is tiny, provided the height and connection are accepted for modelling.

This is a project adaptation of established distance-plus-height walking-cost methods; [GRASS GIS r.walk](https://grass.osgeo.org/grass-stable/manuals/r.walk.html) documents horizontal, uphill and downhill contributions. The user subsequently adopted **6 seconds per metre uphill and 2 seconds per metre downhill** for the fallback, including wheelchair-eligible paths as an explicit approximation. These walking-based coefficients are not measured wheelchair speeds. No GRASS installation is required merely to implement a small documented cost formula in the existing Python pipeline.

**Illustrative A→D comparison, not a measured journey or fixed fallback charge**

| Section / alternative | Illustrative time |
|---|---:|
| A→B, healthy Tobler section | 2 minutes |
| B→C, reviewed fallback: 20 m horizontal and 2 m ascent | About 26 seconds, using the illustrative 6 s/m uphill allowance |
| C→D, healthy Tobler section | 3 minutes |
| Direct A→B→C→D | About 5 minutes 26 seconds |
| A→D using the available detour | 13 minutes |

Dijkstra compares complete journey costs and selects the estimated 5:26 route in this example. If B→C instead costs 10 minutes, the direct total becomes 15 minutes and the 13-minute detour wins. Whenever using fallback estimates changes the selected journey or reachability, report the estimated route and the route available with fallback sections excluded. If that comparison route is unavailable, say so explicitly.

**Agreed instructions recorded**

- [X] Keep Tobler on healthy sections and preserve all original geometry, provider gradients, sampling evidence and failed-time diagnostics.
- [X] Allow a separately identified distance-and-height fallback on specifically reviewed, accepted connections with unusable time calculations. Begin the review with the existing 26 affected source records and their problematic intervals; do not automatically apply a fallback to every steep section.
- [X] Preserve path direction, Enabled filtering and all mode restrictions. A fallback must not make stairs or other prohibited paths wheelchair eligible, invent a cross-level connection, or override a barrier. Lifts retain the existing 30-second entry rule.
- [X] Keep unsupported connections or geometry unresolved. A cost estimate does not repair them. Keep healthy neighbouring intervals usable even where the problematic interval cannot qualify for a fallback.
- [X] Compare the fallback-enabled journey against available alternatives using finite, nonnegative costs. Expose estimated-section identities, reasons, costs and warnings, and the comparison route when fallback changes the selected journey or reachability.
- [X] Apply this change to the transport time model. Hospital horizontal-distance costs remain unchanged by this fallback decision.

**Implementation and verification actions**

- [X] Record the review of all **26 affected records / 27 intervals** in [time_fallback_review.json](../config/time_fallback_review.json). Original same-source continuity and height changes are accepted for approximate costs; original failures and uncertain geometry remain visible, including zero-height-vertex warnings. Eligibility restrictions remain. Original source geometry issues are not marked resolved.
- [X] Record the user-confirmed fallback coefficients: **6 s/m uphill, 2 s/m downhill**, shared with wheelchair mode as an explicit approximation. These settings are saved in the versioned routing policy.
- [X] Update the Step 2 and Step 3 plans for a complete coordinated rebuild, integrating the fallback throughout original-source profiles, attachments, subdivisions, matrices and validation. Retain historical run evidence; completed rebuild tasks are now checked.
- [X] Set executable policies and implement the revised plans in one full Step 2/Step 3 rebuild, preserving original source diagnostics and a comparable baseline time scenario.
- [X] Validate ordinary, vertical/near-vertical, uphill/downhill and rise-and-fall cases, route selection against detours, mode restrictions, uncertainty reporting, and save/reopen preservation. Publish new versioned outputs before claiming that current routing uses this rule.

## 6. Wheelchair parameter, transport scope and boarding codes

### 6.1 Mode/operator eligibility

**Latest user instruction:** the bus subcost considers **KMB, CTB and GMB only**. General calculations retain all three. Wheelchair bus-candidate selection removes GMB services; KMB and CTB remain eligible under the user's accepted wheelchair-accessibility assumption. MTR remains the separate third transport category/subcost and retains its accepted mode-accessibility assumption.

- Do not reopen general vehicle accessibility certification as a mandatory prerequisite for using these accepted mode/operator assumptions.
- Preserve operator information and source evidence.
- A stop served by GMB and KMB/CTB can remain eligible in wheelchair mode through its KMB/CTB services. Filter service/operator evidence before deciding stop eligibility.
- Joint codes such as `KMB+CTB` are split into their operator memberships.
- Other bus operators, including LWB/NLB, are outside the selected bus scope. Preserve their original records, but do not include them in this bus subcost or reclassify them as KMB/CTB. Joint services can qualify through an included operator.

This mode policy does not mean every connecting footpath is wheelchair suitable. The pedestrian network's physical barriers remain separate from transport eligibility.

### 6.2 MTR access selection

**Agreed, clarified 14 October:** general mode starts with all **611 mapped access points** as candidate targets, subject to general equipment rules. Wheelchair mode accepts the existing **276 mapped mobility access records as its complete target pool** for this model. Do not make complete station coverage, further entrance research or exact equipment reconciliation a prerequisite. These records are entrances/access points, not stations. The remaining 335 points are general-mode candidates and outside wheelchair targets. Preserve both lists. All routes must still satisfy path/direction rules and connectivity; the accepted 276 targets are not guaranteed reachable from every estate.

**Accepted equipment differences:** Tin Shui Wai C, Diamond Hill A2 and LOHAS Park B count as mobility access points. Their ramp/lift/same-level differences do not require further investigation for target eligibility. Preserve both source descriptions without claiming one is the confirmed equipment type. Route lift timing comes from the actual lift edge used, not a guessed interpretation of the entrance label.

MTR's [accessibility booklet](https://www.mtr.com.hk/archive/en/services/caring_for_our_customer_booklet.pdf) states that each station and Light Rail stop has at least one barrier-free access. The three stations without a mapped mobility point in our selection therefore represent incomplete coordinate/evidence coverage, not a finding of physical inaccessibility. The user accepts the present 276-point coverage; do not invent locations or automatically add station-centre targets.

**Agreed equipment eligibility, including the clarification:** lifts, stair lifts and wheelchair aids can be valid routes when `wheelchair=true`. In general mode (`wheelchair=false`), exclude **both wheelchair aids and stair lifts**; ordinary lifts remain eligible. This does not reverse the separate wheelchair exclusion of ordinary stairs, escalators and travelators. Keep equipment types distinct in the data and apply their mode-specific rules. For time routing, each original lift identity costs 30 seconds on entry with zero wait; continuing its split pieces adds no charge. All eligible non-lift intervals, including stair lifts and moving equipment, use the same Tobler function in both modes. Equipment timing is settled for this model.

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

### 6.4 Wheelchair parameter and later journey integration

| Selection | Pedestrian paths/equipment | Bus services | MTR candidate pool |
|---|---|---|---|
| General / `wheelchair=false` | Allow ordinary stairs, escalators, travelators and lifts; exclude wheelchair aids and stair lifts | Allow KMB, CTB and GMB | All 611 mapped access records, subject to general equipment rules and route connectivity |
| `wheelchair=true` | Exclude ordinary stairs, escalators and travelators; allow lifts, stair lifts and wheelchair aids | Allow KMB and CTB; exclude GMB | The existing 276 mobility access records, accepted as the complete target pool; routes still obey path rules |

Keep the complete source/prepared data. Step 2 provides graphs for both selections; later journey calculations must select the matching graph and targets. Do not permanently delete stairs or GMB from the shared data. The parameter must affect routing/target selection before calculating **all three subcosts**, since the optimal route and nearest eligible stop may change. General mode excludes wheelchair aids and stair lifts; wheelchair mode allows them. **Latest answer: when wheelchair=true, exclude paths with WheelchairBarrier=1.** Source code 2 means false; missing/unknown values remain explicitly unknown. MTR selection, ordinary lift timing and the absence of a hard ramp-slope limit are settled. Eligible non-lift path intervals use Tobler, including other equipment paths, under the Step 2 decision.

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

**Current validated snapshots:** frozen Step 1 `20261014T090829Z-20d0139c`, Step 2 `20261016T075559Z-119a5636` and Step 3 `20261016T080509Z-4c604c82`. The [pair registry](../precomputed/outputs/rebuild/current.json) selects compatible graph stages; `outputs/current` selects Step 1. All **134 tests** and full-data validations pass. Both graph stages retain six matrices, spatial GeoDataFrames, routing/terminal mappings, original and derived evidence, and complete source diagnostics. See [Step 2 validation](../precomputed/outputs/step_2/current/validation_report.md) and [Step 3 validation](../precomputed/outputs/step_3/current/validation_report.md).

**Retained complete builds:** paths relative to `work/`. Earlier audit/cleanup statements describe their date, rather than the current selected pair.

| Output | Current complete build |
|---|---|
| Step 1 and frozen preparation input | `precomputed/outputs/runs/20261014T090829Z-20d0139c` |
| Step 2 pedestrian graphs | `precomputed/outputs/step_2/runs/20261016T075559Z-119a5636` |
| Step 3 attached graphs | `precomputed/outputs/step_3/runs/20261016T080509Z-4c604c82` |
| Standalone MTR output | `precomputed/outputs/mtr_master_runs/20261013T122652Z-run-9juiqhf3` |

Previous successful Step 2 `20261014T105436Z-8fe534aa` and Step 3 `20261014T145819Z-4d15d1a3` remain retained for historical comparison. Original inputs and the verified `cache/network_1961f2466a896ff4` extraction remain available. Failed test/build candidates in cache are not selected outputs; no new cleanup was performed in this rebuild.

The [history directory](../precomputed/history/README.md) contains compact reports, manifests, policies, identity records and regional summaries for the three removed snapshots. These are metadata archives, not loadable builds: geometry, routing matrices, profiles and mappings from those superseded runs were removed. `original_SUCCESS.json` records an old completion and is not a current successful-build marker. Historical artifact hashes and earlier test reports describe checks performed before cleanup; the cleanup inventory records retained metadata hashes and the successful post-cleanup checks.

**Historical Step 1 scope:** that run did not implement production graph construction, Enabled filtering, snapping/connector construction, routing costs, distance/time caches, or ranking. Step 2 now implements graph construction and both cost models; use its implementation/review document for full-data publication status. Step 3 now implements estate/destination connectors; journey subcosts and ranking remain later work. The local gradient demonstrations are examples, not completion of these later stages.

The previous successful full Step 1 snapshot was **`20261013T121410Z-c823aaf9`**, then selected through `work/precomputed/outputs/current/`. It passed with **zero errors, 14 warning groups and 31 passing tests**. All six GeoDataFrames, sixteen reference tables, eight embedded MTR JSON files and the policy snapshot passed full read-back checks. All 23 source hashes were rechecked before publication. Its full build was removed during cleanup; its reports remain in the history directory. The still earlier `20261013T081016Z-b7e527bb` run and its 93 row-level warnings are historical references, not an available current build. Lower warning count reflects resolved physical matching, accepted assumptions recorded as assumptions, and grouped retained source gaps; it does not mean all missing evidence was resolved.

| Spatial layer | Records |
|---|---:|
| Pedestrian network | 465,892 |
| Estates | 244 |
| Hospitals | 44 |
| MTR access records | 611 |
| Railway station reference points | 98 |
| Bus/minibus stops | 9,264 |

Total spatial records: 476,153. All exported geometries/attributes and reference-table values were checked after reopening. The network retains all 1,963,912 vertices and original Z coordinates. Only five non-schedule network supporting tables are loaded.

Code is in [work/src/estate_ranking](../src/estate_ranking). Configuration is [work/config/step_1.json](../config/step_1.json). Outputs are selected through [work/precomputed/outputs/current](../precomputed/outputs/current). The saved [current Step 1 validation report](../precomputed/outputs/current/validation_report.md) records its checks. The [independent audit of the previous run](../precomputed/history/step_1/20261013T121410Z-c823aaf9/step_1_recheck.json) remains historical evidence for that earlier snapshot.

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
- Candidates and failures are written to cache; the previously failed candidates were removed during cleanup. Complete selected Step 1 and Step 2 runs remain under `precomputed/outputs/runs` and `precomputed/outputs/step_2/runs`, respectively. Historical metadata lives under `precomputed/history`.
- A current-run symlink publishes data and its identity snapshot together. The local `config/entity_ids.json` link points to that snapshot. A fresh checkout restores identities/aliases from the published snapshot if the local link is absent.
- Original iGeoCom `EASTING`/`NORTHING` fields are named `source_grid_easting`/`source_grid_northing` to avoid case-insensitive collisions with working coordinate fields. Original properties remain in `raw_json`.
- Geodatabase FIDs identify records in their selected source snapshot; do not treat them as guaranteed persistent entity IDs across new source versions. Persistent path IDs and the estate/hospital ID registry serve different purposes.
- Coded booleans must be decoded explicitly: several fields use 1=true and 2=false, so ordinary Python truthiness would misread 2. WheelchairBarrier=1 indicates a segment assessed as unsuitable; WheelchairAccess=1 describes an accessible entrance/exit connection and is not a universal flag that every usable path must have. Keep codes, labels, nulls, and source definitions separate.
- Use `utf-8-sig` for JSON/CSV inputs where a BOM may be present. Do not turn nullable integer identifiers into strings such as `"117.0"`, or merge different stop IDs merely because their coordinates coincide.

## 9. Source files and provider evidence

### Accepted site-version selection — 14 October 2026

The two Castle Peak Hospital supporting site records share SiteID **1503020249**. Use the record with the latest parsed `LastAmendmentDate`: **2026/07/13 00:00:00**, English name `CASTLE PEAK HOSPITAL`. The older version is amended 2022/06/06. Preserve both source records with their distinct record IDs, but choose the newer one wherever a single canonical site description is needed; avoid multiplying path rows by joining both versions. This is a network site-reference choice, not an extra hospital destination or a change to the 44 hospital targets. The selection rule is implemented and verified in the rebuilt Step 1 canonical lookup; both source versions remain preserved.

### Physical MTR masters added after the original Step 1 export

**User instruction:** create one file with a unique ID, name and coordinates per physical station, ignoring lines/routes, and another with station ID, mobility exits/access points and their own coordinates. Use the supplied MTR dictionary to decode the CSVs.

**Implemented:** [mtr_station_master.json](../precomputed/mtr_master/mtr_station_master.json) has 98 stations; [mtr_mobility_exit_master.json](../precomputed/mtr_master/mtr_mobility_exit_master.json) has 276 mobility access records across 95 stations. IDs are `MTR-S-<station GEONAMEID>` and `MTR-A-<access GEONAMEID>`, independent of row order and line membership. Original iGeoCom WGS84 points supply coordinates. Ten mobility points have no named exit code and retain null codes. Distinct source points remain distinct even when coordinates/exit names coincide.

All 611 access points now match physical stations, including Racecourse and the Diamond Hill record. All 100 CSV station IDs map to these stations through a separate legacy-ID table. Hong Kong 39/44, Kowloon 40/45 and Tsing Yi 42/46 now each share one physical identity.

The ZIP's station, facility and category PDFs confirm `Station_No` refers to station CSV ID, `Key` to `Item_Code`, and `Y/N` to available/unavailable. The facility coordinate field is explicitly **not in use**. Decode all 3,564 facility rows; do not use that field as coordinate evidence. Use point-level iGeoCom mobility categories or positive external facility descriptions linked to the exact station/exit. Paid-area/general station facilities do not generate street entrance coordinates. Exit-level evidence does not locate equipment at each associated map point; its scope is recorded.

The selected 276 comprise 249 explicitly categorised points plus 27 otherwise unspecified points with named-exit facility evidence. The user now accepts these 276 as the complete wheelchair target pool, including the three equipment-description differences. All other 335 points remain in the full access map and review file for general-mode consideration. Assisted types, exit-only evidence and equipment descriptions are preserved. The master itself does not implement route reachability; later mode-specific rules follow Section 6.

Run from `work/`: `PYTHONPATH=src ../.venv/bin/python -m estate_ranking.mtr_master`. The standalone output is staged/checked and published through `precomputed/outputs/mtr_master`. Step 1 embeds the same prepared records in `outputs/current/mtr_master/`; the original MTR bookmark points to that integrated snapshot. The earlier MTR-integrated suite passed 31 tests; the current complete suite passes 89. See [the master guide](../precomputed/docs/mtr_master_readme.md), [review](../precomputed/mtr_master/mtr_master_review.json) and [manifest](../precomputed/mtr_master/mtr_master_manifest.json).

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

The statuses below distinguish remaining implementation/source questions from accepted modelling decisions. An accepted limitation is not a repaired source record. `[X]` on a decision means it has been recorded, not that new output has been generated.

- [X] **Equal-height implementation:** Step 2 implements and tests repeatable XYZ samples, at most two rounds of four, exact height equality, the bounded ten-point flat check and separately signed interval times. Raw gradients and sampling evidence are retained.
- [X] **Time-model implementation:** Step 2 implements and tests standard Tobler for all eligible non-lift paths in both modes, summed signed intervals, and lift identity entry charges of 30/0-second travel/wait. This supersedes the older deferred wheelchair/equipment notes. Hospital cost stays distance.
- [X] **Autonomous Step 2 source/routing audit:** qualifying endpoints are preferred after visit checks; invalid intervals are isolated without new junctions; the 89-test suite and full-data audit pass in `20261014T105436Z-8fe534aa`. Original records and retained builds remain unchanged; superseded build artifacts were subsequently removed at the user's request. The later repository commits are recorded below; this context update remains uncommitted.
- [X] **Old-build cleanup and verification:** remove three superseded builds and 14 failed candidates, reclaim 3.866 GiB, retain compact historical metadata, and verify all 30 selected Step 2 artifact hashes, seven frozen Step 1 hashes, selected links, metadata hashes and current graph loading/source-ID regressions. The current builds and original inputs remain available.
- [ ] **Original vertical/gradient limitations:** 25 sources contain original vertical intervals and one source has unrepresentable Tobler time. Healthy adjacent pieces are now usable; replacement source geometry/gradient is unsupported. That was the original time-model limitation; reviewed intervals now have primary estimates, while baseline graphs retain the original exclusions. Original geometry/gradient defects remain unresolved and are not marked repaired.
- [X] **Physical graph implementation:** Step 2 implements and tests directed connections, complete compatible clusters, height/floor checks, mode exclusions and disabled-path filtering. Step 1 continues to preserve all source rows and prepare base candidates. No schedule checks or maximum ramp-slope cutoff are introduced.
- [X] **MTR candidate preparation/integration:** all 611 points are retained, physical identities/evidence are integrated and base mode/equipment candidate flags are prepared. Step 2 implements pedestrian graph connections and mode filtering. Step 3 now attaches eligible MTR access points; calculating estate-to-MTR journeys remains Step 4.
- [ ] **Unnamed MTR access codes:** physical station matching is resolved in the new masters. Of the old 12 parsing cases, two alternate name formats now parse; ten source points genuinely supply no named exit code. Retain their coordinates and null codes unless supported exit labels are obtained. The old 45-case report has not been rewritten.
- [ ] **Facility IDs 70/888:** 72 facility rows refer to these station IDs absent from the station CSV. These are two missing station identities, not 72 stations. Identify/document them without guessing.
- [X] **Equipment-difference decision recorded:** accept Tin Shui Wai C, Diamond Hill A2 and LOHAS Park B as mobility access points; no exact ramp/lift/same-level reconciliation is required. Both source descriptions remain preserved. This closes the modelling question, not the documentary difference.
- [X] **MTR coverage decision recorded:** accept the existing 276 mapped mobility points as the complete wheelchair MTR target pool. The other 335 points remain general candidates and outside wheelchair targets. Unlocated facilities and the three stations without mapped mobility points remain source limitations; no further coverage research is required for this model.
- [X] **Terminal/floor/building warning treatment recorded:** ignore these non-blocking findings as investigation tasks: 9 terminal IDs affect 11 paths, 3 floor IDs affect 34 paths, and 44 BuildingID_1 values affect 248 paths. Preserve IDs, geometry and diagnostics; ordinary level/connectivity checks remain required. The missing references have not been repaired.
- [ ] **Other missing network references where needed:** 107 site IDs affect 280 paths; nine distance-post records refer to missing path IDs. These were not included in the ignore instruction. Assess only where a later operation needs the relationship; do not discard valid geometries automatically.
- [X] **Castle Peak Hospital version decision recorded:** select the latest `LastAmendmentDate`, 13 July 2026, for SiteID 1503020249. Preserve both source versions.
- [X] **Apply the latest warning-review decisions in implementation:** executable policy and canonical site lookup were updated and validated in Step 1 run `20261014T090829Z-20d0139c`. All original versions and unresolved reference evidence remain preserved.
- [X] **Bus candidate preparation:** derive unknown code 99 with assumed pickup/drop-off permission, retain raw values and derive KMB/CTB/GMB general candidates plus KMB/CTB wheelchair candidates. Actual route reachability/cost calculation is unfinished.
- [ ] **Hospital-scope implementation:** all 44 institutions are included when none is selected. Implement the settled rule; do not reopen A&E-only scope as an unanswered question.
- [X] **Estate/destination attachment:** rebuilt and verified in `20261016T080509Z-4c604c82`. The current 200 m/50 m search/warning thresholds, expanded flagged search, flat costs, outdoor preference, indoor fallback, uncertain levels, original/derived source-profile subdivisions, scenario-specific mappings and directed terminals are implemented. See current coverage and long-connector warnings above. Subcosts and final ranking remain later work.
- [ ] **Subcost/ranking implementation:** minimum reachable route cost within each eligible target group is agreed. Implement the three separate subcosts and retain target IDs/units/reachability. Combining/scaling them into final cost and handling wholly unreachable target groups in that final ranking are deliberately deferred; original recommended weights are not agreed settings.
- [X] **Time-fallback approach recorded — 16 October 2026:** use a flagged distance-and-height estimate on reviewed accepted connections whose time model fails, retain Tobler on healthy sections, and compare complete journeys with available alternatives. See Section 5.6.
- [X] **Time-fallback rebuild and validation:** complete Steps 2/3 rebuilt, all 134 tests and full-data validation passed, primary and baseline outputs saved and selected as the verified 16 October pair. Original source defects remain open above. Actual estate journey comparison/cache reporting remains Step 4.
- [ ] **Optional later checks:** DTM use, new-estate allocation verification, dataset-currency review and interpretation of co-located records where relevant. Do not turn these into unnecessary prerequisites for accepted assumptions.

Closed as modelling decisions: always-open routes; WGS84 and map-point assumptions; supplied gradient magnitude with height-based sign and the two-round/four-points-per-round equal-height fallback; repeatable interpolated path samples and summed local interval times; shared standard Tobler on healthy eligible non-lift intervals in both modes, with the newly accepted reviewed distance-and-height fallback approach in Section 5.6; 30/0-second lift travel/wait and no hard ramp-slope cutoff; general retention of stairs with wheelchair exclusion of stairs/escalators/travelators; wheelchair allowance of lifts/stair lifts/wheelchair aids with general exclusion of stair lifts/wheelchair aids; KMB/CTB/GMB-only bus scope with wheelchair exclusion of GMB; 611/276 MTR candidate pools; unknown derived boarding code 99 treated as both; all 44 hospitals when none is selected; minimum reachable route cost within each target group; two cost-model kinds and three separate estate subcosts. Fallback height coefficients are settled at 6 s/m uphill and 2 s/m downhill in both modes as an explicit approximation; full-data validation passed in the selected 16 October pair. Final combination remains deliberately undecided. Implementation status varies as described above.

## 11. Gradient demonstrations already performed

The user asked for five points on Pok Fu Lam Road from HKU C1 toward Queen Mary, then asked for points farther apart.

Sources used: MTR access points for C1 (`GEONAMEID 559800`, longitude 114.13456, latitude 22.28449), hospital points for Queen Mary (longitude 114.13117, latitude 22.2704), original network XYZ/Gradient data, and the two relevant provider dictionaries.

- [Initial five-point sample](../precomputed/docs/hku_c1_pokfulam_gradient_sample.json): first sampled road-side point about 10.3 m from C1's 2D map point; four intervals covering 13.2 m. Two had equal endpoint heights with positive raw gradients; two had decreases. Equal-height signs were left unassigned. Two links have wheelchair-barrier flags. It was a slope demonstration, not a validated accessible route.
- [Farther sample](../precomputed/docs/hku_c1_pokfulam_gradient_farther_sample.json): five existing vertices across source path `250002139`, horizontal length 228.157334 m, supplied gradient `0.05129629` radians. Heights toward Queen Mary: **62.7974, 65.3262, 68.7189, 71.1355, 74.5113 m above HKPD**. All four sampled comparisons rise, so all use `+0.05129629`; reverse travel uses the negative value. The first point is about 117.8 m from C1 in straight-line position; that location offset is not the ranking metric.

The farther points belong to one source polyline. The same magnitude is therefore retained for every sampled interval; it was not recalculated from the sampled height difference. Full coordinates, source hashes and intervals are in the JSON/CSV artifacts. The initial example script is [work/examples/hku_c1_pokfulam_gradient_demo.py](../examples/hku_c1_pokfulam_gradient_demo.py).

## 12. Documents to consult next

1. This handoff for the latest user decisions and remaining choices.
2. [Step 3 plan](step_3/step_3_plan.md) and [implementation](step_3/step_3_implementation.md) for facility connections, terminal APIs and validated coverage.
3. [Step 2 plan](step_2/step_2_plan.md) and [implementation/review](step_2/step_2_implementation.md) for current graph/cost rules and validated outputs.
4. [Step 1 human-readable plan](step_1/step_1_implementation_human_readable.md) for detailed explanations and checklists. Its older resolution entries must be interpreted with the later accepted assumptions above.
5. [Step 1 technical plan](step_1/step_1_implementation_plan.md) for implementation structure.
6. [Original estate-ranking design](estate_ranking_design.md) for the overall pipeline; later decisions here override earlier suggestions, notably the hospital distance model and ignored schedules.
7. [Earlier chat export](whole_chat_export.md) for historical context; it does not contain all decisions made after it was prepared.
8. [Provider-document review](../precomputed/docs/step_1_provider_documentation_review.md), [latest validation report](../precomputed/outputs/current/validation_report.md), and [MTR review CSV](../precomputed/outputs/current/mtr_match_review.csv) for evidence and snapshot details.

When a future decision is made, update this handoff and affected checklist items. Record whether the change is a modelling assumption, a source-confirmed fact, or implemented behaviour. Keep unresolved items unchecked and do not claim that a discussion or demonstration completed production routing.
