# Step 2: build the pedestrian graph and assign route costs

This checklist records the agreed Step 2 work and its implementation status, including the latest lift and height-tolerance decisions.

## 1. Purpose and documentation

Explanation for the team: Step 2 builds general and wheelchair pedestrian graphs. Hospital journeys use horizontal distance in metres; transport journeys use gradient-adjusted time in seconds.

Steps we will take:

- [X] Provide horizontal-distance costs in metres for hospital journeys.
- [X] Provide gradient-adjusted time costs in seconds for transport journeys.
- [X] Return spatial outputs as actual GeoDataFrames.
- [X] Separate “Explanation for the team” from “Steps we will take” in each implementation area.
- [X] Maintain this Markdown checklist as work proceeds: mark an action `- [X]` only after completing and verifying it, or explicitly recording an agreed decision. Leave unfinished actions and unresolved evidence `- [ ]`. Recording a source limitation does not resolve it.

Step 3 attaches estates and destinations. Step 4 calculates journeys and subcosts. These later stages and the undecided final score combination are listed separately below.

## 2. Inputs and mature libraries

Explanation for the team: we will reuse established geometry and graph tools. Our custom code will implement the project’s rules about heights, eligibility, gradients and lift charges.

Steps we will take:

- [X] Continue using the local .venv, GeoPandas, Shapely, NumPy and Pyogrio.
- [X] Request installation approval for SciPy 1.13.1 before installing it. This version supports the current Python 3.9/NumPy 2 environment and has an Apple Silicon Python 3.9 wheel. Compatibility notes (https://docs.scipy.org/doc/scipy-1.13.1/release/1.13.0-notes.html), available wheel (https://pypi.org/project/scipy/1.13.1/).
- [X] Use SciPy’s sparse matrices and existing algorithms for connectivity analysis and shortest-path validation. Connectivity API (https://docs.scipy.org/doc/scipy-1.13.1/reference/generated/scipy.sparse.csgraph.connected_components.html), Dijkstra API (https://docs.scipy.org/doc/scipy-1.13.1/reference/generated/scipy.sparse.csgraph.dijkstra.html).
- [X] Use Shapely’s spatial index to find nearby geometry. Check heights separately because its spatial index operates in two dimensions. Shapely STRtree documentation (https://shapely.readthedocs.io/en/2.0.7/strtree.html).
- [X] Plan no Homebrew or npm dependency for this stage. If another package becomes necessary, explain its purpose and request approval before installing it.
- [X] Synchronise the executable policy and documentation with all agreed decisions:
  - [X] Both modes use the same Tobler speed assumption.
  - [X] All non-lift paths use Tobler.
  - [X] Exclude Enabled=false paths from both modes.
  - [X] Charge 30 seconds per lift, using the original PedestrianRouteID as its model identity.
  - [X] Accept the existing 276 wheelchair MTR access points and the three equipment-description differences.
  - [X] Select Castle Peak Hospital’s site record amended 13 July 2026, preserving both original versions.
  - [X] Leave missing terminal, floor and building references without further investigation.
- [X] Rebuild and validate Step 1 once, then freeze one successful input snapshot for Step 2. Record its run ID, hashes and policy.

Access schedules remain excluded. The validated source snapshot yields 465,861 general-mode and 430,496 wheelchair-mode eligible source paths before splitting.

## 3. Build height-aware connections

Explanation for the team: nearby paths may connect, but overlapping map positions can represent different floors or a bridge above a road. We will accept only supported endpoint connections.

Steps we will take:

- [X] Read the network in EPSG:2326, preserving its original XYZ geometry and HKPD height metadata.
- [X] Create deterministic endpoint/node identities independent of row order.
- [X] Join matching endpoints. For nearby connections, require both:
  - [X] Horizontal separation ≤ 0.10 m.
  - [X] Height difference ≤ 0.025 m.
- [X] Apply those limits to endpoint-to-endpoint connections, endpoint-to-interior connections and all members of an accepted node cluster. Prevent chained merges from exceeding either limit.
- [X] Leave ambiguous matches disconnected and report them. Detect separate visits from the traversed geometry between candidate positions, rather than differences in vertex-index parameters. Preserve ordinary bends, shared vertices and closed-path drawing seams. Several incident paths sharing one accepted junction are valid.
- [X] Split a receiving path at an accepted interior connection, interpolating its position and height from the original vertices. Minimise horizontal separation within the height-permitted interval of each segment; handle vertical, near-vertical and constant-height segments without a near-vertical cutoff.
- [X] Report middle-to-middle crossings without automatically joining them. An existing endpoint is required.
- [X] For inferred connections, differing known floor IDs within the same building prevent a merge unless an explicit vertical-transition path provides the connection. Missing supporting references remain accepted limitations.
- [X] Preserve original geometry separately from derived pieces. Record small alignment corrections without adding separate travel costs.
- [X] Preserve parallel and closed paths with their identities.
- [X] Apply provider direction:
  - [X] 0: permits both directions.
  - [X] 1: follows drawing order.
  - [X] -1: reverses drawing order.
- [X] Apply mode exclusions and Enabled=false filtering. Unsupported required routing codes produce explicit diagnostics rather than guessed meanings.

The 2.5 cm height tolerance is a connection rule, not a claim that source elevations are accurate to 2.5 cm. Equal-height gradient sampling continues to use exact equality, as previously agreed.

## 4. Assign distance, Tobler and lift costs

Explanation for the team: hospital routes minimise horizontal distance. Transport routes minimise time. Three different lifts cost 30 × 3 = 90 seconds, even when used consecutively.

Steps we will take:

- [X] Calculate each piece’s horizontal polyline length for distance routing in both modes.
- [X] Build the source path’s height/cost profile before topology splitting. Splitting must not restart sampling or alter classification.
- [X] Preserve gradient magnitude n in radians. Assign +n uphill, -n downhill and derived zero slope to level intervals.
- [X] For equal endpoint heights with a nonzero gradient:
  - [X] Sample four distinct internal positions along the original XYZ path.
  - [X] Interpolate heights from its vertices.
  - [X] If all remain level with the endpoints, sample four additional positions.
  - [X] If all ten points remain level, classify the path as relatively flat.
  - [X] Stop after at most two rounds.
- [X] Use seed 20261013 with a stable per-source-path derivation. Reverse travel reuses the same samples in reverse order.
- [X] For non-flat paths, preserve separately signed portions using original vertices and sampled positions. Sum their times rather than averaging climbs and descents.
- [X] Apply Tobler to every eligible non-lift interval in both modes:

  ```text
  slope = tan(signed_gradient_radians)
  speed_kmh = 6 × exp(-3.5 × abs(slope + 0.05))
  time_seconds = horizontal_length_metres × 3.6 / speed_kmh
  ```

- [X] Treat each original lift path record as one lift identity. Graph pieces created from that record retain the same identity.
- [X] Charge 30 seconds when entering a lift. Continuing through pieces of that same lift adds no charge. Entering a different lift adds another 30 seconds, even without intervening walking.
- [X] Track the current lift identity in time-routing states. A non-lift edge resets that state, so leaving and subsequently entering a lift starts another use. Waiting time remains zero.
- [X] Keep hospital distance costs separate: no lift seconds are added to metres.
- [X] Use stable numeric calculations. Preserve paths with unrepresentable Tobler times for distance routing and retain source-level diagnostics. Determine each piece’s directional time and status only from intervals that overlap it: an invalid overlapping interval or an overflowing piece total excludes that piece direction from time routing, while healthy pieces remain usable. Do not cap costs or replace gradients. Non-lift vertical intervals without a usable horizontal run receive the same explicit time-unavailable treatment.
- [X] Preserve gradients, sampling evidence, source lift identities, exclusions and cost-status reasons.

No maximum ramp-slope cutoff applies.

## 5. Outputs, tests and acceptance

Explanation for the team: physical geometry, routing states and sparse costs are stored separately so parallel paths, original heights and lift identities survive. A run becomes current only after full validation.

Steps we will take:

### Interfaces and storage

- [X] Expose build_graph(...) and read_graph(..., wheelchair=False, metric="time"), supporting "time" and "distance".
- [X] Return node/edge GeoDataFrames with SciPy sparse routing matrices and mappings to their source edges.
- [X] Preserve physical parallel edges. When constructing a matrix, select the minimum eligible cost per state pair and retain its edge mapping; do not let sparse duplicate entries sum alternative route costs.
- [X] Preserve explicitly stored zero-cost transitions.
- [X] Store lift-identity states separately from physical geometry.
- [X] Publish validated runs under work/precomputed/outputs/step_2/runs/, selected through step_2/current/. Include policy, manifests, validation reports and review records. Successful outputs remain trackable in Git.

### Tests

- [X] Test connections exactly at and immediately outside 0.10 m horizontally / 0.025 m vertically, chained and ambiguous matches, interior splits, different levels, directions, parallel paths and closed paths.

- [X] Test signed slopes, reverse travel, bounded sampling, unchanged costs after splitting, shared Tobler behaviour, disabled paths and wheelchair exclusions.

### Routing checks

- [X] One lift split into several graph pieces costs 30 seconds.
- [X] Three different consecutive lift records cost 90 seconds.
- [X] Leaving and re-entering a lift incurs a new charge.
- [X] Distance routing receives no lift-time penalty.
- [X] Extreme-slope time exclusions preserve distance usability.
- [X] Sparse graph construction preserves minimum costs and zero-cost transitions.

- [X] Run save/reopen checks and a full-data build. Report source accounting, components, disconnected regions, ambiguous connections, exclusions, unavailable costs, runtime and memory.

### Acceptance checks

- [X] Pass the required tests and full-data validation.
- [X] Account for every source path, including mode exclusions and unavailable time costs.
- [X] Verify that geometry, heights, units and identities survive storage and reopening.
- [X] Verify that failed builds and publication attempts preserve the previously selected successful output.
- [X] Preserve ambiguous connections and unresolved source evidence in review records without claiming they have been repaired.

## Implementation record

- [X] Record the initial implementation and its original validation. Historical full-data run: **`20261014T092300Z-399fee39`**; frozen Step 1 input: **`20261014T090829Z-20d0139c`**. That initial suite passed **52 tests**; the first regression repair passed **66** and the autonomous audit below passes **89**.
- [X] Record the explanation, implementation details, numeric limitations, connected regions, runtime/memory and acceptance evidence in [step_2_implementation.md](step_2_implementation.md). Final score combination and estate/destination attachment remain later work.

## Regression repair checklist

Explanation for the team: review found missed height-compatible lift connections, vertex-layout-dependent ambiguity checks, and source-level invalid time leaking into healthy pieces. These are implementation defects; the agreed tolerances, eligibility rules, cost models and original records stay unchanged.

Steps we will take:

- [X] Minimise horizontal separation within each segment's height-permitted parameter interval, including vertical, near-vertical and constant-height segments.
- [X] Detect separate visits from intervening geometry and traversal continuity, preserving ordinary bends and shared vertices.
- [X] Determine each piece's directional time and status from overlapping intervals only; retain source diagnostics and update conservation checks.
- [X] Add synthetic boundary, repeated-visit, mixed-validity and forward/reverse regression tests and both real lift source-ID regressions.
- [X] Run the complete suite, including lift continuation, three identities and re-entry checks.
- [X] Rebuild from frozen Step 1 run `20261014T090829Z-20d0139c`; verify all saved outputs and publish a new Step 2 snapshot only on success.
- [X] Report before/after connectivity, regression results, new run ID and remaining limitations; update the implementation/context documents without rewriting historical runs.
- [X] Leave changes uncommitted and unpushed, as requested.

Repair publication: **`20261014T101626Z-eaef8030`**, from the same frozen Step 1 input, with **66 passing tests**, 397,197 nodes and 466,819 pieces, complete save/reopen validation and direct forward/reverse checks for both real lift pairs. Detailed before/after component counts and retained limitations are in [the implementation report](step_2_implementation.md#validated-repair-publication). The initial run is preserved.

## Autonomous source and routing audit

Explanation for the team: investigate the remaining 12 rejected junction clusters and 26 sources with unavailable time without changing agreed tolerances, gradients, eligibility or original geometry. Distinguish existing valid routes from actual gaps. Isolate invalid cost intervals so usable adjacent geometry remains accessible; a subdivision is not a new cross-path junction.

Steps we will take:

- [X] Fix the demonstrated endpoint-preference defect: include qualifying existing endpoints before traversal-visit checks and prefer one only after ruling out separate visits.
- [X] Verify all affected source records against the original geodatabase and frozen successful Step 1 snapshot.
- [X] Audit all 12 clusters in both modes and metrics, retaining source-ID/coordinate evidence and distinguishing original-path connections, other available routes and unreachable pairs.
- [X] Explain all 25 sources with vertical intervals and the extreme-gradient source using original geometry and provider definitions; record only evidence-supported correction decisions.
- [X] Subdivide source paths at changes in interval cost status after junction decisions, preserving healthy portions without adding cross-path connections or crossing invalid intervals.
- [X] Add meaningful regression tests and pass the full suite, including lift identities and save/reopen checks.
- [X] Rebuild Step 2 from frozen run `20261014T090829Z-20d0139c`, save and verify reproducible audit evidence before publication, and preserve historical runs.
- [X] Report routing/count changes and retained source limitations; update the implementation report and project context, leaving changes uncommitted and unpushed.

Autonomous audit publication: **`20261014T105436Z-8fe534aa`**, with **89 passing tests**, 397,225 nodes and 466,406 pieces. The endpoint-preference repair removes the former 89.56 m endpoint detour; the 11 remaining rejected merge clusters have original-source connections for eligible endpoints. Cost-boundary subdivisions restore 29 general / 20 wheelchair healthy pieces. All 26 source-total time flags remain recorded. Full evidence and unchanged component counts are in [the autonomous audit report](step_2_implementation.md#validated-autonomous-audit-publication).

- [ ] Resolve unsupported original vertical geometry and extreme-gradient time limitations if authoritative evidence becomes available. No source geometry, gradient or eligibility replacement is established by the audit.

## User-requested cleanup of old builds

Explanation for the team: the latest explicit cleanup request supersedes preservation of complete superseded runs. Retain the selected Step 2 snapshot and frozen Step 1 input; preserve compact historical reports separately from reusable builds.

Steps we will take:

- [X] Remove three superseded build directories and 14 failed staging directories, retaining historical metadata under `work/precomputed/history/`; reclaim 3.866 GiB.
- [X] Update historical report links and retain the cleanup inventory.
- [X] Verify selected builds, frozen dependencies and current graph loading after cleanup.
- [X] Leave all changes uncommitted and unpushed.

## Later stages — outside Step 2

Explanation for the team: these tasks remain unfinished and are not part of the completed Step 2 graph build.

Steps we will take in later stages:

- [ ] Step 3: attach estates and destinations to the graph using agreed connector rules.
- [ ] Step 4: calculate journeys and the separate MTR, bus and hospital subcosts.
- [ ] Decide final score combination and treatment of wholly unreachable target groups before implementing final ranking.
