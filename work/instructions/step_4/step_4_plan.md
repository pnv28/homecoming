# Step 4: cache estate journey costs and paths

## 1. Purpose and agreed rules

Explanation for the team

Step 4 uses Step 3’s saved connections to calculate the following:

| Result | Calculation | Modes |
|---|---|---|
| Hospital | Distance and path to each of the 44 hospitals | One shared general-walking model |
| Bus | Minimum walking time and paths to every equally nearest eligible stop | General and wheelchair |
| MTR | Minimum walking time and paths to every equally nearest eligible access point | General and wheelchair |

The hospital result is a shared proximity measure using the general pedestrian network. Changing the wheelchair parameter changes bus and MTR calculations, while hospital distances and paths remain identical.

Recorded decisions

- [x] Cache 10,736 hospital results: 244 estates × 44 hospitals.
- [x] Calculate transport results separately for general and wheelchair users.
- [x] Save costs and actual paths.
- [x] Preserve all destinations tied for minimum cost, without selecting a preferred winner.
- [x] Keep the three subcosts separate; combining and ranking remain Step 5.

“Nearest” means minimum network cost, including connectors. Save one optimal path per destination; do not enumerate every alternative path to that destination.

## 2. Reuse existing tools and calculate costs

Explanation for the team

walking_route.py already reconstructs ordered path sections, handles connector geometry and lift costs, and checks that section costs equal the journey total. We will extract reusable reconstruction logic into the package and keep the example working.

We will use SciPy’s existing Dijkstra implementation, which accepts our sparse matrices and returns path predecessors. NumPy handles compressed storage; GeoPandas, Shapely and Pyogrio handle spatial results. SciPy documentation (https://docs.scipy.org/doc/scipy-1.13.1/reference/generated/scipy.sparse.csgraph.dijkstra.html)

I also checked NetworkX and OSMnx. Their documented routing functions provide overlapping capabilities, but adapting our existing matrices and lift states offers no identified benefit here. No additional dependency is currently required. NetworkX (https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.shortest_paths.weighted.single_source_dijkstra.html), OSMnx (https://osmnx.readthedocs.io/en/stable/user-reference.html#osmnx.routing.route_to_gdf)

Steps we will take

1. [ ] Freeze the successful Step 2/Step 3 pair selected by `precomputed/outputs/rebuild/current.json`, its policies, parameters and required upstream references. Verify success records and hashes; do not use the old pre-fallback Step 3 snapshot for new caches.
2. [ ] Load primary and baseline general/wheelchair time matrices plus the shared general distance matrix, with scenario-specific state, terminal and transition mappings. Baseline excludes fallback intervals and uses its own attachments under the same connector policy.
3. [ ] Use all 244 estates. Preserve existing connections, directions, transport eligibility, connector costs and lift identities. Do not attach points again.
4. [ ] Record the shared hospital model as an explicit Step 4 policy overriding the earlier two-mode hospital calculation. Leave frozen upstream policies unchanged.
5. [ ] For transport, run directed Dijkstra from each estate terminal in each mode and time scenario. Preserve the approved 6 s/m ascent and 2 s/m descent fallback as an explicit approximation in both modes; do not recompute or replace upstream costs.
6. [ ] Inspect every eligible attached bus/MTR destination in each scenario. Cache each group’s minimum finite time and all exactly tied destinations. Also cache baseline costs/paths to primary-winning destinations for a like-for-like journey comparison; baseline group winners may be different targets. Preserve model/review warnings and source failures on estimated route sections.
7. [ ] Include walking and connector time only. Do not add vehicle journeys, service waiting or fares.
8. [ ] For hospitals, search from each hospital terminal through the transposed general-distance matrix. Recover estate-to-hospital paths in the original direction.
9. [ ] Populate all estate–hospital pairs once. Do not use wheelchair-distance connections or create a second hospital cache.
10. [ ] Preserve full precision; rounding for display must not change selection.

This requires 488 primary transport searches, 488 baseline transport searches and 44 shared hospital searches: **1,020 searches total**. The additional same-target comparisons use those existing search results, not new Dijkstra calls.

## 3. Save paths and explain unavailable results

Explanation for the team

Dijkstra’s predecessor links describe the calculated paths. Shared sections can be stored once and combined with Step 3’s saved geometry. Retrieving a cached route will not require another routing calculation.

Steps we will take

1. [ ] Retain predecessor links needed by every reachable hospital pair and every tied nearest transport destination. Remove unused branches.
2. [ ] Store shared links as compressed numeric arrays with routing-state IDs, predecessor IDs, root identity, search direction and frozen graph references. Use NumPy’s existing compression support. NumPy documentation (https://numpy.org/doc/2.0/reference/generated/numpy.savez_compressed.html)
3. [ ] Save an index connecting cached results to their path links. Hospital entries use a shared-general model identity; transport entries retain their user mode.
4. [ ] Reuse the example’s transition lookup, path ordering, geometry reversal and cost-sum checks. Do not call its arbitrary-coordinate attachment workflow.
5. [ ] Return ordered sections containing source/edge IDs, direction, distance, applicable cost, lift identity and connector identity.
6. [ ] For time routes, use actual transition costs: same-lift continuation remains free; entering another lift retains its 30-second charge.
7. [ ] For hospital routes, sum horizontal metres. Do not add lift seconds or apply Tobler.
8. [ ] Preserve network XYZ geometry and 2D connectors in returned route GeoDataFrames. Keep zero-distance movements explicit without inventing geometry or height.
9. [ ] Record unavailable results with null costs, no route and explicit reasons: unattached origin/destination, no eligible or attached target, or no directed route.
10. [ ] Preserve attachment warnings, estimated-section identifiers, original failure reasons, selected time model and path-source references. When estimates change the chosen journey or reachability, expose the primary result, the baseline group result and the baseline path to the same primary target where available; report missing baseline routes explicitly. Hospital results identify the shared general-network model.

Valid zero-cost journeys remain distinct from unavailable journeys.

## 4. Public results and publication

Explanation for the team

Selecting a hospital will select its cached distance and path. With no hospital selected, use the minimum reachable distance among all 44 and preserve every tied hospital.

Hospital selection and wheelchair selection will not trigger new routing.

Steps we will take

1. [ ] Provide public readers with an optional saved-run directory:
   - read_subcosts(wheelchair=False, hospital_id=None): a 244-row estate GeoDataFrame containing MTR time, bus time, hospital distance, destination IDs, units, statuses and warnings.
   - read_hospital_costs(): the 10,736 shared hospital-pair results as a GeoDataFrame using estate point geometry.
   - read_route(estate_id, target_id, wheelchair=False, scenario="primary"): the cached ordered route-section GeoDataFrame. The parameter selects transport mode; hospital targets always resolve to the shared general route, identified in metadata.
2. [ ] Return tied destination IDs in stable order without designating a preferred winner.
3. [ ] Support every reachable hospital pair and every tied nearest bus/MTR destination.
4. [ ] Return an empty route with status information for a recorded unavailable journey. Reject unknown IDs and uncached transport destinations without silently rerouting.
5. [ ] Save spatial result tables in GeoPackage layers, restoring serialized ID collections through the readers.
6. [ ] Publish compressed links, mappings, policies, manifests and reports under work/precomputed/outputs/step_4/, using staged runs and a successful current selection.
7. [ ] Reference retained Step 3 geometry instead of duplicating the network. Failed builds preserve the previous selection and upstream outputs.
8. [ ] Update work/instructions/step_4/step_4_plan.md, the project context and overall design consistently: one hospital model, five input graphs, 44 hospital searches, 10,736 hospital pairs, primary/baseline time comparisons and revised interfaces.
9. [ ] Refresh the context timestamp in HKT, including seconds. Mark only completed implementation [X].
10. [ ] Keep successful outputs tracked with appropriate Git LFS rules. Do not automatically commit or push.

Final weights, normalisation, ranking and penalties for unreachable groups remain undecided.

## 5. Tests and acceptance

Checks we will complete

- [ ] Verify directed costs, connector inclusion, transport eligibility and lift charges in each time scenario. Test primary-winner versus baseline-winner changes, unavailable baseline paths, exact ties and estimated-section warnings.
- [ ] Verify hospital costs, paths and statuses are identical under both user-mode requests and use general-mode connections.
- [ ] Verify all 44 hospitals and hospital selection without rerouting.
- [ ] Compare reversed hospital searches with forward estate searches.
- [ ] Preserve every exactly tied destination while distinguishing unequal unrounded costs.
- [ ] Cover unreachable groups, unattached points and valid zero costs.
- [ ] Check every cached reachable path’s direction, permitted transitions and summed cost.
- [ ] Detect broken predecessor links, cycles, missing transitions and incompatible graph references.
- [ ] Verify save/reopen preservation and GeoDataFrame outputs.
- [ ] Confirm result and route retrieval work with Dijkstra disabled.
- [ ] Keep walking_route.py working after extracting shared logic.
- [ ] Run repository tests and relevant upstream regressions.

Full-data acceptance must account for 10,736 shared hospital pairs, 976 primary transport-group results, 976 baseline transport-group results, every tied winner and baseline comparisons to primary-winning destinations. Report reachability, warnings, route counts, runtime and storage size before selecting the successful run.