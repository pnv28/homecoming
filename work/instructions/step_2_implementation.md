# Step 2 implementation and review

## Inputs and decisions

### Explanation for the team

This stage turns the prepared paths into connected junctions and directed path pieces. Hospitals will use metres; transport targets will use seconds. It does not yet attach estates or destinations, calculate the three journey subcosts, or combine final scores.

The current Step 2 plan supersedes older notes in the project context: both modes now use the same Tobler assumption, every non-lift path uses that function, and `Enabled=false` is excluded. These are modelling decisions. They do not establish measured wheelchair speeds or centimetre source accuracy.

### Steps we will take

- [X] Install SciPy 1.13.1 with approval in the existing `.venv`; pin it in `work/requirements.txt`.
- [X] Synchronise executable policy with the lift identity, shared Tobler, Enabled, MTR-pool and accepted-reference decisions.
- [X] Preserve both Castle Peak Hospital site versions and add `canonical_site_references` selecting record `network:PedRouteRelSitePoly:3348`, amended 13 July 2026. The 44 hospital destinations are unchanged.
- [X] Rebuild Step 1 successfully once, then resolve its current link to a fixed run directory. Step 2 records the run ID, artifact hashes, original source hashes and complete frozen policy.
- [X] Preserve existing missing-reference warnings. Site/distance-post references are unnecessary for this graph operation; future operations needing them must assess them then.

## Connections and spatial geometry

### Explanation for the team

A junction needs endpoint evidence. Two lines crossing in the middle do not automatically connect. A nearby endpoint can connect to another endpoint or split a receiving path if their horizontal and height differences satisfy the agreed limits. Known floor conflicts within the same building block inferred connections unless an incident explicit vertical-transition path supports the connection.

Exact XYZ endpoints are source-supported junctions. For inferred connections, we first identify all nearby candidate sites using Shapely's two-dimensional spatial index, then check heights and floors separately. Every pair of sites in a proposed cluster must be compatible. A connected group that fails that requirement is ambiguous: we keep its original exact endpoint groups separate. We do not pick an arbitrary side of a chain. Multiple paths at one supported junction are allowed.

Original geometries remain in `sources`. Derived edges retain their original/interpolated XYZ geometry. A node uses a deterministic representative coordinate; `memberships.csv` records each member's horizontal and signed vertical alignment correction. Corrections receive no additional distance or time cost. Small visible gaps between edge endpoints and representative node points are therefore recorded, rather than hidden by rewriting source geometry.

A source position is **original vertex index plus segment fraction**. This also identifies positions inside vertical lifts, where horizontal chainage alone would be insufficient. Source IDs and these positions determine node/edge IDs, independent of source row order.

### Steps we will take

- [X] Require EPSG:2326 and finite XYZ coordinates; persist EPSG:5738/HKPD metadata.
- [X] Enforce inclusive horizontal 0.10 m and height 0.025 m limits for inferred connections and complete accepted clusters. Height comparisons use inclusive upper bounds to avoid cancellation in subtraction; there is no added height-equality tolerance for gradient sampling.
- [X] Interpolate endpoint-to-interior positions on original segments, including vertical segments.
- [X] Preserve source-parallel paths and closed paths. Sparse routing alternatives are reduced separately.
- [X] Preserve ambiguous clusters, ambiguous repeated interior visits, floor rejections, middle crossings and XY overlaps in `review.jsonl`. Crossings never create junctions on their own.
- [X] Respect direction 0/both, 1/forward, -1/reverse. Record unsupported feature, Enabled, direction or required barrier codes as explicit exclusions. Invalid XYZ, missing/nonfinite gradients, duplicate path identities and unsupported multipart ordering fail the candidate build with diagnostics.

## Source costs and lift states

### Explanation for the team

A source profile is calculated before splitting. It retains original vertices, deterministic samples, signed gradient intervals and both travel directions. Cutting a path apportions existing interval costs; it never samples or classifies the path again.

For equal endpoint heights with a nonzero gradient, samples are uniform in original XYZ arclength. A SHA-256-derived per-`PedestrianRouteID` seed starts from 20261013. Four distinct internal positions are sampled first; a second group of four is used only if the first remains level. Comparisons use exact stored/interpolated height equality. After ten level points the model classifies the path as relatively flat; unsampled source detail can still exist. Non-flat profiles keep original vertices plus samples, with separately signed uphill, downhill and level intervals. Reverse traversal reuses the same profile and samples, reversing interval order and signs.

Every non-lift interval uses `tan(signed_gradient)` in Tobler's function. Log-space evaluation avoids overflowing intermediate speed/time calculations. Unrepresentable source-direction totals and non-lift vertical intervals without a usable horizontal run are unavailable for time routing, with a recorded reason. Their physical edges and horizontal distance routing survive. Costs are never capped and provider gradients are never replaced.

Time-routing states remember the current original lift identity. Entering a lift costs 30 seconds. Continuing pieces of that identity costs zero; entering another identity costs another 30 seconds. Traversing a non-lift edge resets the identity. Distance routing has one state per physical node and adds no lift seconds.

### Steps we will take

- [X] Preserve provider radians, derived signed angles, heights, classification, sample rounds/positions, per-interval times and status reasons in `profiles.jsonl`.
- [X] Check exact source-position coverage and conservation of each source's distance and directional time across its pieces.
- [X] Persist physical geometry separately from state tables, sparse matrices and matrix-entry-to-source-edge mappings.
- [X] Select the minimum eligible parallel cost for each ordered state pair, with deterministic ties. Preserve explicitly stored zero entries; never sum duplicate alternatives or call `eliminate_zeros`.
- [X] Start routing in a node's `lift_id=None` state and accept the minimum across destination states. `RoutingGraph.costs_from(node_index)` implements that reduction with SciPy Dijkstra.

## Interfaces, storage and validation

### Explanation for the team

`build_graph(network, wheelchair=False, metric="time")` accepts the prepared network GeoDataFrame or a successful Step 1 directory. `read_graph(directory=None, wheelchair=False, metric="time")` loads the selected saved graph. Both support `"distance"` and `"time"` and return a `RoutingGraph` with node/edge GeoDataFrames, a SciPy CSR matrix, routing states and `edge_mapping` in matrix-entry order. The physical graph also retains every original source row with its Allow/Exclude reasons.

For a full publication, run `python -m estate_ranking.step_2`. The CLI builds physical geometry once, then all four mode/metric matrices. It saves in ignored staging, reopens all spatial attributes, geometries and nulls, checks every evidence row, matrix entry and mapping, and compares deterministic shortest-path results. Input hashes are rechecked before success. Only then does an atomic link switch select the new run. A lock prevents competing Step 2 builds.

### Steps we will take

- [X] Keep candidates and failures under `work/cache/step_2_staging/`; failures retain tracebacks and leave the previous current link intact.
- [X] Publish successful artifacts under `work/precomputed/outputs/step_2/runs/`, selected through `step_2/current/`. Do not commit or push automatically.
- [X] Save `graph.gpkg` (nodes/edges/sources), `schema.json`, `model_policy.json`, `frozen_input.json`, `manifest.json`, profiles/review/memberships, four `.npz` matrices, state tables, transition mappings, region bounds, validation reports and `SUCCESS.json`.
- [X] Record active-state weak/strong components, largest component sizes and per-region EPSG:2326 bounding boxes. State tables retain component labels, physical node references and active flags.
- [X] Exercise boundaries and immediately outside values, XYZ chains, ambiguous projections, floor conflicts, crossings, interior splits, directions, parallel/closed paths, bounded sampling, reverse signs, split conservation, shared modes, disabled/unsupported codes, lift continuation/different identities/reentry, time exclusions, zero-cost entries, persistence and publication failure.
- [X] Finish the full-data build, review its accounting/connectivity/time exclusions and record runtime/memory below.

The artifact manifest stores hashes and byte sizes for every other output file, plus the frozen Step 1 snapshot and software versions. Public readers restore spatial dtypes and height metadata. Original sampling evidence is available in `profiles.jsonl`; it is not eagerly loaded by `read_graph`, which avoids duplicating a large profile collection in memory.

## Full-data acceptance result — 14 October 2026

### Explanation for the team

The validated graph run is **`20261014T092300Z-399fee39`**, selected through `work/precomputed/outputs/step_2/current/`. Its input is the frozen Step 1 run **`20261014T090829Z-20d0139c`**. All four directed mode/metric matrices passed save/reopen and shortest-path checks. All **465,892 source paths** are accounted for; originals and exclusions remain available.

| Item | Result |
|---|---:|
| General eligible source paths | 465,861 |
| Wheelchair eligible source paths | 430,496 |
| Eligible union source paths | 465,866 |
| Physical nodes | 397,199 |
| Physical pieces | 466,752 |
| Ambiguous candidate clusters left disconnected | 23 |
| Recorded floor-conflict rejections | 972 |
| Middle crossings reported without automatic joins | 11,790 |
| XY overlaps preserved | 2 |
| Source-direction profile records reopened | 465,892 |
| Review records reopened | 12,788 |
| Build and validation runtime | 241.823 seconds |
| Peak process memory | 2,196.484 MiB |

General eligibility excludes 26 disabled paths and five stair lifts. Wheelchair eligibility excludes 26 disabled paths, 23,387 paths with both an excluded type and barrier, 11,541 with a barrier, and 442 with an excluded type alone. Original records are preserved.

Twenty-five source paths have non-lift vertical intervals without usable horizontal run, and one has unrepresentable Tobler time. Both directions are unavailable for these sources; distance remains usable. Within mode-eligible physical pieces this excludes 52 general time directions and 42 wheelchair time directions. These are recorded numeric/geometry limitations, without cost caps or gradient replacements.

| Routing graph | Active states | Weak components | Strong components | Stored matrix entries | Stored zeros |
|---|---:|---:|---:|---:|---:|
| General distance | 397,198 | 511 | 537 | 923,263 | 2 |
| General time | 400,972 | 514 | 563 | 931,222 | 3,780 |
| Wheelchair distance | 386,255 | 8,259 | 8,259 | 854,385 | 2 |
| Wheelchair time | 390,028 | 8,261 | 8,309 | 862,324 | 3,780 |

A weak component is a connected region when travel direction is ignored. A strong component permits travel both ways between every pair of its states. Time graphs include lift identities as extra states, so their counts are not counts of additional physical junctions. Every active region has an EPSG:2326 bounding box in its `_regions.csv` file; `_states.csv` references its nodes and components. Disconnected regions remain visible for Step 3 rather than being bridged with invented links.

### Steps we will take

- [X] Pass the complete **52-test** suite, including the Step 1 regression tests. Command: `PYTHONPATH=work/src .venv/bin/python -m unittest discover -s work/tests -v`.
- [X] Reopen every node/edge/source geometry with exact XYZ WKB and every attribute/null; retain height metadata. Check every membership correction, profile and review record.
- [X] Validate each sparse matrix, source-edge mapping, explicit zero transition and deterministic shortest-path result after reopening.
- [X] Recheck all frozen input artifact hashes and all five implementation hashes before publication.
- [X] Preserve failed-build diagnostics in ignored cache, and verify failed builds/publication leave a previous selection intact. A first full attempt caught a tuple-versus-JSON-array comparison in the evidence validator; the corrected validator passed the complete rerun.
- [X] Publish the validated run locally through the atomic current link. Source artifacts and all large successful outputs remain trackable through Git/Git LFS; no commit or push was requested.

Read [the saved validation report](../precomputed/outputs/step_2/current/validation_report.md), [automated review](../precomputed/outputs/step_2/current/review_record.json), and [manifest](../precomputed/outputs/step_2/current/manifest.json). The retained [test log](../precomputed/docs/step_2_tests.txt) and [test report](../precomputed/docs/step_2_test_report.json) record the separate repository suite.
