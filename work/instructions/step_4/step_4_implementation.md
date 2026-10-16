# Step 4 cache and reader guide

Updated 2026-10-16 18:30:12 HKT (UTC+08:00). Selected run: `20261016T102523Z-8e69faad`.

Step 4 consumes one verified record from `precomputed/outputs/rebuild/current.json`. It pins the retained Step 2 and Step 3 run directories and their manifest hashes. It uses the five saved Step 3 graphs and scenario-specific terminal mappings, plus the two explicit hospital-only origin overrides documented below. It does not rebuild graph topology or remove estimated edges from the primary attached graph to construct a baseline.

The primary time scenario includes healthy Tobler costs and reviewed distance-and-height estimates, using 6 seconds per metre uphill and 2 seconds per metre downhill in both eligible modes. The baseline uses the separately saved graph and attachments excluding those estimates. The October 14 graph is historical evidence, not this baseline. Both scenarios accept the saved expanded connectors and their full costs and warnings.

## Build and saved artifacts

From the repository root:

```sh
PYTHONPATH=work/src .venv/bin/python -m estate_ranking.step_4
# Reuse the current successful cache and recalculate only two reviewed hospital origins:
PYTHONPATH=work/src .venv/bin/python -m estate_ranking.step_4 --amend-hospitals
PYTHONPATH=work/src .venv/bin/python -m unittest discover -s work/tests -v
```

Candidates are staged in ignored `work/cache/step_4_staging/`. A successful candidate moves to `work/precomputed/outputs/step_4/runs/<run_id>/`; an atomic `current` link selects it after verification. Rebuild and Step 4 process locks coordinate CLI builds. The pair registry and all frozen artifact hashes are rechecked before publication. Failures retain diagnostics and preserve the prior selection. Successful outputs are trackable; GeoPackages, compressed NumPy links and the large JSON results use Git LFS. Builds do not commit, push, or remove previous runs.

| Artifact | Contents |
|---|---|
| `frozen_inputs.json` | Exact selected Step 2/3 pair, retained paths and manifest hashes |
| `cache_policy.json`, `model_policy.json`, `attachment_policy.json` | Calculation rules and frozen upstream assumptions/review |
| `results.json` | Exact numeric costs, statuses, tied destinations, route records, search mappings and comparison tables; unavailable costs are JSON null |
| `results.gpkg` | Estate geometry/attributes and estate-location spatial tables for hospital costs, transport groups and both comparisons; nested fields are JSON text |
| `*_links.npz` | Shared pruned numeric trees: state, parent state and original transition-row index, with one block per root search |
| `hospital_overrides.json` | Snapshot-pinned reviewed hospital-only connections; original Step 3 attachments remain unchanged |
| `amendment_parent.json` | Parent Step 4 run, retained directory and manifest hash for derived amendment runs |
| `validation_report.json` | Full-data accounting, all-path checks, comparison changes, warnings, runtime and payload size |
| `SUCCESS.json`, `manifest.json` | Successful identity, code hashes, frozen references and all artifact hashes |

The original full calculation used 1,020 production searches: 488 primary transport searches, 488 baseline transport searches, and 44 reverse hospital searches. An amendment reuses those results and runs just **two forward hospital searches**; a future full build also applies the two reviewed overrides after its original searches. Current route mappings retain 1,022 search identities. Independent forward distance checks are additional validation work. Every attached eligible bus/MTR destination participates in minimum selection; all destinations with the exact unrounded minimum survive. One optimal path per destination is retained, rather than every alternative route with equal cost.

Hospital searches use the transposed general-distance graph. Saved links recover estate-to-hospital transitions in the original direction. Hospital metres never contain lift seconds or Tobler costs. All 244 × 44 pairs are recorded, including unreachable pairs.

## Reviewed hospital-origin amendment

Kwai Luen and Chun Shek originally attached to isolated path pockets. The reviewed replacement connections use existing ordinary outdoor nodes in the same frozen graph:

| Estate | Node / source path | New horizontal connector | Nearest hospital distance |
|---|---|---:|---:|
| Kwai Luen | 374121 / 120017850 | 7.385986 m | 1,842.014074 m |
| Chun Shek | 227647 / 290061624 | 6.062483 m | 2,457.147476 m |

`work/config/step_4_hospital_overrides.json` pins the exact Step 3 run/manifest, node IDs, XYZ coordinates and supporting source IDs. `hospital_amendment.py` validates the source is an allowed ordinary outdoor path, the node permits departure and its physical state is outside a lift. A changed snapshot, source or node fails rather than silently applying old indices.

The amendment calculates each estate's 44 hospital costs from its reviewed node, adding the straight horizontal estate connection. It replaces **88 pair records**, including their route links, while preserving every other route, all transport minima/comparisons and every Step 2/3 artifact. Each corrected estate can reach 29 hospitals; other hospital pairs remain unavailable where the graph has no directed connection. This produces 58 newly reachable pairs compared with the original full cache.

Saved `origin_override` metadata preserves both the original and replacement attachment. The route reader prepends the replacement 2D connector, then follows the cached directed graph transitions; it never traverses the old estate connector or performs a search. Network geometry retains XYZ, but no estate height is invented. Overrides apply to hospital results in both modes/scenarios, without changing bus/MTR results.

The four new warning labels mean:

- `reviewed_hospital_origin_override`: this hospital journey uses the explicitly reviewed replacement origin.
- `map_point_approximation`: the estate pin is the accepted approximate map location.
- `point_height_unknown`: its height is unknown; the connector cost counts horizontal distance.
- `entrance_and_level_unverified`: this does not verify a physical gate, passage, ramp or matching estate level.

Kam Peng's 44 hospital records remain unavailable and unchanged. Reaching the mainland requires boats, outside this pedestrian-only hospital model. The estate remains visible; no cross-water shortcut or straight-line hospital substitute is introduced.

Every primary/baseline transport winner and every baseline journey to a primary winner is included before tree pruning. Repeated route records retain both `winner` and `primary_winner_comparison` purposes. An unreachable comparison is saved with a null cost, a reason and no route links.

## Public Python interfaces

```python
from estate_ranking.step_4 import (
    read_subcosts, read_hospital_costs, read_transport_comparisons, read_route,
)

estates = read_subcosts(wheelchair=False, scenario="primary")
pairs = read_hospital_costs()
groups, same_targets = read_transport_comparisons(wheelchair=True)

# Use IDs returned by the result tables.
estate_id = estates.id.iloc[0]
target_id = estates.bus_target_ids.iloc[0][0]
sections = read_route(estate_id, target_id)

# Explicit saved runs can be reopened after the selected Step 2/3 pair changes.
historical = read_subcosts(directory="work/precomputed/outputs/step_4/runs/<run_id>")
```

All four interfaces return actual EPSG:2326 GeoDataFrames. Comparison reading returns a pair of GeoDataFrames. Every reader accepts `directory=None` as its final optional argument. The default selection rejects an incompatible selected rebuild pair on every call, including calls served by an already opened cache. Explicit directories use their frozen references and remain available as history. First opening verifies local and upstream artifacts; subsequent calls reuse the open cache. Readers never invoke Dijkstra.

`read_subcosts(wheelchair=False, hospital_id=None, scenario="primary", directory=None)` returns one row per estate with its preserved estate attributes/geometry and separate `bus_time_s`, `mtr_time_s`, `hospital_distance_m`, target-ID lists, units, statuses, reasons and warning lists. A selected hospital chooses its cached pair. `requested_hospital_id` remains a column and metadata value even when that pair is unavailable. With no selected hospital, the reader returns the minimum reachable hospital distance and every exactly tied hospital. All hospital requests resolve to `shared_general_distance`, regardless of wheelchair mode or transport scenario. Missing numeric values appear as pandas missing values in GeoDataFrames and as null in the saved JSON; valid zero remains zero.

`read_hospital_costs(directory=None)` returns all 10,736 shared pair records at their estate locations. `cost` has unit `metres`; `target_id` identifies the hospital. `hospital_cache` in frame metadata identifies the shared calculation. Pair records include route IDs, status/reason, warnings and endpoint connector evidence.

`read_transport_comparisons(wheelchair=False, directory=None)` returns group and same-target comparisons. Group rows contain both minima, both tied destination lists, reachability/cost/winner changes, selected-path changes and attachment changes. Same-target rows compare each primary-winning target against the baseline journey to that target, including baseline unavailability and its reason. `delta_seconds` is primary minus baseline, and is missing when either required cost is unavailable. A changed attachment is reported separately from an estimated-section traversal.

`read_route(estate_id, target_id, wheelchair=False, scenario="primary", directory=None)` returns cached sections in travel order, including network XYZ and 2D connector geometry. It includes actual transition cost/unit, horizontal distance, direction, source/edge identifiers, connector identity, lift entry/continuation model, estimated-time use, review IDs, original failure status and warnings. Zero-distance connector movements remain explicit rows with null line geometry. Network sections with zero horizontal distance retain their original vertical XYZ geometry. Route metadata in `frame.attrs` includes status, reason, cost, purposes, physical-path identity, estimated seconds, connector positions/distances/warnings and the shared hospital-cache marker when applicable.

Unknown estate, hospital or target IDs produce explicit errors. A known transport destination whose journey was not cached also produces an explicit error; it does not trigger a new search. Baseline retrieval supports both baseline winners and primary-winner comparison targets. Recorded unavailable routes return empty GeoDataFrames with status/reason in `attrs`.

## Reconstruction and comparison identity

`estate_ranking.routes` supplies predecessor traversal, transition lookup, ordered geometry and summed-cost checks. The arbitrary-coordinate example uses this same reconstruction module while retaining its own attachment workflow. Step 4 never invokes that arbitrary-coordinate workflow.

Saved transition indices refer to the frozen scenario graph, preserving allowed directions, barriers, equipment eligibility and lift-state costs. Network path identity uses original source IDs, section positions and travel directions. Connector identity uses the entity, terminal role, actual original source/position, XYZ attachment and connector distance; scenario labels and scenario-specific attachment-ID suffixes do not count as changes. Both scenarios share the same jointly subdivided physical sections from Step 3.

Each selected primary path records whether it actually traverses estimated time, its estimated seconds, review IDs, original failure reasons and model warnings. Baseline and distance paths do not acquire estimated-time labels from physical source evidence. Reaching a destination with an estimate-enabled graph does not itself mean the chosen route uses estimates.

Straight connectors, uncertain entrance levels and expanded searches remain accepted approximations. These results describe walking and connector costs only; they include no vehicle journey, waiting or fares. Step 5 now has an agreed [scoring/ranking plan](../step_5/step_5_plan.md), including bounded scaling, equal-thirds weights and incomplete ordering; ranking implementation remains pending.

## Selected full-data results

The selected run pins Step 2 `20261016T075559Z-119a5636` and Step 3 `20261016T080509Z-4c604c82`.

| Result | Count |
|---|---:|
| Shared hospital pairs | 10,736 |
| Reachable / unavailable hospital pairs | 6,323 / 4,413 |
| Primary / baseline transport-group rows | 976 / 976 |
| Reachable general groups per scenario | 478 of 488 |
| Reachable wheelchair groups per scenario | 452 of 488 |
| Same-target primary-winner comparisons | 931 |
| Tied transport groups, both scenarios combined | 2 |
| Deduplicated route records | 12,599 |
| Reachable cached routes checked | 8,186 |
| Independent forward hospital pairs checked | 264 |
| Selected primary routes using estimates | 7 |
| Changed group costs / winner sets / selected path sets | 7 / 1 / 7 |
| Changed group reachability / attachment positions | 0 / 0 |

All 931 same-target comparisons are reachable in this snapshot; synthetic tests also cover unavailable comparisons. One reachable baseline comparison is additional to its baseline winning destination and is retained after pruning. There are no missing predecessor links or cycles.

The original full calculation took **139.70 seconds** before final publication checks. The selected amendment uses **two production searches** and took **67.72 seconds** through serialization/all-path checks, before final hash and reader checks. Its payload is **52,763,085 bytes (50.32 MiB)** before small manifest/success/report overhead. Pruned links reference the frozen upstream geometry rather than duplicating every route's geometry. Parent snapshots and their manifests remain retained.

`connector_warnings` counts occurrences at cached route endpoints, including repeated endpoints across pairs/scenarios: `alternative_level`=772, `connector_above_threshold`=4, `distance_tie_lower_height_assumption`=588, `entrance_and_level_unverified`=88, `level_uncertain`=25,110, `long_connector`=1,622, `map_point_approximation`=88, `point_height_unknown`=88, `reviewed_hospital_origin_override`=88. These are endpoint occurrences, not counts of distinct estates or source defects. The four override labels each occur 88 times because two hospital origins appear in 44 pairs each, including unavailable pairs. `upstream_attachment_warnings` separately counts the unchanged original Step 3 attachment records, including 140 beyond-threshold occurrences and 20 indoor fallbacks. Nonwinning destinations and their original evidence remain in Step 3.

The repository suite passes **151 tests**, including 13 original Step 4 tests, four hospital-amendment tests and the existing coordinate-route and graph regressions. See [the test output](../../precomputed/docs/step_4_tests.txt). The [independent amendment review](../../precomputed/docs/step_4_amendment_review.json) checks preservation against the original full cache, unchanged transport link files, Kam Peng and GeoPackage override metadata. The additional published-cache check is reproducible with:

```sh
PYTHONPATH=work/src .venv/bin/python work/tests/check_step_4_cache.py
```

It exercises all four public readers with Dijkstra disabled, both modes/scenarios, selected/shared hospital views, changed/estimated/long-connector route samples and unavailable routes. It also reopens every spatial result table to compare exact costs and estate geometries, then runs the real source-ID lift/endpoint regressions against all five frozen graphs. Its report is [step_4_reader_acceptance.json](../../precomputed/docs/step_4_reader_acceptance.json).

The real-data coordinate example also passed after reconstruction extraction: the documented sample produced **319.1 m / 263.39 seconds** with summed-cost verification and PNG/JSON/CSV artifacts in ignored cache. That coordinate-example result is historical evidence from the original Step 4 implementation. The current [test summary](../../precomputed/docs/step_4_test_report.json) records the 151-test amendment regression run.
