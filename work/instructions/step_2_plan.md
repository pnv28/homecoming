# Step 2: build the pedestrian graph and assign route costs

Current plan: work/instructions/step_2_plan.md (work/instructions/step_2_plan.md). The file already contains the latest lift and height-tolerance decisions.

## 1. Purpose and documentation

Step 2 builds general and wheelchair pedestrian graphs with two metrics:

- Horizontal distance in metres for hospital journeys.
- Gradient-adjusted time in seconds for transport journeys.

Spatial outputs will be actual GeoDataFrames.

Each implementation area will distinguish “Explanation for the team” from “Steps we will take.” [X] means a completed action or explicitly recorded decision; unfinished implementation and unresolved evidence remain [ ].

Step 3 attaches estates and destinations. Step 4 calculates journeys and subcosts. Final score combination remains undecided.

## 2. Inputs and mature libraries

Explanation for the team: we will reuse established geometry and graph tools. Our custom code will implement the project’s rules about heights, eligibility, gradients and lift charges.

Steps we will take:

1. Continue using the local .venv, GeoPandas, Shapely, NumPy and Pyogrio.
2. Request installation approval for SciPy 1.13.1 before installing it. This version supports the current Python 3.9/NumPy 2 environment and has an Apple Silicon Python 3.9 wheel. Compatibility notes (https://docs.scipy.org/doc/scipy-1.13.1/release/1.13.0-notes.html), available wheel (https://pypi.org/project/scipy/1.13.1/).
3. Use SciPy’s sparse matrices and existing algorithms for connectivity analysis and shortest-path validation. Connectivity API (https://docs.scipy.org/doc/scipy-1.13.1/reference/generated/scipy.sparse.csgraph.connected_components.html), Dijkstra API (https://docs.scipy.org/doc/scipy-1.13.1/reference/generated/scipy.sparse.csgraph.dijkstra.html).
4. Use Shapely’s spatial index to find nearby geometry. Check heights separately because its spatial index operates in two dimensions. Shapely STRtree documentation (https://shapely.readthedocs.io/en/2.0.7/strtree.html).
5. Plan no Homebrew or npm dependency for this stage. If another package becomes necessary, explain its purpose and request approval before installing it.
6. Synchronise the executable policy and documentation with all agreed decisions:
   - Both modes use the same Tobler speed assumption.
   - All non-lift paths use Tobler.
   - Exclude Enabled=false paths from both modes.
   - Charge 30 seconds per lift, using the original PedestrianRouteID as its model identity.
   - Accept the existing 276 wheelchair MTR access points and the three equipment-description differences.
   - Select Castle Peak Hospital’s site record amended 13 July 2026, preserving both original versions.
   - Leave missing terminal, floor and building references without further investigation.
7. Rebuild and validate Step 1 once, then freeze one successful input snapshot for Step 2. Record its run ID, hashes and policy.

Access schedules remain excluded. The current source snapshot should yield 465,861 general-mode and 430,496 wheelchair-mode eligible source paths before splitting.

## 3. Build height-aware connections

Explanation for the team: nearby paths may connect, but overlapping map positions can represent different floors or a bridge above a road. We will accept only supported endpoint connections.

Steps we will take:

1. Read the network in EPSG:2326, preserving its original XYZ geometry and HKPD height metadata.
2. Create deterministic endpoint/node identities independent of row order.
3. Join matching endpoints. For nearby connections, require both:
   - Horizontal separation ≤ 0.10 m.
   - Height difference ≤ 0.025 m.
4. Apply those limits to endpoint-to-endpoint connections, endpoint-to-interior connections and all members of an accepted node cluster. Prevent chained merges from exceeding either limit.
5. Leave ambiguous matches disconnected and report them. Several incident paths sharing one accepted junction are valid.
6. Split a receiving path at an accepted interior connection, interpolating its position and height from the original vertices.
7. Report middle-to-middle crossings without automatically joining them. An existing endpoint is required.
8. For inferred connections, differing known floor IDs within the same building prevent a merge unless an explicit vertical-transition path provides the connection. Missing supporting references remain accepted limitations.
9. Preserve original geometry separately from derived pieces. Record small alignment corrections without adding separate travel costs.
10. Preserve parallel and closed paths with their identities.
11. Apply provider direction:
    - 0: permits both directions.
    - 1: follows drawing order.
    - -1: reverses drawing order.
12. Apply mode exclusions and Enabled=false filtering. Unsupported required routing codes produce explicit diagnostics rather than guessed meanings.

The 2.5 cm height tolerance is a connection rule, not a claim that source elevations are accurate to 2.5 cm. Equal-height gradient sampling continues to use exact equality, as previously agreed.

## 4. Assign distance, Tobler and lift costs

Explanation for the team: hospital routes minimise horizontal distance. Transport routes minimise time. Three different lifts cost 30 × 3 = 90 seconds, even when used consecutively.

Steps we will take:

1. Calculate each piece’s horizontal polyline length for distance routing in both modes.
2. Build the source path’s height/cost profile before topology splitting. Splitting must not restart sampling or alter classification.
3. Preserve gradient magnitude n in radians. Assign +n uphill, -n downhill and derived zero slope to level intervals.
4. For equal endpoint heights with a nonzero gradient:
   - Sample four distinct internal positions along the original XYZ path.
   - Interpolate heights from its vertices.
   - If all remain level with the endpoints, sample four additional positions.
   - If all ten points remain level, classify the path as relatively flat.
   - Stop after at most two rounds.
5. Use seed 20261013 with a stable per-source-path derivation. Reverse travel reuses the same samples in reverse order.
6. For non-flat paths, preserve separately signed portions using original vertices and sampled positions. Sum their times rather than averaging climbs and descents.
7. Apply Tobler to every eligible non-lift interval in both modes:

   slope = tan(signed_gradient_radians)
speed_kmh = 6 × exp(-3.5 × abs(slope + 0.05))
time_seconds = horizontal_length_metres × 3.6 / speed_kmh
8. Treat each original lift path record as one lift identity. Graph pieces created from that record retain the same identity.
9. Charge 30 seconds when entering a lift. Continuing through pieces of that same lift adds no charge. Entering a different lift adds another 30 seconds, even without intervening walking.
10. Track the current lift identity in time-routing states. A non-lift edge resets that state, so leaving and subsequently entering a lift starts another use. Waiting time remains zero.
11. Keep hospital distance costs separate: no lift seconds are added to metres.
12. Use stable numeric calculations. Preserve paths with unrepresentable Tobler times for distance routing, flag the affected time directions and omit them from time routing. Do not cap costs or replace gradients. Non-lift vertical geometry without a usable horizontal run receives the same explicit time-unavailable treatment.
13. Preserve gradients, sampling evidence, source lift identities, exclusions and cost-status reasons.

No maximum ramp-slope cutoff applies.

## 5. Outputs, tests and acceptance

Interfaces and storage

- Expose build_graph(...) and read_graph(..., wheelchair=False, metric="time"), supporting "time" and "distance".
- Return node/edge GeoDataFrames with SciPy sparse routing matrices and mappings to their source edges.
- Preserve physical parallel edges. When constructing a matrix, select the minimum eligible cost per state pair and retain its edge mapping; do not let sparse duplicate entries sum alternative route costs.
- Preserve explicitly stored zero-cost transitions.
- Store lift-identity states separately from physical geometry.
- Publish validated runs under work/precomputed/outputs/step_2/runs/, selected through step_2/current/. Include policy, manifests, validation reports and review records. Successful outputs remain trackable in Git.

Tests

Test connections exactly at and immediately outside 0.10 m horizontally / 0.025 m vertically, chained and ambiguous matches, interior splits, different levels, directions, parallel paths and closed paths.

Test signed slopes, reverse travel, bounded sampling, unchanged costs after splitting, shared Tobler behaviour, disabled paths and wheelchair exclusions.

Verify:

- One lift split into several graph pieces costs 30 seconds.
- Three different consecutive lift records cost 90 seconds.
- Leaving and re-entering a lift incurs a new charge.
- Distance routing receives no lift-time penalty.
- Extreme-slope time exclusions preserve distance usability.
- Sparse graph construction preserves minimum costs and zero-cost transitions.

Run save/reopen checks and a full-data build. Report source accounting, components, disconnected regions, ambiguous connections, exclusions, unavailable costs, runtime and memory.

Acceptance: required checks pass; every source path is accounted for; geometry, heights, units and identities survive storage; and failed builds preserve the previously selected successful output. Real estate-to-destination routing remains later work.
