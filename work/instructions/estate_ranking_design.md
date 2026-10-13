# Estate ranking: current design and implementation stages

Updated 13 October 2026 after the user's policy decisions and the full Step 1 rerun. Read [project_context_and_decisions.md](project_context_and_decisions.md) for the complete decisions and [routing_policy.json](../config/routing_policy.json) for their machine-readable snapshot. These instructions supersede the earlier universal no-stairs outline.

## Purpose and final output

A user selects one of the four Housing Authority allocation categories: Urban, Extended Urban, New Territories or Islands. They may select a hospital. A future `wheelchair` parameter changes path/equipment and transport eligibility.

Each candidate estate has three separate subcosts:

| Subcost | Algorithm and units |
|---|---|
| MTR | Minimum reachable gradient-adjusted walking time to an eligible MTR access point, in seconds |
| Bus | Minimum reachable gradient-adjusted walking time to an eligible boarding stop/service, in seconds |
| Hospital | Pedestrian-network distance to the selected hospital, or minimum reachable distance to any of all 44 institutions if none is selected, in metres |

Use network journeys rather than straight-line distances. Filter the candidate estates by allocation category without cutting the pedestrian network or destinations at category boundaries.

**The method of combining the three subcosts into the final estate cost is deliberately undecided.** Preserve all three and their target IDs, units and reachability. Do not select weights or normalisation automatically, take one minimum across the three categories, or add raw metres and seconds. Final handling of wholly unreachable target groups will be decided with the combining method.

## Shared assumptions and mode rules

All routes are assumed always open. Do not load, export, join or evaluate `AccessTime`/`AccessTimeDetails`, or introduce journey date/time inputs. Retain `AccessTimeID` only as inert source evidence. Dataset publication/update dates describe provenance.

Use supplied estate/hospital map points as accepted approximations; verified entrance collection is not required. WGS84 is accepted for estate/hospital/bus longitude-latitude inputs. iGeoCom WGS84 and the network's HK1980 grid/HKPD heights are provider-confirmed. Work horizontally in EPSG:2326 and preserve network XYZ and EPSG:5738 height metadata.

| Rule | General / wheelchair=false | Wheelchair=true |
|---|---|---|
| Ordinary stairs, escalators, travelators | Retain | Exclude |
| Ordinary lifts | Allow | Allow |
| Stair lifts and wheelchair aids | Exclude | Allow |
| Paths marked WheelchairBarrier=1 | This flag alone does not exclude them | Exclude |
| Bus operators | KMB, CTB, GMB | KMB, CTB |
| MTR starting candidates | All 611 mapped access records | 276 records with mobility evidence |

Apply equipment/path rules to both MTR candidate pools; starting counts are not guaranteed final eligible/reachable counts. Bus operator selection applies to services before aggregating stops. Joint services qualify through an included operator; a mixed GMB/KMB stop is not discarded when its KMB service qualifies. Other operators remain preserved in source data but are outside the bus subcost.

There is no maximum ramp-slope cutoff for now. Keep all original rows so both modes can be calculated later. Candidate flags prepare the rules; they do not establish real network connectivity or physical equipment coordinates. Wheelchair speed is explicitly deferred, and current walking estimates must not be presented as a wheelchair travel-time model.

## 1. Harmonise and prepare the data — implemented and rechecked

### Explanation for the team

The source files use different formats and identifiers. Preparation gives them consistent coordinates, identities and field types while preserving the original information. The result is six actual GeoPandas GeoDataFrames, persisted as layers in a GeoPackage. Reference tables without geometry are kept in SQLite, and source/rule/review records are kept in JSON/CSV.

Original inputs are in `work/original_data/`; selected older supplementary files are copied into its `reference/` subfolder with their origin and checksum recorded. The existing local `.venv` is used. GeoPandas 1.0.1 and pandas 2.3.3 were installed with approval; no Homebrew packages were installed.

### Steps we take

1. Inventory every configured input and its hash; verify the seven selected reference copies against their originals. Record package versions, explicit assumptions and `routing_policy.json`.
2. Safely extract/inspect the 3D geodatabase and load its paths plus five non-schedule supporting tables. Preserve every part, vertex, height, timestamp and source code. Skip both schedule tables.
3. Load estate, hospital, access/station and bus points; transform X/Y to EPSG:2326, retaining original coordinates and unknown point heights.
4. Match all 244 estates to the documented allocation lookup. This data crosswalk is an estate-category mapping, not pedestrian-crossing data. Keep administrative districts separate.
5. Decode the supplied MTR dictionary. Create 98 physical station IDs independent of lines, translate all 100 legacy IDs, and link all 611 access points. Preserve 276 mobility records and unresolved evidence. Integrate physical IDs into the spatial layers and SQLite relationships, and embed the eight JSON masters in the same run.
6. Reconcile all 9,264 stops against 69,364 bus/GMB service rows. Preserve raw `stopPickDrop` and derive unknown code **99**, assumed pickup/dropoff both. Known codes remain 1=dropoff, 2=pickup, 3=both. Derive general and wheelchair boarding candidates from the permitted services.
7. Prepare mode-candidate flags without deleting paths or points. General paths retain stairs and exclude stair lifts; wheelchair paths exclude ordinary stairs/escalators/travelators and WheelchairBarrier=1. MTR evidence/equipment selection follows the table above. Missing evidence stays visible.
8. Validate identities, geometry, coordinates, source accounting, estate assignments and required relationships. Save diagnostics for unresolved source references; do not invent missing station identities or equipment locations.
9. Write staged GeoPackage/SQLite/JSON/CSV outputs. Reopen every geometry/attribute/null/reference value, including the actual GeoDataFrames, and recheck all 23 source hashes before selecting the successful run.

The full rerun passed with **476,153 spatial records, zero blocking errors, 14 warning groups and 31 passing tests**. Warnings retain actual MTR evidence gaps, missing supporting network references, both Castle Peak Hospital reference versions and allocation-proxy provenance. They are not failed preservation checks. See the [validation report](../precomputed/outputs/current/validation_report.md).

Finished results are under `work/precomputed/outputs/current/`, selected from successful snapshots in `outputs/runs/`. This folder includes `harmonised.gpkg`, `reference_tables.sqlite`, `schema.json`, `source_manifest.json`, `model_policy.json`, validation/rejection reports, IDs and `mtr_master/`. Failed candidates remain in `work/cache` without replacing the prior successful data/IDs. Successful precomputed outputs remain trackable in Git.

From `work/`:

```sh
PYTHONPATH=src ../.venv/bin/python -m estate_ranking.step_1 --config config/step_1.json
PYTHONPATH=src ../.venv/bin/python -m unittest discover -s tests -v
```

Load the actual GeoDataFrames:

```python
from estate_ranking.export import read_outputs, read_geodataframe

frames = read_outputs()  # dictionary of all six GeoDataFrames
estates = frames["estates"]
network = read_geodataframe("precomputed/outputs/current", "network")
```

The loaders restore nullable integer/boolean/string fields and retain CRS, geometry Z and vertical metadata. Internal `SpatialDataset` containers support efficient ingestion; they are not the public output type. See [both Step 1 plans](step_1/) for detailed explanations and completed checklists.

## 2. Build directed pedestrian connections and route costs — later work

### Explanation for the team

A graph connects usable pieces of the pedestrian network. A point where a bridge crosses a road in the map is not automatically a junction; heights and source references matter. Direction restrictions are separate from uphill/downhill direction.

### Steps we will take

1. Apply the selected mode's candidates/equipment rules, retaining raw sources and explicit unknowns. Inspect `Enabled` semantics where needed without reintroducing schedules. Resolve missing supporting references only where the topology needs them.
2. Build nodes/connections at appropriate endpoints and junctions. Split paths where a real connection meets their interior. Retain separate levels and avoid merging every coincident XY location. Choose and verify connection tolerances against the source accuracy/data.
3. Keep each source feature's gradient magnitude `n`, measured in radians. Use +n for rising heights and -n for falling heights in travel order. Reversing travel reverses those signs; the provider `Direction` field controls permitted travel, not slope sign.
4. When endpoints A/B have equal heights despite a nonzero/differing gradient indication, take four repeatable random internal samples along the actual XYZ polyline. Interpolate from its existing vertices. If those samples remain level, take four additional distinct samples between the same A/B, giving ten points total. Stop after at most two rounds. If all remain level, assume relatively flat and use derived zero slope, preserving the raw gradient. If heights vary, order the points along the path and retain separately signed portions. Do not recursively create further sampling rounds.
5. For walking transport costs, use standard Tobler:

```text
slope = tan(signed_gradient_radians)
speed_kmh = 6 * exp(-3.5 * abs(slope + 0.05))
time_seconds = horizontal_length_metres * 3.6 / speed_kmh
```

This converts the provider angle to rise/run input without recalculating its magnitude from heights. Sum separately signed interval times; a climb followed by a descent must retain both costs. Sampling uses exact height equality for now and seed 20261013, recorded in the policy snapshot. Reuse canonical sample positions for reverse travel.

6. Use **30 seconds lift travel plus zero waiting time per lift use**, an accepted arbitrary assumption. Do not apply Tobler to a vertical lift or assign zero time from its zero horizontal length. Do not charge separately at every vertex. Other equipment timing and the wheelchair speed model remain to be specified.
7. For hospital costs, use horizontal network distance in metres without slope/time penalties. Do not add lift seconds to hospital metres. Both hospital and transport journeys respect the selected mode's physical rules and direction constraints.
8. Verify nonnegative costs, permitted directions, crossing levels and connectivity, including stairs retained for general mode and excluded for wheelchair mode. Report unreachable paths/targets explicitly.

Tobler was researched from the [user-supplied page](https://en.wikipedia.org/wiki/Tobler%27s_hiking_function) and [original report](https://escholarship.org/uc/item/05r820mz.pdf). Standard walking speed is about 5.04 km/h at zero slope. Its walking curve is adopted; wheelchair speed is deliberately deferred.

## 3. Connect estates and facilities to the graph — later work

1. Attach accepted estate/hospital map points and eligible transport access/boarding points to suitable paths. Preserve source positions alongside derived connections.
2. Use appropriate network levels and entrance/equipment evidence where available. Do not attach an access point to a nearby bridge solely because its XY distance is short.
3. Decide and verify connector distances/tolerances; show unusually long or implausible connections. Never assign unknown point heights to zero without evidence.
4. Split an edge at a legitimate connector position where needed. Attribute its length/cost consistently and preserve directionality.
5. Keep failed or uncertain connections visible. The terrain model remains optional for later connector checks and must not overwrite elevated network Z.

## 4. Compute and cache the three subcosts — later work

1. Compute estate-to-target journeys under the selected physical mode and metric. Directed time costs can differ in reverse travel.
2. Use the minimum reachable cost within each eligible MTR/bus group. For hospitals, use the selected hospital or the minimum reachable distance among all 44 institutions.
3. Cache target-level results so a future hospital choice can select the correct column without rerunning all paths. Retain mode, metric, policy/input version and target identity so incompatible results are not mixed.
4. Return MTR time, bus time and hospital distance separately, with the selected targets, units, reachability and relevant data-quality flags. An unreachable group must not receive a zero cost.
5. Use a shortest-path implementation appropriate to the directed network's size. Check the local environment first; additional graph libraries or faster engines require justification and installation permission if absent. No routing engine is implemented by Step 1.

## 5. Combine and rank — deliberately deferred

Filter estates to the selected allocation category, obtain their three subcosts for the chosen mode/hospital, then apply the final combining/scaling function once it is agreed. Return the final estate cost with its separate MTR, bus and hospital subcosts and supporting flags.

Weights, scaling, reachability treatment, tie handling and the final combining method are not selected. Earlier illustrative weighted sums or distance-decay thresholds are not approved defaults.

## Remaining evidence and implementation boundaries

Physical MTR identity matching is resolved. Source gaps remain: facility IDs 70/888; unknown or unnamed access/equipment evidence; certain unlocated facility descriptions; three equipment-description differences; and stations without mapped mobility points. Missing terminal/floor/site/building references and both Castle Peak Hospital reference versions remain preserved for relevant later investigation. Current allocation categories are complete; new estates require verification because the lookup uses documented geographic proxies.

Step 1 prepares and preserves data and agreed candidate selections. It does not establish connected accessible journeys, execute the signed-gradient sampling/Tobler routing model, calculate the three subcosts or produce a final ranked list. Continue with later stages using the current context and saved policy, keeping unresolved items unchecked.
