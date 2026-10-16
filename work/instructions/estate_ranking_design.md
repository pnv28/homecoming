# Estate ranking: current design and implementation stages

**16 October rebuild completed:** selected Step 2 `20261016T075559Z-119a5636` and Step 3 `20261016T080509Z-4c604c82` passed the full coordinated build, all saved-output checks and **134 tests**. Primary time graphs use reviewed distance-and-height estimates; separate baseline time graphs exclude them. Original geometry/gradient defects remain visible. Selection is recorded in `work/precomputed/outputs/rebuild/current.json`. Run the complete coordinated build with `PYTHONPATH=work/src .venv/bin/python -m estate_ranking.rebuild`.


Updated 2026-10-16 18:28:20 HKT (UTC+08:00). Read [project_context_and_decisions.md](project_context_and_decisions.md) for complete decisions and [the Step 3 implementation](step_3/step_3_implementation.md) for current coverage/warnings. Frozen Step 1 remains `20261014T090829Z-20d0139c`; Step 4 is implemented and verified; Step 5 has an agreed plan; ranking implementation remains pending.

**Step 4 amended and verified:** selected cache `20261016T102523Z-8e69faad` contains all 10,736 shared hospital pairs (6,323 reachable), both sets of 976 transport groups and 931 same-target comparisons. Only the two reviewed hospital origins were recalculated; all graph/transport outputs are unchanged and Kam Peng remains unavailable. All 8,186 reachable cached routes passed directed transition/cost checks; 151 repository tests pass. See [the implementation/API guide](step_4/step_4_implementation.md).

## Purpose and final output

A user selects one of the four Housing Authority allocation categories: Urban, Extended Urban, New Territories or Islands. They may select a hospital. The implemented `wheelchair` parameter changes transport path/equipment and target eligibility. Hospital distances always use the shared general-distance cache.

Each candidate estate has three separate subcosts:

| Subcost | Algorithm and units |
|---|---|
| MTR | Minimum reachable gradient-adjusted walking time to an eligible MTR access point, in seconds |
| Bus | Minimum reachable gradient-adjusted walking time to an eligible boarding stop/service, in seconds |
| Hospital | Pedestrian-network distance to the selected hospital, or minimum reachable distance to any of all 44 institutions if none is selected, in metres |

Use network journeys rather than straight-line distances. Filter the candidate estates by allocation category without cutting the pedestrian network or destinations at category boundaries.

**Step 5 scoring decisions are agreed; implementation is pending.** Scale each available cost as `100*x/(x+k)`, with bus `k=600 seconds`, MTR `k=900 seconds` and hospital `k=5000 metres`. Combine with equal thirds by default and configurable normalised nonnegative weights. Preserve all raw costs, targets, units, reachability and warnings. Complete estates rank first; incomplete estates follow by most available required components, then estate name/ID, without a total cost or numerical rank. Do not add raw metres and seconds or take one minimum across the three categories.

## Shared assumptions and mode rules

All routes are assumed always open. Do not load, export, join or evaluate `AccessTime`/`AccessTimeDetails`, or introduce journey date/time inputs. Preserve `AccessTimeID` only as inert source evidence. Dataset publication/update dates describe provenance.

Use supplied estate/hospital map points as accepted approximations; verified entrance collection is not required. WGS84 is accepted for estate/hospital/bus longitude-latitude inputs. iGeoCom WGS84 and the network's HK1980 grid/HKPD heights are provider-confirmed. Work horizontally in EPSG:2326 and preserve network XYZ and EPSG:5738 height metadata.

**Terminology:** “Allow” means a path, equipment type or service may be considered for routing, subject to the other rules and connectivity. “Exclude” means routing cannot use it in that mode. “Preserve” means keep the original record in the saved data, even when routing excludes it. Allowing something does not require the chosen route to use it.

| Rule | General / wheelchair=false | Wheelchair=true |
|---|---|---|
| Ordinary stairs, escalators, travelators | Allow | Exclude |
| Ordinary lifts | Allow | Allow |
| Stair lifts and wheelchair aids | Exclude | Allow |
| Paths marked WheelchairBarrier=1 | This flag alone does not exclude them | Exclude |
| Bus operators | KMB, CTB, GMB | KMB, CTB |
| MTR target pool | All 611 mapped access records, subject to general equipment rules | The existing 276 mapped mobility access records, accepted as the complete target pool for this model |

Use the existing 276 mobility access records as the complete wheelchair MTR target pool; do not require additional entrance research or complete mobility coverage at every station before proceeding. These are entrance/access points, not 276 stations. The other 335 points remain available to general mode and outside wheelchair targets. Accept Tin Shui Wai C, Diamond Hill A2 and LOHAS Park B as mobility access points without requiring their ramp/lift/same-level descriptions to be reconciled. Preserve those source descriptions for traceability. Apply general-mode equipment exclusions where the source identifies stair lifts or wheelchair aids. All journeys still obey path and direction rules, so accepting a target does not establish that it is reachable from every estate. Any lift cost must come from the equipment actually used by the route, not an unresolved entrance description.

Bus operator selection applies to services before aggregating stops. Joint services qualify through an allowed operator; a mixed GMB/KMB stop is not discarded when its KMB service qualifies. Other operators remain preserved in source data but are outside the bus subcost.

There is no maximum ramp-slope cutoff for now. Preserve all original rows so both modes can be calculated later. Candidate flags prepare the rules; they do not establish real network connectivity or physical equipment coordinates. Both modes use the agreed shared standard Tobler assumption on eligible non-lift paths; this is a modelling choice, not a measured wheelchair speed.

## 1. Harmonise and prepare the data — implemented and rechecked

### Explanation for the team

The source files use different formats and identifiers. Preparation gives them consistent coordinates, identities and field types while preserving the original information. The result is six actual GeoPandas GeoDataFrames, persisted as layers in a GeoPackage. Reference tables without geometry are kept in SQLite, and source/rule/review records are kept in JSON/CSV.

Original inputs are in `work/original_data/`; selected older supplementary files are copied into its `reference/` subfolder with their origin and checksum recorded. The existing local `.venv` is used. GeoPandas 1.0.1 and pandas 2.3.3 were installed with approval; no Homebrew packages were installed.

### Steps we take

1. Inventory every configured input and its hash; verify the seven selected reference copies against their originals. Record package versions, explicit assumptions and `routing_policy.json`.
2. Safely extract/inspect the 3D geodatabase and load its paths plus five non-schedule supporting tables. Preserve every part, vertex, height, timestamp and source code. Skip both schedule tables.
3. Load estate, hospital, access/station and bus points; transform X/Y to EPSG:2326, preserving original coordinates and unknown point heights.
4. Match all 244 estates to the documented allocation lookup. This data crosswalk is an estate-category mapping, not pedestrian-crossing data. Keep administrative districts separate.
5. Decode the supplied MTR dictionary. Create 98 physical station IDs independent of lines, translate all 100 legacy IDs, and link all 611 access points. Preserve 276 mobility records and unresolved evidence. Integrate physical IDs into the spatial layers and SQLite relationships, and embed the eight JSON masters in the same run.
6. Reconcile all 9,264 stops against 69,364 bus/GMB service rows. Preserve raw `stopPickDrop` and derive unknown code **99**, assumed pickup/dropoff both. Known codes remain 1=dropoff, 2=pickup, 3=both. Derive general and wheelchair boarding candidates from the permitted services.
7. Prepare mode-candidate flags without deleting paths or points. General mode allows ordinary stairs/escalators/travelators and excludes stair lifts and wheelchair aids; wheelchair mode excludes ordinary stairs/escalators/travelators and paths marked WheelchairBarrier=1. MTR evidence/equipment selection follows the table above. Missing evidence stays visible.
8. Validate identities, geometry, coordinates, source accounting, estate assignments and required relationships. Save diagnostics for unresolved source references; do not invent missing station identities or equipment locations.
9. Write staged GeoPackage/SQLite/JSON/CSV outputs. Reopen every geometry/attribute/null/reference value, including the actual GeoDataFrames, and recheck all 23 source hashes before selecting the successful run.

Step 1 selects the Castle Peak Hospital supporting site record with the latest `LastAmendmentDate`: SiteID 1503020249, amended **13 July 2026**. Preserve both original site records, but use only the selected version where one canonical site description is needed. This does not create a second hospital target. Missing terminal, floor and building references are non-blocking Step 1 warnings; ignore them as investigation tasks and do not discard their paths. Preserve the original IDs and diagnostics. This decision does not waive ordinary geometry, height or connectivity checks. Missing site references and distance-post/path references are separate findings whose status is unchanged.

The Step 1 rerun passed with **476,153 spatial records, zero blocking errors and 14 warning groups**. Its historical stage-specific suite passed **31 tests**; the complete repository suite now passes **151 tests**. Warnings document actual MTR evidence gaps, missing supporting network references, both Castle Peak Hospital reference versions and allocation-proxy provenance. They are not failed preservation checks. See the [validation report](../precomputed/outputs/current/validation_report.md).

Finished results are under `work/precomputed/outputs/current/`, selected from successful snapshots in `outputs/runs/`. This folder includes `harmonised.gpkg`, `reference_tables.sqlite`, `schema.json`, `source_manifest.json`, `model_policy.json`, validation/rejection reports, IDs and `mtr_master/`. Failed candidates remain in `work/cache` without replacing the prior successful data/IDs. Successful precomputed outputs remain trackable in Git.

From `work/`:

```sh
PYTHONPATH=src ../.venv/bin/python -m estate_ranking.step_1 --config config/step_1.json
PYTHONPATH=src ../.venv/bin/python -m unittest discover -s tests -v
```

Load the actual GeoDataFrames:

```python
from estate_ranking.export import read_outputs, read_geodataframe

frames = read_outputs()  # dictionary of all six GeoDataFrames
estates = frames["estates"]
network = read_geodataframe("precomputed/outputs/current", "network")
```

The loaders restore nullable integer/boolean/string fields and preserve CRS, geometry Z and vertical metadata. Internal `SpatialDataset` containers support efficient ingestion; they are not the public output type. See [both Step 1 plans](step_1/) for detailed explanations and completed checklists.

## 2. Build directed pedestrian connections and route costs — implemented and verified

### Explanation for the team

A graph connects usable pieces of the pedestrian network. A point where a bridge crosses a road in the map is not automatically a junction; heights and source references matter. Direction restrictions are separate from uphill/downhill direction.

### Steps we will take

1. Apply the selected mode's candidates/equipment rules, preserving raw sources and explicit unknowns. Inspect `Enabled` semantics where needed without reintroducing schedules. Do not require investigation of the accepted missing terminal/floor/building references; use available geometry, heights and connection evidence. Assess other source gaps only where a required operation depends on them.
2. Build nodes/connections at appropriate endpoints and junctions. Split paths where a real connection meets their interior. Preserve separate levels and avoid merging every coincident XY location. Use the agreed inferred-junction tolerances of 0.10 m horizontal / 0.025 m height; they do not establish source elevation accuracy.
3. Keep each source feature's gradient magnitude `n`, measured in radians. Use +n for rising heights and -n for falling heights in travel order. Reversing travel reverses those signs; the provider `Direction` field controls permitted travel, not slope sign.
4. When endpoints A/B have equal heights despite a nonzero/differing gradient indication, take four repeatable random internal samples along the actual XYZ polyline. Interpolate from its existing vertices. If those samples remain level, take four additional distinct samples between the same A/B, giving ten points total. Stop after at most two rounds. If all remain level, assume relatively flat and use derived zero slope, preserving the raw gradient. If heights vary, order the points along the path and preserve separately signed portions. Do not recursively create further sampling rounds.
5. For walking transport costs, use standard Tobler:

```text
slope = tan(signed_gradient_radians)
speed_kmh = 6 * exp(-3.5 * abs(slope + 0.05))
time_seconds = horizontal_length_metres * 3.6 / speed_kmh
```

This converts the provider angle to rise/run input without recalculating its magnitude from heights. Sum separately signed interval times; a climb followed by a descent must account for both costs. Sampling uses exact height equality for now and seed 20261013, recorded in the policy snapshot. Reuse canonical sample positions for reverse travel.

6. For reviewed time-model failures, use horizontal flat walking time plus **6 seconds per metre climbed and 2 seconds per metre descended**, as an explicit approximation in both modes. Preserve original geometry/gradient/failure evidence, retain baseline time graphs without these estimates, and carry review IDs and warnings through splitting and journey reconstruction. No estimate overrides wheelchair restrictions or establishes a new physical connection.

7. Use **30 seconds lift travel plus zero waiting time per lift use**, an accepted arbitrary assumption. Do not apply Tobler to a vertical lift or assign zero time from its zero horizontal length. Charge on entry to an original lift identity; its split-piece continuations are free, and a different identity incurs another 30 seconds. Non-lift travel resets lift identity. All other eligible equipment and both modes use standard Tobler.
8. For hospital costs, use horizontal network distance in metres without slope/time penalties. Do not add lift seconds to hospital metres. Transport journeys respect the selected mode's physical rules and direction constraints. Step 4 uses one shared general-network hospital distance result for both modes, as recorded in its plan; Step 3 preserves both distance graphs for inspection.
9. Verify nonnegative costs, permitted directions, crossing levels and connectivity, including stairs allowed for general mode and excluded for wheelchair mode. Report unreachable paths/targets explicitly.

Tobler was researched from the [user-supplied page](https://en.wikipedia.org/wiki/Tobler%27s_hiking_function) and [original report](https://escholarship.org/uc/item/05r820mz.pdf). Standard walking speed is about 5.04 km/h at zero slope. Its walking curve is adopted as the shared assumption for both modes.

## 3. Connect estates and facilities to the graph — implemented and verified

### Explanation for the team

Connections preserve each supplied 2D map point and place an attachment on an eligible ordinary path. Outdoor paths are preferred; indoor paths are a flagged fallback. Straight flat connectors are accepted approximations, with preferred search/warning thresholds of 200 m for estates/hospitals/MTR and 50 m for buses. If no suitable in-threshold path exists, allow and flag a farther connection under the current Step 3 plan; distance alone does not reject it. Derived attachment points have original interpolated HKPD heights; facility heights remain unknown.

### Completed actions

1. [X] Freeze and verify the successful Step 2 and referenced Step 1 inputs and policies. Preserve all 10,163 original points and destination flags, including exclusions.
2. [X] Select one closest suitable source position per mode and relevant metric, retaining segment identity for repeated visits. Exclude bridges, tunnels, stairs and equipment interiors from automatic attachment; retain them for subsequent routing where permitted.
3. [X] Record indoor fallback, unknown levels, exact ties, near alternative heights/floors, long connectors and unattached reasons. Count horizontal distance and flat Tobler time; save zero-distance mappings without degenerate lines.
4. [X] Collect all selections, reuse eligible same-source nodes within the existing tolerances, then subdivide original pieces without new cross-path junctions. Verify original profile evidence and preserve directional costs, samples, availability and lift identities.
5. [X] Compile four primary augmented graphs and two baseline time graphs with outgoing estate terminals and incoming destination terminals accepting lift states. Preserve distinct coincident identities and prevent shortcuts through facility terminals.
6. [X] Validate all point records, spatial/null/cost roundtrips, terminals, shortest paths, components and frozen hashes before selecting the successful Step 2/Step 3 pair through `outputs/rebuild/current.json` (stage `current` links remain for compatibility).

Read [the completed Step 3 plan](step_3/step_3_plan.md), [implementation/API guide](step_3/step_3_implementation.md) and [full-data validation](../precomputed/outputs/step_3/current/validation_report.md). Step 4 now caches estate subcosts and comparisons; final ranking remains deferred.

## 4. Compute and cache the three subcosts — implemented and verified

1. [X] Freeze one verified Step 2/3 pair, including exact manifests, policies, approved fallback evidence and upstream reference. Consume all five saved graphs with each scenario's own attachments and terminals.
2. [X] Run 488 primary transport searches, 488 baseline transport searches and 44 reverse general-distance hospital searches. Inspect all attached eligible destinations, retaining every exactly tied minimum and full numeric precision.
3. [X] Save all 10,736 shared hospital pairs, 976 primary transport-group results, 976 baseline group results and baseline comparisons to every primary winner, including unavailable outcomes.
4. [X] Retain shared pruned predecessor links for all required paths. Preserve permitted directions, equipment restrictions, lift charges, original XYZ, 2D connectors, zero movements, review/failure evidence and connector warnings. Expanded connections retain their saved costs and eligibility.
5. [X] Compare group minima/winner sets and baseline journeys to the primary-winning targets. Identify physical paths independently of scenario labels, and report attachment changes separately from actual estimated traversal time.
6. [X] Provide GeoDataFrame readers for the 244 estates, all hospital pairs, both comparison tables and ordered cached routes. Hospital selection and wheelchair/scenario changes require no new search. Default readers reject incompatible selected pairs; explicit saved directories reopen history.
7. [X] Validate every reachable cached path, check reverse hospital results against independent forward searches, exercise readers with Dijkstra disabled and run repository/upstream regressions. Publish staged successful outputs with frozen references, manifests and Git LFS rules, retaining prior selections on failure.
8. [X] Apply the two snapshot-pinned hospital-only origin overrides for Kwai Luen and Chun Shek using existing ordinary outdoor nodes. Recalculate their 88 pairs with two forward searches, count new map-point connectors, preserve original attachments/unknown heights and leave all graph, transport and other hospital records unchanged. Keep Kam Peng unavailable; no boat link is added.

Read [the completed Step 4 plan](step_4/step_4_plan.md), [reader and artifact guide](step_4/step_4_implementation.md), [full-data report](../precomputed/outputs/step_4/current/validation_report.json) and [repository test results](../precomputed/docs/step_4_tests.txt). Unreachable costs remain missing with explicit reasons; their agreed Step 5 treatment is documented below.

## 5. Combine and rank — plan agreed, implementation pending

Explanation for the team: each midpoint gives 50 points; it is not a journey limit. A hospital 10 km away receives about 66.67 points and remains eligible. The bounded function compresses differences between very large costs, so retain original times/distances. Smaller final costs mean better access. Step 5 reads saved Step 4 measurements without new routing. Kam Peng remains visible with unavailable hospital access; boat links are outside this pedestrian-only model.

1. [X] Agree `scaled_cost = 100*x/(x+k)`, using bus/MTR/hospital midpoints 600 seconds / 900 seconds / 5,000 metres, fixed across modes, scenarios, filters and hospital selections.
2. [X] Agree equal-thirds default weights. Configurable nonnegative finite weights are normalised to sum to one; at least one must be positive. Only positive-weight components are required for a total.
3. [X] Agree complete-first ordering; incomplete estates follow by descending available-required count, then name/ID. Their total cost and numerical rank stay missing.
4. [ ] Implement full-precision scaling and weighted costs in GeoDataFrames, preserving raw measurements, destination ties, reasons, warnings and selected hospital identity. Keep valid zeros and explicit missing routes separate.
5. [ ] Filter estates by allocation category and rank within the result using exact unrounded total-cost competition ties (`1,2,2,4`). Keep scaling independent of filtering.
6. [ ] Save and verify versioned spatial ranking outputs with frozen Step 4 provenance, scoring policy and readers; use existing NumPy/pandas/GeoPandas/Pyogrio. No additional package is needed.

See [the Step 5 plan](step_5/step_5_plan.md) for explanations, interfaces, defaults and tests. The plan is written; ranking code and outputs remain unimplemented.

## Remaining evidence and implementation boundaries

Physical MTR identity matching is resolved. The user accepts the existing 276 mobility access points as the complete wheelchair MTR target pool, including the three equipment-description differences; additional mobility coverage and exact ramp/lift reconciliation are not prerequisites. Facility IDs 70/888, unnamed codes and unlocated descriptions remain preserved source unknowns; do not invent identities or coordinates. Missing terminal/floor/building references are accepted non-blocking limitations with no required investigation. Missing site and distance-post/path references remain separate findings. Castle Peak Hospital's latest-amendment selection is implemented in the frozen Step 1 snapshot. Current allocation categories are complete; new estates require verification because the lookup uses documented geographic proxies.

Step 1 prepares and preserves data and agreed candidate selections. It does not establish connected accessible journeys, execute the signed-gradient sampling/Tobler routing model, calculate the three subcosts or produce a final ranked list. Continue with later stages using the current context and saved policy, keeping unresolved items unchecked.
