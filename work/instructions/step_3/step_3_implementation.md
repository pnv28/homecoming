# Step 3: facility connections and augmented graphs

Last updated: 2026-10-16 16:21:12 HKT (UTC+08:00)

## Explanation for the team

Selected Step 3 **`20261016T080509Z-4c604c82`** was rebuilt completely from the new verified Step 2 **`20261016T075559Z-119a5636`** and unchanged frozen Step 1. All **10,163** supplied estate, hospital, MTR access and bus-stop map points are preserved. Estates depart through outgoing terminal connectors; destinations receive incoming connectors. Terminals have unknown height and cannot connect unrelated paths.

Primary time graphs allow the reviewed distance-and-height estimates. Baseline time graphs exclude those estimates. Their attachment selections are calculated separately under identical connector rules, then all source positions are collected before shared physical subdivision. This preserves fair comparisons even when an estimate changes which path can accept an attachment. In this particular full dataset no attachment selects an estimated piece directly; estimated sections remain available during network travel.

Connections prefer ordinary outdoor paths inside **200 m** for estates/hospitals/MTR or **50 m** for buses, then ordinary indoor paths inside the same threshold. If neither qualifies, the indexed search expands to the closest suitable outdoor path, or indoor path if no suitable outdoor candidate exists anywhere in the dataset. These distances are search/warning thresholds, not rejection limits. Eligibility, direction, enabled-path and scenario availability checks continue to apply. Automatic attachment excludes bridges, tunnels, stairs and equipment interiors, including vertical zero-horizontal-run segments. Eligible equipment remains usable during network travel.

Connectors are straight horizontal map-point approximations. Their length counts toward the journey; flat Tobler time is `length * 0.6 * exp(0.175)` seconds. They do not establish surveyed entrances, actual slope or unobstructed passage. Source heights remain unknown; interpolated network attachment heights retain HKPD metadata. Unknown levels, near alternative levels, distance ties, indoor fallback, non-bus connectors over 50 m and all above-threshold connections are flagged.

Shapely indexes original horizontal segments. Segment identity distinguishes repeated visits at the same XY. Exact ties choose lower height, then stable source identity and position. Near-level diagnostics retain the 1 m distance window and greater-than-2 m height difference, or distinct known floors in one building. Junction tolerances stay **0.10 m horizontal / 0.025 m height**.

Selections are collected before subdivision. Node reuse requires the selected source/piece, tolerances, a short source traversal and suitable direction; otherwise a new source-only node is created. Every piece recovers original profile evidence and the separately reviewed derived profile. Distance and both time scenarios conserve parent/source costs; fragments do not restart sampling. Original direction, mode flags and lift identities remain. Lift entry costs 30 seconds per original lift identity, with free continuation and zero waiting.

## Implementation and use

```python
from estate_ranking.attachments import read_attached_graph

graph = read_attached_graph(wheelchair=False, metric="time")
# For comparison, use scenario="baseline" with metric="time".
graph.nodes          # physical Point Z GeoDataFrame
graph.edges          # physical LineString Z GeoDataFrame, original and selected cost evidence
graph.entities       # original GeoDataFrames by entity type
graph.attachments    # primary/baseline statuses and selected Point Z geometry
graph.connectors     # positive-length 2D lines; zero-distance cases use explicit mappings
graph.terminals      # selected mode/metric/scenario entity-to-terminal mapping
graph.states         # physical/lift states plus separate terminal states
graph.matrix         # directed SciPy CSR, including deliberate stored zero-cost entries
graph.edge_mapping   # one mapping row per CSR entry; negative edge_index means connector

costs = graph.costs_from_entity(graph.entities["estate"].id.iloc[0])
```

`attach_points(physical, entities, evidence_directory=None)` returns augmented physical and original entity GeoDataFrames, attachments, connectors, candidate reviews and validation. A reopened physical graph requires its explicit frozen Step 2 directory as evidence. `attached_routing_graph(...)` compiles the chosen mode/metric/scenario and terminals. `costs_from_entity(...)` retains destination terminal costs; `costs_from(node_index)` reduces to physical nodes.

Default readers use [the verified pair registry](../../precomputed/outputs/rebuild/current.json). Explicit directories inspect historical runs; Step 3 pins its own upstream run, not a changing `current` link. Rebuild the complete pair from the repository root:

```sh
PYTHONPATH=work/src .venv/bin/python -m estate_ranking.rebuild
```

No additional dependency is needed. Fresh candidates validate before atomic paired selection; publication rollback is tested. No commit or push was performed.

## Outputs and acceptance

The selected immutable directory is [outputs/step_3/runs/20261016T080509Z-4c604c82](../../precomputed/outputs/step_3/runs/20261016T080509Z-4c604c82/). `attachments.gpkg` stores physical nodes/edges, original point layers, attachment points and connector lines. CSV stores memberships, candidate reviews, states, transitions and terminals. Six NPZ matrices store four primary mode/metric graphs and two baseline time graphs. Policies, frozen references, manifests, package versions and validation reports accompany them. Unchanged original source geometry and profile evidence are referenced through the retained Step 2 directory.

Completed checks verify all original points, primary/baseline counts, flagged thresholds and costs, topology/subdivision conservation, exact spatial/attribute/null/Z preservation, terminal directions, lift-state arrival, matrix/mapping roundtrips, shortest-path relaxation and real source-ID lift/endpoint regressions. Both weak and strong component labels remain in routing state tables. Independently, all **34 artifact hashes**, implementation and upstream hashes, GeoPackage integrity, public readers and terminal invariants passed. The complete repository suite passes **134 tests**.

## Current full-data result

- **20,814 primary + 20,238 baseline records**, preserving 10,163 original points.
- **406,561 physical nodes / 475,742 pieces**; split 7,268 parents, adding 9,336 nodes/pieces.
- **29,256 positive-length connector records** across scenarios/modes/metrics; no zero-distance mappings in this dataset.
- All eligible records attach; exclusions remain visible. Attachment does not guarantee estate-to-target reachability.
- Build runtime: **430.851 seconds**.

| Type / mode / metric | Eligible | Attached | Unattached | Excluded |
|---|---:|---:|---:|---:|
| bus_stop/general/time | 8848 | 8848 | 0 | 416 |
| bus_stop/wheelchair/time | 4130 | 4130 | 0 | 5134 |
| estate/general/distance | 244 | 244 | 0 | 0 |
| estate/general/time | 244 | 244 | 0 | 0 |
| estate/wheelchair/distance | 244 | 244 | 0 | 0 |
| estate/wheelchair/time | 244 | 244 | 0 | 0 |
| hospital/general/distance | 44 | 44 | 0 | 0 |
| hospital/wheelchair/distance | 44 | 44 | 0 | 0 |
| mtr_access/general/time | 598 | 598 | 0 | 13 |
| mtr_access/wheelchair/time | 276 | 276 | 0 | 335 |

The time rows have the same counts in the baseline scenario; distance is saved once per mode. Baseline records are comparison selections, not additional source points.

**Warnings that remain:** every selected point's level is uncertain; source points are accepted map approximations. Candidate reviews preserve alternative levels, lower-height tie assumptions, indoor fallback and longer connectors. **36 general / 34 wheelchair bus records per time scenario exceed 50 m**, with maxima **5,209.271 m / 5,161.979 m**. Such long straight connectors may cross unmapped barriers and are not verified walks. Their finite costs and explicit flags follow the expanded-search policy; they must remain visible to later routing/ranking users. Original gradient/geometry defects remain preserved alongside estimates. No unavailable source record has been silently declared repaired.

The [full validation report](../../precomputed/outputs/step_3/runs/20261016T080509Z-4c604c82/validation_report.md) contains distributions, warnings, matrices/components and reopen evidence. See also [test evidence](../../precomputed/docs/rebuild_test_report.json), [source/artifact preservation audit](../../precomputed/docs/rebuild_source_preservation.json), [public-reader smoke checks](../../precomputed/docs/rebuild_reader_verification.json) and [the completed plan](step_3_plan.md).

Step 4 remains to implement estate-to-target subcost caches, selected/all-hospital reduction and complete route comparisons. Its plan uses a shared general-network hospital distance result for both modes and primary/baseline transport time results. Final score combination remains undecided.

## Retained historical result

Old Step 3 `20261014T145819Z-4d15d1a3` remains available with its original reports and artifacts: 112 tests at that time, 406,540 nodes / 475,721 pieces, four matrices, and 36 general / 34 wheelchair bus records unattached under the former hard distance limits. Those historical reports are unchanged. The new build changes both fallback policy and the connector threshold policy; comparisons with that old snapshot must not attribute every difference solely to fallback time.
