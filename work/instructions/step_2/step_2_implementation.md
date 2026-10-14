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

Exact XYZ endpoints are source-supported junctions. For inferred connections, Shapely's two-dimensional index finds nearby paths; each segment's height constraint supplies a permitted parameter interval and the XY minimum is chosen within it. Constant-height segments check their whole height; vertical segments use the closest height to break the constant-XY tie. Near-vertical segments use their actual horizontal run without a cutoff. Original endpoint pairs and explicitly supported projections seed connection components; derived cuts do not become independent endpoints that can create extra proximity joins. Every pair of sites in a proposed cluster must be compatible. Separate visits are identified by whether intervening source geometry leaves the endpoint’s permitted XYZ neighbourhood, independent of vertex spacing. An ordinary bend or shared vertex within that neighbourhood is one visit; the seam of a closed source is handled cyclically. A connected group that fails that requirement is ambiguous: we keep its original exact endpoint groups separate. We do not pick an arbitrary side of a chain. Multiple paths at one supported junction are allowed.

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

Every non-lift interval uses `tan(signed_gradient)` in Tobler's function. Log-space evaluation avoids overflowing intermediate speed/time calculations. Source-level unavailable-direction diagnostics remain recorded. Each derived piece uses only overlapping intervals: an invalid overlapping interval or an overflowing piece total makes that direction unavailable, while a healthy piece remains usable even if another interval invalidates the source total. Physical edges and horizontal distance routing survive unavailable time costs. Costs are never capped and provider gradients are never replaced.

Time-routing states remember the current original lift identity. Entering a lift costs 30 seconds. Continuing pieces of that identity costs zero; entering another identity costs another 30 seconds. Traversing a non-lift edge resets the identity. Distance routing has one state per physical node and adds no lift seconds.

### Steps we will take

- [X] Preserve provider radians, derived signed angles, heights, classification, sample rounds/positions, per-interval times and status reasons in `profiles.jsonl`.
- [X] Check exact source-position coverage, conservation of distance and available directional source totals, and each piece’s local directional costs/statuses. Source totals propagate invalid pieces and numeric overflow rather than dropping nulls from an aggregation.
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

## Initial full-data validation result — 14 October 2026 (historical)

### Explanation for the team

The initial graph run was **`20261014T092300Z-399fee39`**. It passed the checks available at that time; the later regression review below identifies defects those checks missed. Its compact historical reports are retained under `precomputed/history/step_2/20261014T092300Z-399fee39/`; the superseded large build artifacts were removed at the user's request after the autonomous audit. Its input is the frozen Step 1 run **`20261014T090829Z-20d0139c`**. All four directed mode/metric matrices passed save/reopen and shortest-path checks. All **465,892 source paths** are accounted for; originals and exclusions remain available.

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

Read [the saved validation report](../precomputed/history/step_2/20261014T092300Z-399fee39/validation_report.md), [automated review](../precomputed/history/step_2/20261014T092300Z-399fee39/review_record.json), and [manifest](../precomputed/history/step_2/20261014T092300Z-399fee39/manifest.json). The retained [test log](../precomputed/docs/step_2_tests.txt) and [test report](../precomputed/docs/step_2_test_report.json) record the separate repository suite.

## Regression repair — joint projections, visits and local piece costs

### Explanation for the team

The repair keeps the original 0.10 m / 0.025 m connection limits, endpoint-supported junctions, mode exclusions, disabled-path exclusion, shared Tobler model and original lift identities. The original source geometry, gradient classification and samples remain unchanged. The frozen Step 1 input is still `20261014T090829Z-20d0139c`; Step 1 is not rebuilt.

Joint XY/height projection exposes a subtle interaction near a lift base: a derived interior cut must not act as a new independent endpoint and cause a false chain to the lift's original base. Candidate components now start only from original endpoint pairs and actual endpoint-to-interior attachment evidence. Every member pair still has to satisfy the height, horizontal and floor rules, and repeated visits remain ambiguous.

The retraced `(-10,0,0) → (0,0,0) → (-10,0,0)` source has separate visits at parameters 0.51 and 1.49 for incoming endpoint `(-4.9,0,0)`. The intervening turnaround leaves the permitted neighbourhood, so the attachment is recorded and disconnected. Adding source vertices does not change that decision. Ordinary bends, shared vertices and closed drawing seams remain usable.

For source `[(0,0,0),(0,0,5),(10,0,6)]` at gradient 0.1 radians, the vertical piece remains unavailable for time routing. After splitting at the original vertex `(0,0,5)`, the healthy piece costs **10.1546407884 seconds uphill / 7.1558544190 seconds downhill** and retains its separately calculated downhill time. Source-level unavailability remains visible. Invalid overlapping intervals remain unavailable even when partially overlapped; finite intervals can form usable pieces when the complete source total overflows, provided each piece's own sum is representable.

### Steps we will take

- [X] Pass all **66 tests**, including 14 new regression tests, forward/reverse travel, inclusive/nextafter boundaries, dense vertices and repeated visits, local invalidity/overflow, persistence and the two real source-ID pairs.
- [X] Reconfirm one split lift costs 30 seconds, three original lift identities cost 90 seconds, and leaving/re-entering incurs a new entry charge.
- [X] Reproduce the original real regressions by source IDs and coordinates: `290063550 → 260001786` was unreachable in the old time graph; `290064373 → 280005280` required **105.0998356 seconds generally / 166.0983617 seconds in wheelchair mode** to enter the far lift-end identity state.
- [X] Check both real pairs in their input neighbourhoods: direct lift entry and reverse travel each cost **30 seconds**. Independent equal-height residuals reproduce **0.0222275165 m** and **0.0049667849 m**; the accepted constrained XY minimum may use another position within the height band.
- [X] Complete the frozen-input full-data rebuild, validate/reopen every output and pass both source-ID checks in the reopened general and wheelchair time matrices before publication.
- [X] Record the new run ID, before/after graph/component counts, remaining source limitations and final publication result.

### Validated repair publication

The first repaired run **`20261014T101626Z-eaef8030`** was selected through `work/precomputed/outputs/step_2/current/` before the autonomous audit below. It was built from the unchanged frozen Step 1 snapshot. The original Step 2 run **`20261014T092300Z-399fee39`** and its complete artifact hashes remain preserved; no Step 1 rebuild, dependency installation, commit or push was performed for this repair.

| Physical graph | Before | After | Change |
|---|---:|---:|---:|
| Physical nodes | 397,199 | 397,197 | -2 |
| Physical pieces | 466,752 | 466,819 | +67 |

All **465,892 source paths** remain accounted for, with **465,861 general / 430,496 wheelchair eligible sources** and 465,866 in their union. Eligibility/exclusion decisions are unchanged.

| Routing graph | Weak components before → after | Strong components before → after | Matrix entries before → after |
|---|---:|---:|---:|
| general distance | 511 → 507 | 537 → 533 | 923,263 → 923,309 |
| general time | 514 → 510 | 563 → 558 | 931,222 → 931,310 |
| wheelchair distance | 8259 → 8255 | 8259 → 8255 | 854,385 → 854,425 |
| wheelchair time | 8261 → 8257 | 8309 → 8304 | 862,324 → 862,406 |

Both real footway/lift pairs pass direct **30-second forward and reverse** identity-state routing checks in the reopened general and wheelchair time graphs. The new run records the source IDs, original XYZ, accepted lift parameters and independent equal-height residuals in its validation report and automated review. Saved numeric node indexes are not used to identify the regressions.

All source-level invalidity diagnostics are retained: 25 sources with non-lift vertical intervals and one with unrepresentable Tobler times. There are **0 healthy physical-piece directions from sources with unavailable source totals** in this full snapshot; healthy-piece recovery is demonstrated by the mixed-interval synthetic regression above. Piece-level status counts: forward `{"available": 466793, "non_lift_vertical_without_horizontal_run": 25, "unrepresentable_tobler_time": 1}`; reverse `{"available": 466793, "non_lift_vertical_without_horizontal_run": 25, "unrepresentable_tobler_time": 1}`. The available source totals conserve cost across splits, null/overflow source totals are propagated rather than silently summing only healthy parts, and every stored piece is checked against its overlapping intervals.

Remaining unavailable eligible directed pieces: general time: {"non_lift_vertical_without_horizontal_run": 50, "unrepresentable_tobler_time": 2}; wheelchair time: {"non_lift_vertical_without_horizontal_run": 40, "unrepresentable_tobler_time": 2}. These receive no capped or replacement time; horizontal distance remains preserved. Review counts are `{"ambiguous_cluster": 12, "topology_summary": 1, "floor_conflict_rejected": 972, "middle_crossing_not_auto_joined": 11790, "overlapping_xy_paths_preserved": 2}`. Ambiguous attachments/clusters remain disconnected; floor conflicts and missing supporting references remain recorded source limitations. Middle crossings still do not create junctions automatically. Estate/destination attachment and final ranking remain later work.

Runtime was **566.971 seconds**; peak process memory was **2081.75 MiB**. All geometry/attribute/null, membership, profile/review, four-matrix/mapping and Dijkstra read-back checks passed before the atomic publication. Source/input policy hashes and all six implementation hashes were rechecked. Independent post-publication verification also confirmed every original source geometry/attribute and all original profile evidence against the initial run.

- [X] Publish only after full output checks and both real lift regressions pass.
- [X] Preserve all historical artifacts and original source/profile evidence.
- [X] Retain the 66-test log, regression comparison and fidelity evidence in [the repair report](../precomputed/docs/step_2_repair_test_report.json) and [test log](../precomputed/docs/step_2_repair_tests.txt).
- [X] Record the new [validation report](../precomputed/history/step_2/20261014T101626Z-eaef8030/validation_report.md), [comparison](../precomputed/history/step_2/20261014T101626Z-eaef8030/comparison_to_previous.json) and [automated review](../precomputed/history/step_2/20261014T101626Z-eaef8030/review_record.json).
- [X] Leave the repair uncommitted and unpushed as requested.

## Autonomous audit — endpoint preference and invalid-interval boundaries

### Explanation for the team

The user authorised an autonomous investigation, including parallel agents, of the 12 rejected clusters and 26 sources with unavailable time. This investigation preserves the frozen Step 1 snapshot, all original geometry/attributes/gradients, connection tolerances, eligibility and lift rules. It does not invent replacement elevations or reinterpret equipment types.

The baseline cluster audit distinguishes rejected inferred merges from actual disconnection. Eleven clusters already have connections through their own source paths in general mode. In wheelchair mode, ten do; one consists entirely of excluded paths. One remaining height-conflict cluster needs other paths, including an **89.55947655 m** endpoint-to-endpoint route in each direction. The baseline evidence is [the source-ID cluster audit](../precomputed/docs/step_2_cluster_audit_20261014T101626Z.json).

That height cluster exposed an implementation defect. Incoming endpoint `250011610` lies **0.0946374663 m horizontally / 0.0189000000 m vertically** from the existing endpoint of `250015300`; both satisfy the agreed limits. However, the constrained XY minimum lies inside `250015300` and differs from its own endpoint by **0.0439 m in height**. Introducing that unnecessary interior cut creates an artificial non-clique. The fix explicitly includes eligible original receiving endpoints before checking traversal visits, then prefers an existing endpoint only after excluding separate visits. It changes neither tolerance nor the complete-pairwise rule.

All 26 unavailable source records match the original geodatabase and frozen Step 1. The 25 vertical sources contain 26 original zero-horizontal/nonzero-height intervals, with jumps from **0.0018 m to 65.9772 m**; three staircases include zero-elevation stretches. Eight jumps are at most 0.025 m, but that connection tolerance does not authorise flattening them. There is no supported replacement geometry. Each source also contains healthy walking intervals, which were hidden within a larger unavailable physical piece unless an external endpoint had caused a split.

Cost-boundary subdivisions now isolate changes in per-interval forward/reverse status. They are inserted **after junction decisions**, use original/interpolated XYZ, and belong to one source only. They do not seed proximity connections, join middle crossings or make an invalid interval traversable. Source-level unavailability stays visible while healthy adjacent pieces become usable. Profile sampling and gradient signs remain unchanged.

The extreme Footway `150021876` has **0.00781025036 m horizontal run and -2.0883 m height change**. Its supplied **1.56705634-radian** gradient agrees with the geometry-derived angle to about **2.3 × 10⁻¹⁰ radians**. The provider dictionary confirms radians. Tobler gives roughly **10⁴⁰⁴ seconds** in each direction, beyond float64 range. The existing exclusion is correct under the agreed model; no gradient correction or cost cap is justified.

A further validation defect appeared in the isolated all-unavailable fixture: pandas stored entirely null time aggregates as object values, making the numeric finite check fail. Converting those aggregates to float preserves nulls and lets valid distance-only graphs pass validation.

### Steps we will take

- [X] Run three parallel evidence investigations using the installed local environment.
- [X] Verify original archive hash, all 77 extracted-file hashes, affected original attributes/XYZ and the provider definitions.
- [X] Implement the supported endpoint-preference correction, healthy cost-boundary subdivisions and entirely-unavailable graph validation fix.
- [X] Pass **89 tests**, including **23 new tests** for these changes and their evidence helpers. Existing lift continuation, consecutive identities, re-entry, source conservation and storage checks pass.
- [X] Complete the full frozen-input rebuild and verify all four matrices, source-ID regressions, source/routing audit save/reopen and input/code hashes before publication.
- [X] Record the successful publication, count changes, independent fidelity checks and remaining limitations.
- [ ] Resolve original unsupported vertical geometry and extreme-gradient time limitations. Recording and isolating them does not repair the source.

### Validated autonomous audit publication

The new selected snapshot is **`20261014T105436Z-8fe534aa`**, built from unchanged frozen Step 1 run **`20261014T090829Z-20d0139c`**. All **89 tests**, both original lift regressions and the new real endpoint-preference regression pass. All four matrices, spatial values, profiles, memberships, review records and source/routing audit pass save/reopen checks. The selected raw archive/dictionary and all ten implementation-file hashes were checked before publication. Runtime: **315.966 seconds**; peak process memory: **2,212.844 MiB**.

| Physical graph / evidence | Previous repaired run | Autonomous audit run |
|---|---:|---:|
| Nodes | 397,197 | 397,225 |
| Pieces | 466,819 | 466,406 |
| Rejected inferred merge clusters | 12 | 11 |
| Healthy piece directions on sources with unavailable totals | 0 | 58 |
| Sources with unavailable time totals | 26 | 26 |

The net **28 additional nodes** comprise 29 isolated cost-boundary nodes and one merged endpoint junction. The **413 fewer pieces** reflect 442 unnecessary interior subdivisions avoided by endpoint preference, offset by 29 new cost subdivisions. Original path coverage and source costs remain conserved; fewer pieces do not mean deleted source geometry. Interior projection candidates fall from 956 to 511. Floor rejections remain 972, middle crossings 11,790 and preserved XY overlaps two.

The 29 recovered healthy pieces cover **766.558511 m** in general mode; **20 pieces / 362.718808 m** are wheelchair eligible. They contribute **58 / 40 available directed time pieces** respectively. The 25 invalid vertical pieces and one extreme-gradient piece remain unavailable for time, and available for distance subject to mode eligibility. The source profiles retain their unavailable total diagnostics.

| Graph | Weak / strong components (unchanged) | Matrix entries before → after | Stored zeros after |
|---|---:|---:|---:|
| General distance | 507 / 533 | 923,309 → 923,256 | 50 |
| General time | 510 / 558 | 931,310 → 931,221 | 3,782 |
| Wheelchair distance | 8,255 / 8,255 | 854,425 → 854,356 | 40 |
| Wheelchair time | 8,257 / 8,304 | 862,406 → 862,301 | 3,782 |

The repaired real endpoint pair now shares one accepted junction, removing the former 89.5595 m detour between those endpoints. No additional alignment travel cost is introduced. All 11 remaining clusters have local original-source routes between their eligible endpoints in both metrics: 11 in general mode, ten in wheelchair mode, with the other cluster's sources excluded by the existing wheelchair rules. Their declined merges remain in review evidence; they are not missing endpoint routes.

Source/routing audit evidence verifies **82 records** against original FGDB and frozen Step 1. Independent verification additionally checks all four repaired-cluster records, every original source geometry/attribute, unchanged source profiles/policy/frozen input, and all new and historical artifact hashes.

### Remaining source limitations and routing impact

Source investigations establish no replacement geometry or gradient. Eight vertical jumps are within the connection height tolerance, but exact gradient sampling and original geometry are not changed. Three staircases have zero-height stretches; the audit cannot establish their correct elevations. The extreme source's near-vertical geometry corroborates its supplied gradient, and its unavailable direct time remains excluded.

Of the unavailable eligible piece directions, **44 of 52 general** and **34 of 42 wheelchair** have another finite time route between their endpoints. The remaining **eight directions per mode** correspond to four invalid pieces per mode:

- General: sources `120010565`, `120010729`, `280013841`, `290038266`.
- Wheelchair: sources `120010565`, `120010729`, `150021694`, `290036414`.

These are local endpoint reachability results, not estate-to-destination journeys or proof that missing links should be added. Source `150021876` has existing alternate time routes of **40.4983 / 46.3544 seconds** generally and **1,702.0225 / 1,834.9190 seconds** in wheelchair mode, forward/reverse. Those are actual available routes; no hypothetical direct-time cost or measured detour is invented.

- [X] Publish only the validated run and preserve the two historical Step 2 snapshots.
- [X] Retain the [89-test log](../precomputed/docs/step_2_autonomous_tests.txt), [build log](../precomputed/docs/step_2_autonomous_build.txt), [independent verification](../precomputed/docs/step_2_autonomous_test_report.json), [source/routing audit](../precomputed/outputs/step_2/runs/20261014T105436Z-8fe534aa/source_routing_audit.md), [full JSON evidence](../precomputed/outputs/step_2/runs/20261014T105436Z-8fe534aa/source_routing_audit.json) and [before/after comparison](../precomputed/outputs/step_2/runs/20261014T105436Z-8fe534aa/comparison_to_previous.json).
- [X] Leave all changes uncommitted and unpushed.
- [ ] Resolve the original vertical/gradient limitations if authoritative replacement evidence becomes available. The source audit does not claim these are repaired.

## Superseded artifact cleanup — user requested

### Explanation for the team

After the autonomous audit passed, the user requested removal of old build artifacts. The three superseded published builds (one Step 1 and two Step 2) and 14 failed staging directories were removed, reclaiming **3.866 GiB**. Their compact historical reports, manifests, policy and identity metadata are retained in [the history directory](../precomputed/history/README.md). Those metadata folders are not loadable builds; historical hash checks record verification before cleanup. Earlier preservation checkboxes describe the completed builds at that time and are superseded by this explicit cleanup request.

The selected Step 2 run, its frozen successful Step 1 input, active MTR output, original sources and verified network extraction remain intact. Existing snapshots and manifest contents were not rewritten.

### Steps we will take

- [X] Resolve all selected outputs and frozen dependencies before cleanup; acquire build locks and reject potentially active staging directories.
- [X] Preserve compact historical metadata with exact hashes before removing obsolete generated geometry, matrices, mappings and failed staging output.
- [X] Update historical report links and record the [cleanup inventory](../precomputed/history/cleanup_20261014.json).
- [X] Verify retained artifacts, frozen hashes and current graph loading after cleanup.
- [X] Leave source changes and cleanup uncommitted and unpushed.
