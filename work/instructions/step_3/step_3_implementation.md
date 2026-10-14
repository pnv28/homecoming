# Step 3: facility connections and augmented graphs

## Explanation for the team

Step 3 preserves all supplied estate, hospital, MTR access and bus-stop map points and selects one connection for each applicable mode and metric. Estates depart through outgoing terminal connectors. Destinations receive incoming terminal connectors. Terminal states have no physical XYZ node, so source-point heights remain unknown and terminals cannot connect unrelated paths.

Connections prefer ordinary outdoor paths, using the source `Location_label` field. Ordinary indoor paths are a flagged fallback within the same distance limit. Feature types outside the explicit ordinary-path allowlist and unknown locations are unsuitable for automatic attachment. Bridges, tunnels and equipment remain available for subsequent network travel under Step 2's mode rules.

Connectors are straight horizontal map-point approximations. Their distance counts toward the journey; time uses flat Tobler, `length * 0.6 * exp(0.175)` seconds. This does not establish a surveyed entrance, actual slope, or unobstructed passage. Every selected path level is marked uncertain. Near alternatives, distance ties, indoor fallback and connectors longer than 50 m are retained as review evidence. Bus connectors have a 50 m limit; other points have a 200 m limit, inclusive.

Shapely indexes original horizontal segments of mode- and cost-eligible physical pieces. Segment identity distinguishes repeated visits at the same XY position. Projection and interpolation recover the original vertex-index-plus-fraction position and HKPD height. Exact ties choose lower height, then source identity and source position. Alternative-level diagnostics use an absolute 1 m connector-distance window and a height difference greater than 2 m, or distinct known floors in a shared building. They do not alter junction tolerances.

All selections are collected before subdivision. Reused nodes must belong to the selected source/piece, satisfy the 0.10 m / 0.025 m tolerances and a short intervening source traversal, and permit the terminal's departure or arrival direction. New nodes subdivide one source only. The original cost profiles are reconstructed from complete original XYZ geometry and compared against saved evidence, including sampling and classifications. Pieces apportion overlapping original intervals without fragment resampling. Direction, availability, lift identity and directional costs are conserved.

## Implementation and use

The public functions are in `estate_ranking.attachments`:

```python
from estate_ranking.attachments import attach_points, read_attached_graph

# Reopen the selected successful Step 3 output.
graph = read_attached_graph(wheelchair=False, metric="time")
graph.nodes          # physical Point Z GeoDataFrame
graph.edges          # physical LineString Z GeoDataFrame
graph.entities       # original GeoDataFrames by entity type
graph.attachments    # statuses and selected Point Z geometry; null if not attached
graph.connectors     # positive-length 2D lines; zero-distance mappings in attachments
graph.terminals      # entity/attachment -> terminal state mapping, including exclusions
graph.states         # physical/lift states and separate terminal states
graph.matrix         # directed SciPy CSR, with deliberate stored zero-cost entries
graph.edge_mapping   # one mapping row per CSR entry; negative edge_index = connector

# Costs to all routing states, with infinity for unreachable states.
costs = graph.costs_from_entity(graph.entities["estate"].id.iloc[0])
```

`attach_points(physical, entities, evidence_directory=None)` takes a Step 2 physical graph and a dictionary of original point GeoDataFrames keyed by `estate`, `hospital`, `mtr_access` and `bus_stop`. A reopened physical graph requires its frozen Step 2 directory as `evidence_directory`. The returned `AttachedPoints` contains the augmented physical graph, entities, attachment/connector GeoDataFrames, candidate reviews and subdivision validation. `attached_routing_graph(...)` compiles a selected mode/metric and adds terminal states. `costs_from(node_index)` reduces costs to physical nodes only; `costs_from_entity(...)` retains the terminal states for future target reduction.

From the repository root:

```sh
PYTHONPATH=work/src .venv/bin/python -m estate_ranking.step_3
PYTHONPATH=work/src .venv/bin/python -m unittest discover -s work/tests -v
```

The production builder freezes Step 2 `20261014T105436Z-8fe534aa` and Step 1 `20261014T090829Z-20d0139c`. It verifies success identities, policies, all Step 2 manifest artifact hashes and seven Step 1 frozen hashes, then rechecks them before publication. Implementation hashes and installed package versions are recorded. No additional dependency is required.

## Outputs and acceptance

Successful runs live under `work/precomputed/outputs/step_3/runs/`, selected through `current`. `attachments.gpkg` stores physical nodes/edges, original point layers, selected attachment points and positive-length connector lines. CSV files store memberships, candidate reviews, routing states, transitions and terminal mappings; NPZ files hold the four matrices. Policies, frozen references, manifests and JSON/Markdown validation reports accompany the spatial data. Unchanged original network geometry and profile evidence are referenced in the retained Step 2 snapshot through repository-relative paths.

Required checks verify point accounting, selection counts, connector limits and costs, subdivision conservation, exact spatial/attribute/null roundtrips, terminal roles, arrival from lift states, matrix/mapping roundtrips, shortest-path relaxation and upstream lift/endpoint regressions. Both weak and strong component labels are saved in each routing state's table. Coverage, distance quantiles, warnings, exclusions and unattached counts are in the validation report. Failed builds retain the previous successful selection and leave upstream snapshots unchanged.

Estate-to-target subcosts, hospital preference selection and final ranking remain later work.

## Full-data result

Selected run: `20261014T145819Z-4d15d1a3`. All **112 tests pass**. The successful build retains **10,163 original points**, records **20,814 mode/metric selections**, and produces **406,540 physical nodes / 475,721 pieces**. It splits 7,252 parent edges, adding 9,315 single-source nodes.

| Type / mode / metric | Eligible | Attached | Unattached | Excluded |
|---|---:|---:|---:|---:|
| bus_stop/general/time | 8848 | 8812 | 36 | 416 |
| bus_stop/wheelchair/time | 4130 | 4096 | 34 | 5134 |
| estate/general/distance | 244 | 244 | 0 | 0 |
| estate/general/time | 244 | 244 | 0 | 0 |
| estate/wheelchair/distance | 244 | 244 | 0 | 0 |
| estate/wheelchair/time | 244 | 244 | 0 | 0 |
| hospital/general/distance | 44 | 44 | 0 | 0 |
| hospital/wheelchair/distance | 44 | 44 | 0 | 0 |
| mtr_access/general/time | 598 | 598 | 0 | 13 |
| mtr_access/wheelchair/time | 276 | 276 | 0 | 335 |

The [full validation report](../../precomputed/outputs/step_3/current/validation_report.md) includes connector distance quantiles, warnings, graph/component counts, exact reopen checks and the preserved upstream endpoint/lift regressions. No commit or push was performed.
