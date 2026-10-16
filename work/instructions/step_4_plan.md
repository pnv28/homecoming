# Step 4: calculate and cache estate journey costs and paths

## 1. Purpose and settled decisions

Explanation for the team

Step 3 connected estates and destinations to the pedestrian network. Step 4 calculates journeys using those saved connections.

For each estate, we will save:

| Result | What we calculate and cache |
|---|---|
| Hospitals | Distance and path to each of the 44 hospitals |
| Bus | Minimum walking time and paths to all equally nearest eligible stops |
| MTR | Minimum walking time and paths to all equally nearest eligible access points |

“Nearest” means lowest network cost, including connectors. It does not mean shortest straight-line distance.

Recorded decisions

- [x] Calculate both general and wheelchair modes.
- [x] Cache costs and actual paths.
- [x] Preserve every destination tied for minimum cost, without choosing a preferred winner.
- [x] Keep hospital distances, bus times and MTR times separate.
- [x] Leave the final combining formula and estate ranking to Step 5.

There will be 21,472 estate–hospital results: 244 estates × 44 hospitals × two modes. Unreachable pairs remain recorded.

For each destination, save one valid optimal path. Returning all tied destinations does not require enumerating every alternative path to the same destination.

## 2. Freeze inputs and calculate costs

Explanation for the team

We will reuse the verified Step 3 graphs and established cost rules. Step 4 will not move points, change connections or reinterpret gradients.

SciPy already provides Dijkstra’s algorithm and the information needed to recover paths. Local feasibility checks passed, including hospital searches performed backwards through the directed graph. No additional dependency is currently required. SciPy documentation (https://docs.scipy.org/doc/scipy-1.13.1/reference/generated/scipy.sparse.csgraph.dijkstra.html)

Steps we will take

1. [ ] Freeze Step 3 run 20261014T145819Z-4d15d1a3, its policies and referenced upstream snapshots. Verify success records, required files and hashes.
2. [ ] Load the four routing matrices and their terminal/transition mappings. Use all 244 estates; allocation-category filtering remains later work.
3. [ ] Preserve existing destination eligibility, wheelchair restrictions, directions, connector costs and lift states. Do not repeat point attachment.
4. [ ] For transport, run directed Dijkstra once from each estate terminal in each mode’s time graph.
5. [ ] Inspect every eligible attached bus and MTR destination’s resulting cost. Find each group’s minimum finite cost and preserve all destinations with exactly that unrounded value.
6. [ ] Keep bus and MTR results separate. Include walking and connector time only; do not add vehicle journeys, service waiting or fares.
7. [ ] For hospitals, run Dijkstra from each hospital terminal through the transposed distance matrix. This efficiently calculates estate-to-hospital distances while respecting original travel directions.
8. [ ] Populate every estate–hospital pair from those searches. Reconstruct paths in the original estate-to-hospital direction.
9. [ ] Keep full numerical precision in caches. Display rounding must not change destination selection or create ties.

This requires 488 transport searches and 88 hospital searches, rather than a separate search for every pair.

## 3. Save paths and handle unavailable journeys

Explanation for the team

Dijkstra records links showing how an optimal path reaches each position. Many journeys share sections, so we can save those links once and reference Step 3’s existing path geometry.

Opening a cached route will assemble its saved sections without running Dijkstra again.

An unavailable journey needs an explicit explanation. It must never be represented as a zero-cost journey.

Steps we will take

1. [ ] Retain predecessor links needed by all cached hospital routes and all tied nearest transport routes. Remove branches unused by those results.
2. [ ] Save shared links as compressed numeric arrays, indexed by routing state and linked to the exact frozen graph. Use NumPy’s existing compression support. NumPy documentation (https://numpy.org/doc/2.0/reference/generated/numpy.savez_compressed.html)
3. [ ] Save a route index connecting each reachable estate/destination/mode result to its saved path links.
4. [ ] Reuse the existing examples’ transition-to-path reconstruction approach, adapting it to frozen Step 3 terminals rather than attaching coordinates again.
5. [ ] Recover ordered sections with their source IDs, edge IDs, direction, distance, applicable cost, lift identity and connector identity.
6. [ ] For time routes, use actual routing-transition costs. Continuing the same lift identity must remain free; entering another lift must retain its 30-second charge.
7. [ ] For hospital routes, report distance in metres. Do not add lift seconds or describe a distance-optimal path as the fastest path.
8. [ ] Preserve original XYZ network geometry and 2D connector geometry when returning route GeoDataFrames. Do not invent connector heights. Keep zero-distance movements explicit even when they have no drawable line.
9. [ ] Record unavailable results with a null cost, no route and an explicit status/reason: origin unattached, destination unattached, no eligible/attached destination, or no directed route.
10. [ ] Preserve relevant estate and destination attachment warnings, including level uncertainty, indoor fallback and long connectors. Keep path-source references available for further inspection.

Reachable zero-cost journeys remain valid. Infinity may be used internally during routing, but published result tables use null costs and explicit statuses for unavailable journeys.

## 4. Results, interfaces and publication

Explanation for the team

The output should support both the future ranking calculation and inspection of individual journeys.

Choosing a hospital later will select its cached result. Leaving hospital selection empty will use the minimum reachable distance among all 44, preserving all tied hospitals.

Steps we will take

1. [ ] Provide these public readers, with an optional saved-run directory:
   - read_subcosts(wheelchair=False, hospital_id=None): return a 244-row estate GeoDataFrame with the three separate subcosts, destination IDs, units, statuses and warnings.
   - read_hospital_costs(wheelchair=False): return all 10,736 estate–hospital results for that mode as a GeoDataFrame using estate point geometry.
   - read_route(estate_id, target_id, wheelchair=False): return the cached journey’s ordered route-section GeoDataFrame.
2. [ ] Return all tied destination IDs in stable ID order for reproducible output, without designating a preferred destination.
3. [ ] Allow hospital route retrieval for every reachable cached pair. Allow bus/MTR route retrieval for every tied nearest destination.
4. [ ] Return an empty route GeoDataFrame with status information for a recorded unavailable journey. Reject unknown IDs and requests for transport destinations outside the cached nearest set; do not silently calculate a new journey.
5. [ ] Save estate summaries, hospital-pair results and tied transport destinations in GeoPackage layers. Serialize ID collections explicitly and restore them through the public reader.
6. [ ] Save compressed path links, route mappings, policies, manifests, frozen references and validation reports under work/precomputed/outputs/step_4/, with runs/ and a current selection.
7. [ ] Reference retained Step 3 geometry instead of duplicating the complete network.
8. [ ] Stage and validate a candidate run before selecting it. Failures preserve the previous successful selection and leave upstream outputs unchanged.
9. [ ] Update the Step 4 instructions, project context and overall design. Separate explanations from implementation actions and tick only completed work.
10. [ ] Refresh the context’s last-updated timestamp in HKT, including seconds. Keep successful artifacts trackable, applying Git LFS conventions where appropriate. Do not automatically commit or push.

No final score, weights, normalisation or penalty for unreachable groups will be introduced.

## 5. Tests and acceptance

Explanation for the team

We must establish that saved numbers agree with the saved paths, direction rules remain intact, and later reads use the cache.

Checks we will complete

- [ ] Verify directed asymmetric costs, one-way paths, both wheelchair modes and connector inclusion.
- [ ] Verify all 44 hospital columns and switching hospital preference without rerouting.
- [ ] Compare reversed hospital searches against forward estate searches on representative cases.
- [ ] Verify all exactly tied destinations survive, while unequal unrounded costs remain distinct.
- [ ] Cover unreachable destinations, wholly unreachable groups, unattached points and valid zero-cost journeys.
- [ ] Verify path direction, original geometry references, lift entry/continuation charges and no shortcuts through terminals.
- [ ] Check every cached reachable path’s permitted transitions and summed cost against its result.
- [ ] Detect broken links, missing transitions, predecessor cycles and incompatible graph references.
- [ ] Verify exact save/reopen preservation of costs, identities, statuses, warnings and path links.
- [ ] Confirm cached result and route readers work with Dijkstra disabled.
- [ ] Run the existing repository tests and relevant upstream regressions.

Full-data acceptance must account for all 21,472 hospital pairs, all 976 estate/mode/transport-group results, and every tied transport winner. Report reachability, tie counts, route counts, warnings, runtime and storage size.

Select a successful run only after required integrity checks pass. Accepted source assumptions and genuine unreachable journeys remain visible in the results.