# Step 2: rebuild the complete pedestrian graph and route costs

Last updated: 2026-10-16 16:19:58 HKT (UTC+08:00)

## 1. Purpose, decisions and completion status

**Explanation for the team**

We will rerun the whole of Step 2 from the successful Step 1 input, then rerun the whole of Step 3 against the new Step 2 result. This is a fresh, coordinated build of the complete network, connections, costs and outputs. We will not patch selected matrix entries in the currently published files. All source paths will be processed and accounted for again.

Within that full build, healthy walking sections still use Tobler. Reviewed problematic sections receive the accepted distance-and-height estimate where supported. An unresolved time calculation does not mean deleting the original path from the source data. Unsupported connections remain explicitly unresolved rather than being made into invented shortcuts.

**Recorded decisions**

- [X] Rebuild all of Steps 2 and 3 together, using the existing Step 1 snapshot; Step 1 does not need repeating for this cost change.
- [X] Use hospital costs in horizontal metres and transport costs in seconds. Keep the three eventual estate subcosts separate.
- [X] Integrate the distance-and-height fallback into the original-source cost pipeline, preserving healthy Tobler costs and original failure evidence.
- [X] Keep direction, mode exclusions, original gradients, lift identities and the existing connection tolerances.
- [X] Preserve a baseline time scenario excluding fallback sections for route comparison. The main rebuilt time scenario includes accepted fallback estimates.

**Checkboxes below refer to this new build and are updated only as actions complete.** Earlier successful runs remain historical evidence; their checkmarks and test counts do not establish completion of this rebuild. Mark an action `[X]` only when completed and verified. An accepted assumption is different from a provider-confirmed fact.

## 2. Freeze inputs, parameters and mature dependencies

**Explanation for the team**

Reproducibility requires recording both the original prepared data and the new routing assumptions. The new cost policy can differ from the old policy saved with Step 1 without changing the frozen Step 1 files.

**Steps we will take**

- [X] Freeze Step 1 `20261014T090829Z-20d0139c`; verify success, schemas, hashes, coordinates and prepared mode flags. Read all 465,892 source paths, preserving original XYZ, attributes and identities, including paths excluded from a selected routing mode.
- [X] Record the old Step 2 `20261014T105436Z-8fe534aa` and Step 3 `20261014T145819Z-4d15d1a3` as retained comparison snapshots. Do not overwrite them or restore previously deleted bulky builds.
- [X] Continue using the repository-root `.venv`, GeoPandas, Shapely, NumPy, pandas, Pyogrio and SciPy. Reuse library spatial indexes, sparse matrices, connected-component analysis and Dijkstra. No new package is currently needed. Explain and record any necessary additional mature dependency under the existing user authorisation.
- [X] Review every unavailable interval found in the full source pass, beginning with the known 26 affected source records. Record source positions, original failure, distance, ascent/descent, feature type, direction, permitted modes and the evidence or explicit assumption supporting a continuous connection.
- [X] Assign each affected interval an explicit fallback decision and reason. A confirmed lift retains lift treatment; unknown connectivity, unusable geometry and unsupported required codes remain unresolved. Review does not require inventing replacement coordinates or changing the provider gradient.
- [X] Set the uphill/downhill seconds-per-metre coefficients and their use or adaptation for wheelchair mode. The user confirmed **6 s/m uphill and 2 s/m downhill**, shared with wheelchair mode as an explicit approximation. Validate and record those parameters; missing or invalid coefficients must fail the build.
- [X] Save a versioned derived routing policy and the interval review decisions separately from the unchanged source-preparation policy. Update policy validation and lineage checks to permit the documented routing change while still verifying all frozen input hashes and source-related assumptions.

Access schedules remain ignored; routes are assumed always open. `Enabled=false` and the agreed mode restrictions still exclude travel. No maximum ramp-slope cutoff applies. Current source eligibility counts, before splitting, are 465,861 general and 430,496 wheelchair; the rebuild must explain any difference.

## 3. Rebuild all height-aware topology

**Explanation for the team**

A network junction represents a supported connection. Similar X/Y coordinates can describe different floors, a bridge or a tunnel, so the fallback must never create connections solely to make a journey possible.

**Steps we will take**

- [X] Recreate the complete physical graph from original EPSG:2326 geometry with HKPD heights, EPSG:5738, and deterministic identities independent of row order.
- [X] Join matching source endpoints and infer nearby connections only when horizontal separation is at most **0.10 m** and height separation at most **0.025 m**. Every pair of members in a proposed cluster must satisfy both rules; chained merges cannot exceed the limits.
- [X] Include qualifying original receiving endpoints before considering interior cuts. Prefer an existing endpoint only after ruling out separate visits through the original traversal geometry.
- [X] Handle endpoint-to-interior projection jointly in X/Y and height, including vertical, near-vertical and constant-height segments. Interpolate original XYZ at accepted source positions.
- [X] Preserve ordinary bends, shared vertices, closed-path seams and parallel identities. Leave ambiguous connections disconnected with diagnostics. Report middle-to-middle crossings without joining them unless supported by an original endpoint connection.
- [X] Prevent inferred same-building merges between differing known floor IDs unless an explicit vertical-transition path supplies the connection. Missing terminal/floor/building references remain accepted limitations; available evidence still applies.
- [X] Apply drawing-order direction codes: 0 both ways, 1 forward, -1 reverse. Apply general/wheelchair equipment rules, barriers, Enabled filtering and diagnostics for unsupported required codes.
- [X] Add source-only cost/model boundaries after junction decisions where needed to expose healthy, estimated and unavailable sections. These boundaries must not seed new cross-path junctions.
- [X] Preserve original geometry separately from derived pieces and record permitted small alignment corrections without adding a separate travel charge.

The 0.025 m height tolerance is a connection rule, not source elevation accuracy or the tolerance for gradient sampling.

The mode rules to reapply are:

| Path/equipment | General | Wheelchair |
|---|---|---|
| Ordinary stairs, escalators and travelators | Allow | Exclude |
| Ordinary lifts | Allow | Allow |
| Stair lifts and wheelchair aids | Exclude | Allow |
| Path with WheelchairBarrier=1 | Apply other general rules | Exclude |
| Enabled=false | Exclude | Exclude |

Allow means eligible for selection, not compulsory use. Preserve source records even when a selected mode excludes travel.

## 4. Rebuild original and derived costs for every source

**Explanation for the team**

For A→B→C→D, all sections are processed again. A→B and C→D retain their valid Tobler calculations; reviewed B→C can use an estimated time. We preserve both what the original calculation produced and what the selected routing model uses.

**Steps we will take**

- [X] Calculate horizontal polyline distance for every usable piece. Hospital distances remain metres; no walking or lift seconds are added.
- [X] Rebuild the original source profile before topology splitting. Preserve the provider's radian gradient magnitude, use ordered height change for its sign, and retain separately signed intervals.
- [X] Preserve the equal-height sampling rule: four distinct internal positions, repeat once only if still flat, at most eight internal samples plus endpoints. Use original XYZ interpolation, seed `20261013` with stable source derivation, exact height equality and the same samples for reverse travel. Do not restart sampling on fragments.
- [X] Evaluate Tobler using stable arithmetic on healthy eligible non-lift intervals in both modes:

  ```text
  slope = tan(signed_gradient_radians)
  speed_kmh = 6 * exp(-3.5 * abs(slope + 0.05))
  time_seconds = horizontal_length_metres * 3.6 / speed_kmh
  ```

- [X] Compute approved fallback intervals using the recorded parameters:

  ```text
  flat_speed_mps = (6 * exp(-3.5 * 0.05)) / 3.6
  estimated_seconds = horizontal_length_metres / flat_speed_mps
                    + uphill_seconds_per_metre * total_ascent_metres
                    + downhill_seconds_per_metre * total_descent_metres
  ```

- [X] Accumulate ascent and descent through original vertices; a rise and fall do not cancel. Exchange ascent/descent for reverse travel. Preserve original unavailable values and failure reasons alongside the finite estimated directional costs and model/review identifiers.
- [X] Apply the fallback only to reviewed model-failure intervals, not every steep or merely expensive path. Identify interval failures and overflowing piece totals separately. Unsupported or unapproved intervals retain unavailable time; healthy neighbouring intervals remain usable. Do not cap the provider gradient, average neighbouring gradients, make a nonzero crossing free or flatten a height change.
- [X] Preserve original source evidence as immutable provenance and add a separate derived cost profile. If both a rise and fall occur within B→C, calculate their contributions separately. Explicitly distinguish original-source validity, derived routing availability and model uncertainty.
- [X] Split by overlapping original/derived intervals. Verify horizontal-distance conservation and directional cost conservation separately for each time scenario. A new finite fallback total must not erase an original unavailable-total diagnostic.
- [X] Charge **30 seconds on entry per original lift PedestrianRouteID**, zero for continuing that identity's graph pieces, and another 30 seconds for another lift. Non-lift travel resets identity; leaving and re-entering a lift starts another use. Waiting remains zero. Three consecutive distinct lifts cost 90 seconds.

The distance-plus-height formula is a project adaptation of documented [GRASS walking-cost methods](https://grass.osgeo.org/grass-stable/manuals/r.walk.html). It is a modelling assumption, not a correction to source geometry or a measured wheelchair speed. No GRASS installation is needed for this formula.

## 5. Recompile all graph outputs and comparison evidence

**Explanation for the team**

The main output is the complete rebuilt network. A separately identified baseline records the result with fallback time sections excluded, so later journeys can show whether an estimate changed the chosen route. Both scenarios must otherwise use identical source data, directions, mode rules and non-fallback policies.

**Steps we will take**

- [X] Rebuild the four primary matrices: general time, wheelchair time, general distance and wheelchair distance. Also compile baseline general/wheelchair time matrices with approved fallback intervals excluded.
- [X] Keep physical parallel edges and source identities. For a repeated state pair, select the cheapest permitted transition and keep its mapping; do not sum alternative edges. Preserve explicit zero-cost entries and lift states.
- [X] Extend `build_graph(...)` / `read_graph(...)` to select the primary or baseline time scenario explicitly, with primary as the default for new outputs. Keep the existing mode/metric arguments; identify policy/schema versions so readers cannot silently confuse old and new outputs.
- [X] Return actual node/edge GeoDataFrames and SciPy sparse matrices with state/transition mappings. Spatial and review outputs must identify original status, selected cost model, derived directional times, affected source positions and estimated-section warnings.
- [X] Save GeoPackage layers, NPZ matrices, mapping tables, original/derived profile evidence, interval decisions, complete policies, manifests, software versions and hashes under a new Step 2 run.
- [X] Report all source accounting, eligibility, geometry/topology counts, finite/unavailable/estimated directions, components and changes against the retained snapshots. Record reasons for connectivity changes instead of requiring old component counts to remain identical.

## 6. Tests, full rebuild and coordinated publication

**Explanation for the team**

The whole network and every saved output are checked again. Passing an isolated B→C example is insufficient. Steps 2 and 3 form one coordinated rebuild; a partial or failed rebuild must not become the selected pair.

**Steps we will take**

- [X] Pass existing topology, floor, repeated-visit, lift, direction, wheelchair, cost-boundary, zero-cost and source-ID regressions, including both repaired lift connections and the repaired endpoint cluster.
- [X] Add fallback cases for flat, uphill, downhill, rise-and-fall, zero-horizontal/nonzero-height, numerical overflow, rejected review decisions and finite but expensive Tobler values. Check that unsupported cases remain explicit.
- [X] Verify split/reverse cost conservation, original profile preservation, unchanged healthy edge costs, separate baseline/primary availability, and unchanged horizontal distance meaning.
- [X] Test A→D examples where the estimated direct route wins, the detour wins, no baseline route exists, a wheelchair restriction prevents the route, or several estimated sections occur.
- [X] Run the entire Step 2 pipeline from frozen Step 1, rebuild all topology/profiles/matrices, reopen every output and verify spatial data, nullable values, evidence, sparse mappings, shortest paths and hashes.
- [X] Validate and retain the new Step 2 candidate in its final immutable run directory, with manifest and success record, without changing the old `current` selection. Pass that explicit directory into the complete Step 3 rebuild; do not move it afterwards and break saved upstream references.
- [X] After both candidates pass, publish a completion record identifying the verified Step 2/Step 3 pair and select their successful runs. Keep each Step 3 run pinned to its own verified Step 2 directory, not a mutable upstream `current` link. Restore prior selections on publication failure; readers must not infer a pair by resolving two independent `current` links.
- [X] Update implementation reports, the context with actual HKT date/time, and affected overall/Step 4 instructions. New Step 4 work must reference the new pair and account for baseline comparisons. Keep future route caching and final ranking outside this build.
- [X] Keep successful artifacts tracked with Git LFS as appropriate. Do not automatically commit, push, delete the retained baseline or overwrite historical manifests.

## 7. Historical completion evidence

These records describe earlier completed work, not completion of the new rebuild:

| Snapshot | Earlier result |
|---|---|
| Frozen Step 1 `20261014T090829Z-20d0139c` | Preserved inputs; reused for this rebuild |
| Step 2 `20261014T105436Z-8fe534aa` | 89 tests; 397,225 nodes / 466,406 pieces; unavailable-time exclusion policy |
| Step 3 `20261014T145819Z-4d15d1a3` | 112 repository tests; 406,540 nodes / 475,721 pieces; 10,163 points |

The [Step 2 implementation and audit](step_2_implementation.md) records earlier repairs and limitations. Older superseded bulk runs were removed under the user's cleanup instruction; compact reports remain in `work/precomputed/history/`. Do not restore deleted bulk artifacts to satisfy older preservation wording. An estimated fallback does not mark the original geometry/gradient source issue resolved.

## Completed coordinated rebuild

Selected Step 2 **`20261016T075559Z-119a5636`** passed the complete build and save/reopen validation: **397,225 nodes / 466,406 pieces**, six matrices, **26 estimated pieces across 27 reviewed intervals in 26 source records**, and unchanged original evidence. Runtime: **543.38 seconds**; peak process memory: **1,990.672 MiB**.

Selected companion Step 3: **`20261016T080509Z-4c604c82`**. Both runs are selected through [the verified pair registry](../../precomputed/outputs/rebuild/current.json); Step 3 pins this exact Step 2 directory. **134 repository tests pass**. See [test evidence](../../precomputed/docs/rebuild_test_report.json), [source preservation and saved-artifact checks](../../precomputed/docs/rebuild_source_preservation.json), and [the implementation guide](step_2_implementation.md).

Original geometry/gradient limitations remain unresolved source evidence. The finite fallback is an accepted estimate, not a source repair. Future estate subcost caches and ranking remain outside Steps 2/3. Outputs are available to track with existing Git LFS attributes; no commit or push was performed.
