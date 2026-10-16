 
 
# Revised Step 4: cache journey costs, paths and estimate comparisons

This replaces the Step 4 draft to match the completed Step 2/3 rebuild. Step 4 remains unimplemented. The text has not been saved because this session is in Plan Mode.

## 1. Purpose and settled rules

Explanation for the team

We will calculate the following from the rebuilt network:

| Result | Calculation | Modes |
|---|---|---|
| Hospital | Distance and path to every supplied hospital | One shared general-walking model |
| Bus | Minimum walking time and paths to all equally nearest eligible stops | General and wheelchair |
| MTR | Minimum walking time and paths to all equally nearest eligible access points | General and wheelchair |

Transport calculations now have two scenarios:

- Primary: healthy Tobler costs plus approved distance-and-height estimates.
- Baseline: estimates excluded, using the separately prepared baseline connections.

Both scenarios use the updated connector policy. The old October 14 graph is historical evidence, not the baseline for these comparisons.

Recorded decisions

- [x] Cache 10,736 shared hospital results: 244 estates × 44 hospitals.
- [x] Save transport costs and paths for both modes and scenarios.
- [x] Preserve every exactly tied nearest destination without choosing a preferred winner.
- [x] Use the implemented fallback allowances: 6 seconds per metre uphill and 2 seconds per metre downhill, including wheelchair-eligible paths as an explicit approximation.
- [x] Keep hospital distances unchanged by fallback or wheelchair selection.
- [x] Keep the three subcosts separate; final combination and ranking remain Step 5.

Save one optimal path per cached destination, without enumerating every alternative path to that destination.

## 2. Freeze the rebuilt inputs and reuse existing tools

Explanation for the team

Steps 2 and 3 now publish a compatible pair through one registry. Reading that record once prevents a cache from accidentally combining different builds.

Step 3 already supplies both scenarios’ connections and costs. Step 4 must consume them rather than repeat attachment selection or change routing rules.

Steps we will take

- [ ] Read and freeze one record from work/precomputed/outputs/rebuild/current.json. The currently selected pair is Step 2 20261016T075559Z-119a5636 and Step 3 20261016T080509Z-4c604c82.
- [ ] Verify success records, manifest hashes, relevant artifacts, policies, fallback review and Step 3’s exact upstream reference.
- [ ] Load five graphs: primary/baseline general time, primary/baseline wheelchair time, and general distance.
- [ ] Match terminals across scenarios by entity identity. Do not assume numeric state indices or attachment positions are interchangeable.
- [ ] Preserve all directions, equipment restrictions, barriers, lift identities and original failure evidence.
- [ ] Accept saved beyond-threshold connections and their costs. The 200 m/50 m values are now search/warning thresholds; Step 4 must not reinstate hard rejection limits.
- [ ] Reuse SciPy Dijkstra, NumPy compression, GeoPandas, Shapely and Pyogrio. No additional package is currently needed.
- [ ] Extract reusable reconstruction logic from walking_route.py: predecessor traversal, transition lookup, ordered geometry and cost checks. Keep its example working; do not invoke its arbitrary-coordinate attachment workflow.

## 3. Calculate costs and explain scenario differences

Explanation for the team

Two comparisons answer different questions:

1. Group comparison: does allowing estimates change the nearest bus/MTR destination or its minimum time?
2. Same-target comparison: how would we reach the primary-winning destination with estimates excluded?

For example, primary routing might choose MTR exit A, while baseline routing chooses exit B. We must report both results and also the baseline journey to A, if one exists.

Steps we will take

- [ ] Run directed Dijkstra from each estate in each transport mode/scenario.
- [ ] Inspect every eligible attached bus/MTR destination. Save each group’s minimum finite cost and all destinations with exactly that unrounded value.
- [ ] Cache primary winners, baseline winners, and baseline results to every primary-winning destination, including explicit unavailable outcomes.
- [ ] Use the baseline graph’s own terminal and attachment mappings. Removing estimated edges from the primary attached graph is not an equivalent comparison.
- [ ] Record changes in minimum cost, reachability, tied destination sets, selected paths and attachment positions.
- [ ] Compare path identities using original sections, directions and actual connector positions. Scenario labels alone must not count as a changed path.
- [ ] Record whether each selected primary path actually traverses estimated sections. Preserve review IDs, original failure reasons, model warnings and estimated seconds.
- [ ] Expose attachment changes separately; do not describe every scenario difference as solely an estimated traversal-time effect.
- [ ] Include walking and connector time only, without vehicle travel, waiting or fares.
- [ ] Calculate hospital distances through the transposed general-distance graph, once per hospital, recovering estate-to-hospital paths in the original direction.
- [ ] Preserve full numerical precision. Use exact unrounded equality for destination ties.

The planned calculation remains 488 primary transport searches + 488 baseline transport searches + 44 hospital searches = 1,020 searches. Same-target comparisons reuse those search results.

## 4. Cache paths and provide GeoDataFrame readers

Explanation for the team

Saved predecessor links encode the calculated paths. We will retain shared links once and reference the frozen Step 3 geometry. Reading a cached result or path will not run Dijkstra again.

Steps we will take

- [ ] Retain links for every reachable hospital pair, all primary and baseline transport winners, and all reachable baseline comparisons to primary winners. Include these comparison routes before pruning unused branches.
- [ ] Save compressed numeric links with graph, mode, scenario, root identity and search direction. Deduplicate repeated route records while preserving their purposes.
- [ ] Return ordered route sections with source/edge IDs, direction, distance, applicable cost, connector identity and model provenance.
- [ ] Use actual scenario-specific transition costs. Baseline routes must not be labelled estimated merely because their physical source has fallback evidence.
- [ ] Preserve lift entry, continuation and re-entry charges. Hospital routes contain distance costs without adding lift seconds or Tobler time.
- [ ] Preserve network XYZ and 2D connector geometry without inventing heights. Represent zero-distance movements explicitly.
- [ ] Publish unavailable costs as null with clear reasons and no route. Valid zero costs remain valid results.
- [ ] Carry connector warnings into results, including expanded searches, actual connector distances, uncertain levels and indoor fallback. Do not silently discard long connectors or their destinations.

Public interfaces

- read_subcosts(wheelchair=False, hospital_id=None, scenario="primary") returns a 244-row estate GeoDataFrame with the three separate subcosts, tied destination IDs, units, statuses and warnings.
- read_hospital_costs() returns the 10,736 shared hospital-pair results as a GeoDataFrame.
- read_transport_comparisons(wheelchair=False) returns group-comparison and same-target-comparison GeoDataFrames.
- read_route(estate_id, target_id, wheelchair=False, scenario="primary") returns cached ordered route sections.

All readers accept an optional saved-run directory. Hospital requests always resolve to the shared general-distance cache, identified in metadata. With no hospital selected, return the minimum reachable distance among all 44 and every tied hospital.

Baseline route retrieval must support both baseline winners and primary-winner comparison destinations. Unknown IDs and uncached transport requests produce explicit errors without rerouting; recorded unavailable journeys return an empty route with status information.

## 5. Documentation, validation and publication

Steps we will take

- [ ] Rework work/instructions/step_4/step_4_plan.md around the selected pair, scenario-specific attachments, expanded connector policy and complete comparison caching.
- [ ] Update the context and overall design consistently. Refresh documentation timestamps using actual HKT date and time. Keep unfinished Step 4 actions unchecked.
- [ ] Save spatial tables, compressed links, mappings, policies, manifests and reports under work/precomputed/outputs/step_4/, with staged runs and a successful current selection.
- [ ] Pin retained upstream directories rather than mutable links. Verify the selected pair has not changed before publishing the cache.
- [ ] Have default readers detect an incompatible selected pair; permit explicit reopening of historical caches with their frozen references.
- [ ] Preserve prior selections on failure. Keep successful outputs tracked with appropriate Git LFS rules. Do not automatically commit, push or delete historical outputs.

Tests and acceptance

- [ ] Verify both modes/scenarios, directed costs, connector inclusion and lift charges.
- [ ] Test primary/baseline winner changes, tied destinations, unavailable comparisons and differences in attachment selection.
- [ ] Verify expanded connectors remain eligible, fully charged and visibly flagged.
- [ ] Verify estimated-section provenance and preservation of original failure diagnostics.
- [ ] Verify hospital results remain identical under either user mode and compare reverse searches against forward searches.
- [ ] Check every reachable cached path’s permitted transitions and summed cost.
- [ ] Detect missing comparison links after pruning, predecessor cycles and incompatible references.
- [ ] Verify save/reopen preservation and GeoDataFrame outputs.
- [ ] Confirm all result, comparison and route readers work with Dijkstra disabled.
- [ ] Keep walking_route.py functional and run repository tests and relevant upstream regressions.

Full-data acceptance must account for 10,736 hospital pairs, 976 primary transport-group results, 976 baseline transport-group results, every tied winner and every baseline comparison to a primary winner. Report reachability, estimated-route usage, comparison changes, connector warnings, runtime and storage size.

Final scoring, normalisation, weights and penalties for unreachable groups remain deferred.