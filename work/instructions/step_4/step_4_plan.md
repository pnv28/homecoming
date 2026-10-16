# Revised Step 4: cache journey costs, paths and estimate comparisons

Implemented against the selected 16 October Step 2/3 pair. See [the implementation and reader guide](step_4_implementation.md) and [the selected validation report](../../precomputed/outputs/step_4/current/validation_report.json).

Updated 2026-10-16 20:32:37 HKT (UTC+08:00).

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

- [X] Cache 10,736 shared hospital results: 244 estates × 44 hospitals.
- [X] Save transport costs and paths for both modes and scenarios.
- [X] Preserve every exactly tied nearest destination without choosing a preferred winner.
- [X] Use the implemented fallback allowances: 6 seconds per metre uphill and 2 seconds per metre downhill, including wheelchair-eligible paths as an explicit approximation.
- [X] Keep hospital distances unchanged by fallback or wheelchair selection.
- [X] Keep the three subcosts separate; final combination and ranking remain Step 5.

Save one optimal path per cached destination, without enumerating every alternative path to that destination.

## 2. Freeze the rebuilt inputs and reuse existing tools

Explanation for the team

Steps 2 and 3 now publish a compatible pair through one registry. Reading that record once prevents a cache from accidentally combining different builds.

Step 3 already supplies both scenarios’ connections and costs. Step 4 must consume them rather than repeat attachment selection or change routing rules.

Steps we will take

- [X] Read and freeze one record from work/precomputed/outputs/rebuild/current.json. The currently selected pair is Step 2 20261016T075559Z-119a5636 and Step 3 20261016T080509Z-4c604c82.
- [X] Verify success records, manifest hashes, relevant artifacts, policies, fallback review and Step 3’s exact upstream reference.
- [X] Load five graphs: primary/baseline general time, primary/baseline wheelchair time, and general distance.
- [X] Match terminals across scenarios by entity identity. Do not assume numeric state indices or attachment positions are interchangeable.
- [X] Preserve all directions, equipment restrictions, barriers, lift identities and original failure evidence.
- [X] Accept saved beyond-threshold connections and their costs. The 200 m/50 m values are now search/warning thresholds; Step 4 must not reinstate hard rejection limits.
- [X] Reuse SciPy Dijkstra, NumPy compression, GeoPandas, Shapely and Pyogrio. No additional package is currently needed.
- [X] Extract reusable reconstruction logic from walking_route.py: predecessor traversal, transition lookup, ordered geometry and cost checks. Keep its example working; do not invoke its arbitrary-coordinate attachment workflow.

## 3. Calculate costs and explain scenario differences

Explanation for the team

Two comparisons answer different questions:

1. Group comparison: does allowing estimates change the nearest bus/MTR destination or its minimum time?
2. Same-target comparison: how would we reach the primary-winning destination with estimates excluded?

For example, primary routing might choose MTR exit A, while baseline routing chooses exit B. We must report both results and also the baseline journey to A, if one exists.

Steps we will take

- [X] Run directed Dijkstra from each estate in each transport mode/scenario.
- [X] Inspect every eligible attached bus/MTR destination. Save each group’s minimum finite cost and all destinations with exactly that unrounded value.
- [X] Cache primary winners, baseline winners, and baseline results to every primary-winning destination, including explicit unavailable outcomes.
- [X] Use the baseline graph’s own terminal and attachment mappings. Removing estimated edges from the primary attached graph is not an equivalent comparison.
- [X] Record changes in minimum cost, reachability, tied destination sets, selected paths and attachment positions.
- [X] Compare path identities using original sections, directions and actual connector positions. Scenario labels alone must not count as a changed path.
- [X] Record whether each selected primary path actually traverses estimated sections. Preserve review IDs, original failure reasons, model warnings and estimated seconds.
- [X] Expose attachment changes separately; do not describe every scenario difference as solely an estimated traversal-time effect.
- [X] Include walking and connector time only, without vehicle travel, waiting or fares.
- [X] Calculate hospital distances through the transposed general-distance graph, once per hospital, recovering estate-to-hospital paths in the original direction.
- [X] Preserve full numerical precision. Use exact unrounded equality for destination ties.

The original core calculation is 488 primary transport searches + 488 baseline transport searches + 44 hospital searches = 1,020 searches. Same-target comparisons reuse those results. The reviewed hospital-origin amendment in Section 6 adds two forward searches; amendment-only builds reuse the core results instead of repeating them.

## 4. Cache paths and provide GeoDataFrame readers

Explanation for the team

Saved predecessor links encode the calculated paths. We will retain shared links once and reference the frozen Step 3 geometry. Reading a cached result or path will not run Dijkstra again.

Steps we will take

- [X] Retain links for every reachable hospital pair, all primary and baseline transport winners, and all reachable baseline comparisons to primary winners. Include these comparison routes before pruning unused branches.
- [X] Save compressed numeric links with graph, mode, scenario, root identity and search direction. Deduplicate repeated route records while preserving their purposes.
- [X] Return ordered route sections with source/edge IDs, direction, distance, applicable cost, connector identity and model provenance.
- [X] Use actual scenario-specific transition costs. Baseline routes must not be labelled estimated merely because their physical source has fallback evidence.
- [X] Preserve lift entry, continuation and re-entry charges. Hospital routes contain distance costs without adding lift seconds or Tobler time.
- [X] Preserve network XYZ and 2D connector geometry without inventing heights. Represent zero-distance movements explicitly.
- [X] Publish unavailable costs as null with clear reasons and no route. Valid zero costs remain valid results.
- [X] Carry connector warnings into results, including expanded searches, actual connector distances, uncertain levels and indoor fallback. Do not silently discard long connectors or their destinations.

Public interfaces

- read_subcosts(wheelchair=False, hospital_id=None, scenario="primary") returns a 244-row estate GeoDataFrame with the three separate subcosts, tied destination IDs, units, statuses and warnings.
- read_hospital_costs() returns the 10,736 shared hospital-pair results as a GeoDataFrame.
- read_transport_comparisons(wheelchair=False) returns group-comparison and same-target-comparison GeoDataFrames.
- read_route(estate_id, target_id, wheelchair=False, scenario="primary") returns cached ordered route sections.

All readers accept an optional saved-run directory. Hospital requests always resolve to the shared general-distance cache, identified in metadata. With no hospital selected, return the minimum reachable distance among all 44 and every tied hospital.

Baseline route retrieval must support both baseline winners and primary-winner comparison destinations. Unknown IDs and uncached transport requests produce explicit errors without rerouting; recorded unavailable journeys return an empty route with status information.

## 5. Documentation, validation and publication

Steps we will take

- [X] Rework work/instructions/step_4/step_4_plan.md around the selected pair, scenario-specific attachments, expanded connector policy and complete comparison caching.
- [X] Update the context and overall design consistently. Refresh documentation timestamps using actual HKT date and time. Keep unfinished Step 4 actions unchecked.
- [X] Save spatial tables, compressed links, mappings, policies, manifests and reports under work/precomputed/outputs/step_4/, with staged runs and a successful current selection.
- [X] Pin retained upstream directories rather than mutable links. Verify the selected pair has not changed before publishing the cache.
- [X] Have default readers detect an incompatible selected pair; permit explicit reopening of historical caches with their frozen references.
- [X] Preserve prior selections on failure. Keep successful outputs tracked with appropriate Git LFS rules. Do not automatically commit, push or delete historical outputs.

Tests and acceptance

- [X] Verify both modes/scenarios, directed costs, connector inclusion and lift charges.
- [X] Test primary/baseline winner changes, tied destinations, unavailable comparisons and differences in attachment selection.
- [X] Verify expanded connectors remain eligible, fully charged and visibly flagged.
- [X] Verify estimated-section provenance and preservation of original failure diagnostics.
- [X] Verify hospital results remain identical under either user mode and compare reverse searches against forward searches.
- [X] Check every reachable cached path’s permitted transitions and summed cost.
- [X] Detect missing comparison links after pruning, predecessor cycles and incompatible references.
- [X] Verify save/reopen preservation and GeoDataFrame outputs.
- [X] Confirm all result, comparison and route readers work with Dijkstra disabled.
- [X] Keep walking_route.py functional and run repository tests and relevant upstream regressions.

Full-data acceptance must account for 10,736 hospital pairs, 976 primary transport-group results, 976 baseline transport-group results, every tied winner and every baseline comparison to a primary winner. Report reachability, estimated-route usage, comparison changes, connector warnings, runtime and storage size.

Step 5 decisions are now recorded: bounded component costs `100*x/(x+k)` with bus/MTR/hospital midpoints 600 seconds / 900 seconds / 5,000 metres, equal-thirds configurable weights, and incomplete estates after complete estates, ordered by most available required components then name/ID. Incomplete totals and numerical ranks stay missing. Step 4 does not implement these scores.

- [X] Step 5: agree final scoring, scaling, default weights and missing-route ordering; write the [Step 5 plan](../step_5/step_5_plan.md).
- [X] Step 5: implement and validate the ranking outputs; see [the implementation guide](../step_5/step_5_implementation.md).

## 6. Reviewed hospital-only amendment

Explanation for the team

Kwai Luen and Chun Shek originally connected to small isolated path groups. Nearby existing ordinary outdoor nodes connect to hospitals. The accepted correction is a hospital-only map-point connection override in Step 4; it does not add graph edges, repair source topology or change transport attachments. The estate heights/entrances remain unverified. Kam Peng remains unavailable for hospital walking routes; no boat or cross-water connector is added.

Steps we will take

- [X] Pin reviewed replacement nodes 374121 (source 120017850) and 227647 (source 290061624) to the exact selected Step 3 snapshot and verify identity, coordinates, ordinary-path eligibility and permitted departure.
- [X] Reuse the frozen general-distance matrix and run two forward hospital searches; replace only the two estates' 88 pair records and saved paths.
- [X] Save original and replacement connections separately, count the new horizontal connector distance, preserve network XYZ and unknown estate heights, and reconstruct amended routes without rerouting.
- [X] Preserve all other hospital records, all transport results/comparisons and the original Step 2/3 artifacts. Keep Kam Peng unchanged.
- [X] Save a new versioned Step 4 cache with parent provenance, checksums and explicit override warnings; retain previous runs.
- [X] Ensure future full Step 4 builds apply these same reviewed overrides against the pinned snapshot; a changed snapshot requires explicit review rather than reusing node indices silently.
- [X] Verify amended route totals and independent forward distances; test stale overrides, forbidden departures, preservation, missing selected-hospital identity and publication failure.
- [X] Step 5 scoring was implemented and verified separately from this completed amendment; source/model limitations remain preserved.
