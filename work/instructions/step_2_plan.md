# Step 2: build the pedestrian graph and assign route costs

## 1. Purpose and deliverables

Step 2 turns the prepared paths into a graph:

- Nodes identify endpoints and junctions.
- Edges describe permitted travel between nodes.
- Costs measure horizontal distance or gradient-adjusted travel time.

We will build both general and wheelchair routing models. Spatial outputs will be actual GeoDataFrames, saved under work/precomputed/outputs/step_2/.

Step 3 will attach estates, hospitals and transport access points to this graph. Step 4 will calculate their journeys and three subcosts. The final combining method remains undecided.

The documentation deliverables will be two files under work/instructions/step_2/: a technical implementation plan and a human-readable plan. Each area in the latter will separate “Explanation for the team” from “Steps we will take.” Recorded decisions can have [X]; unfinished implementation and unresolved evidence remain [ ].

## 2. Prepare one consistent input snapshot

Explanation for the team: the instructions contain decisions made after the last prepared output was generated. Before building connections, the program must use one consistent set of data and rules.

Steps we will take:

1. Update the executable policy and current documentation to incorporate the latest decisions:
   - Wheelchair speed uses the same Tobler formula as ordinary walking, as an accepted modelling assumption.
   - Every non-lift path uses Tobler for transport time.
   - Paths marked Enabled=false are excluded from both routing modes.
   - Consecutive lift sections count as one 30-second use.
2. Apply the recorded Step 1 decisions:
   - Accept the existing 276 mobility access points as the complete wheelchair MTR target pool.
   - Accept the three equipment-description differences as mobility access.
   - Select Castle Peak Hospital’s supporting site record amended 13 July 2026, preserving both original versions.
   - Leave missing terminal, floor and building references without further investigation.
3. Rebuild and validate Step 1 once using its existing pipeline. Preserve its historical runs and original source records.
4. Resolve the resulting successful input directory once at Step 2 startup. Record its run ID, file hashes and policy snapshot so an input-link change cannot mix different runs.

Schedules remain outside the model. Excluding Enabled=false is the separate rule you selected.

For the current source snapshot, filtering by mode and Enabled should leave 465,861 general-mode and 430,496 wheelchair-mode source paths, before topology splitting.

## 3. Build connections without joining different levels

Explanation for the team: two paths crossing on a map do not necessarily meet. One may be a bridge above the other. We will use the preserved heights and existing endpoints to establish connections.

Steps we will take:

1. Read the prepared network as a GeoDataFrame in EPSG:2326, preserving XYZ geometry and HKPD height metadata.
2. Identify each path’s endpoints and assign deterministic node identities independent of input row order.
3. Join matching source endpoints. For nearby endpoints, allow at most 0.10 m horizontally and 0.10 m in height.
4. Prevent a chain of nearby points from merging locations farther apart than the permitted limits. Every accepted cluster must satisfy the limits across all its members; otherwise retain separate nodes and report the ambiguity.
5. Connect an endpoint to another path’s interior only when its projected position and interpolated height satisfy those same limits and the connection is unambiguous. Several paths meeting at the same accepted junction can share that junction.
6. Split the receiving path at an accepted interior connection. Calculate the new position and height from its original vertices.
7. Report middle-to-middle crossings without automatically creating junctions. An existing endpoint is required by the agreed rule.
8. Use available floor information to identify conflicting levels. For inferred connections, differing known floor IDs within the same building prevent a merge unless an explicit vertical-transition path supplies the connection. Missing floor/building records remain accepted limitations.
9. Preserve original path geometry separately from derived graph pieces. Record small coordinate adjustments used to associate endpoints with nodes; treat these as alignment corrections without adding separate travel costs.
10. Preserve parallel paths and closed paths with their source identities. Do not collapse distinct paths merely because they connect the same nodes.
11. Apply provider travel direction:
    - 0: create both permitted directions.
    - 1: follow the source drawing direction.
    - -1: travel opposite to it.
12. Apply mode rules and exclude Enabled=false edges. Unknown or unsupported routing codes produce explicit diagnostics rather than silently acquiring a guessed meaning.

Connection repairs must not invent missing lifts, entrances or other equipment.

## 4. Calculate distance and time costs

Explanation for the team: the same connection can have two costs. Hospital journeys minimise horizontal distance. Transport journeys minimise time, so uphill and downhill travel may choose different routes.

Steps we will take:

1. Calculate each graph piece’s horizontal polyline length in metres, preserving its relationship to the source path. This supplies hospital distance costs in both modes.
2. Construct each source path’s height/cost profile before topology splitting, so splitting cannot restart random sampling or change its classification.
3. Preserve the provider’s gradient magnitude n, in radians. Use height changes to assign +n uphill and -n downhill. Level intervals use derived zero slope.
4. For equal endpoint heights with a nonzero source gradient:
   - Sample four distinct internal positions along the original XYZ path.
   - Interpolate their heights from the existing vertices.
   - If they remain level with both endpoints, sample four additional positions.
   - Compare the ordered ten points. If all remain level, classify the source path as relatively flat.
   - Stop after at most two rounds.
5. Use seed 20261013, with a stable per-source-path derivation. Sampling positions follow the actual 3D polyline and remain identical when travel direction reverses.
6. If the sampled path is not flat, preserve separately signed uphill/downhill portions using its original vertices and sampled positions. Sum their interval times; do not average away climbs and descents.
7. Apply Tobler to every eligible non-lift interval:

   slope = tan(signed_gradient_radians)
speed_kmh = 6 × exp(-3.5 × abs(slope + 0.05))
time_seconds = horizontal_length_metres × 3.6 / speed_kmh

   Both modes use this formula. Wheelchair results will identify that shared-speed assumption in their metadata.
8. Charge 30 seconds when entering a continuous lift journey, with zero waiting time. Further consecutive lift sections add no additional lift charge. Travelling along a non-lift edge ends that lift journey.
9. Represent time routing with two states at a junction: arriving through a lift and arriving otherwise. This allows the graph to charge lift entry once, including when one source lift record is split into several pieces.
10. Keep hospital distance routing separate: it uses horizontal metres and receives no lift-time penalty.
11. Evaluate Tobler time using numerically stable calculations. If a cost cannot be represented, preserve the edge for distance routing, flag its time cost, and omit that direction from time routing. Do not cap the cost or replace its gradient. A non-lift vertical segment with no usable horizontal run receives the same explicit “time unavailable” treatment.
12. Preserve source gradients, classifications, sample evidence, exclusions and cost-status reasons for review.

There is no maximum ramp-slope cutoff.

## 5. Outputs, validation and acceptance

Implementation and interfaces

- Use the local .venv, existing GeoPandas, Shapely and NumPy, plus Python’s standard library. No additional dependency is required for Step 2.
- Expose build_graph(...) and read_graph(..., wheelchair=False, metric="time"). Supported metrics are "time" and "distance"; the returned graph bundle contains node/edge GeoDataFrames and compact adjacency arrays.
- Store physical nodes and directed edges with stable IDs, source references, XYZ geometry, mode eligibility, distance and time-status information.
- Store time-routing states/transitions separately so a lift edge does not misleadingly advertise one fixed cost independent of entry state.
- Publish checked snapshots through step_2/runs/ and step_2/current/, with manifests, policy, validation reports and connection/cost review records. Keep successful outputs trackable in Git.

Tests and checks

Test exact and 10 cm connections, rejected wider gaps, prevention of chained merges, endpoint-to-interior splitting, different-height crossings, and middle-to-middle crossings remaining disconnected. Verify all three direction codes, parallel paths and closed paths.

Test uphill/downhill signs, reverse-travel consistency, bounded four-plus-four sampling, preservation of cost profiles after splitting, and shared Tobler behaviour across modes. Verify a continuous multi-section lift costs 30 seconds, while two lift journeys separated by walking cost 60 seconds.

Test disabled-path exclusion, wheelchair equipment/barrier rules, extreme-slope time exclusions, source preservation, GeoDataFrame types and save/reopen equality. Use small shortest-path examples to check the resulting costs and lift states.

Run a full-data build and report component sizes, disconnected regions, ambiguous connections, exclusions, unavailable time costs, runtime and memory use. Disconnected regions are reported without fabricating connections.

Acceptance: required checks pass, every source path is accounted for, units and assumptions are explicit, geometry/heights survive saving, and failed builds leave the previous successful Step 2 output selected. Routing to real estates and destinations remains Step 3/4 work.
