# Step 5: scale the three subcosts and rank estates

Last updated: 2026-10-16 18:28:20 HKT (UTC+08:00)

Status: **plan and decisions recorded; Step 5 code and ranking outputs are not implemented yet**. The requested Step 4 hospital amendment is separate implementation work. Read the project context and current Step 4 implementation guide before implementing this plan.

## 1. What Step 5 receives and what it produces

### Explanation for the team

Step 4 has already calculated the route costs. An estate has a bus walking time, an MTR walking time and a hospital distance. These are different measurements: seconds cannot be added directly to metres. Step 5 converts each measurement into the same numerical range, combines the converted values and puts the estates in order.

Step 5 does not rebuild the map, select new connections or calculate shortest routes. It reads the saved Step 4 results. Choosing a specific hospital reads that estate–hospital pair; choosing no hospital uses the nearest reachable hospital among all 44. The hospital measurement stays the same in wheelchair/general mode and primary/baseline transport scenarios.

The result must be an actual GeoDataFrame: an estate table that keeps its map geometry, original identity/category, three original measurements, converted costs, final cost, rank and explanations. Keep all estates in the requested category, including those with missing routes. Changing the category changes the candidate list and ranks, not the cost formula or destinations searched.

### Steps we will take

- [X] Agree that Step 5 consumes Step 4 results without new routing.
- [ ] Implement in `work/src/estate_ranking/step_5.py`, using the amended successful Step 4 cache through its public readers.
- [ ] Resolve the selected Step 4 run once per calculation. Pass that explicit saved directory to every reader so concurrent selection changes cannot mix snapshots.
- [ ] Validate mode, scenario, hospital identity and allocation category. Supported categories are Urban, Extended Urban, New Territories and Islands; `None` means all estates.
- [ ] Preserve `requested_hospital_id` even if that hospital is unreachable. An empty winning-target list must not erase the user's selection.
- [ ] Do not modify Step 4 records or add a new route/connection approximation.

## 2. Convert each measurement to a bounded cost

### Explanation for the team

Use this function for every available nonnegative measurement:

```text
scaled cost = 100 × x / (x + k)
```

Here `x` is the original time or distance. The reference value `k` is the measurement that receives **50 points**. Zero receives zero points; larger measurements approach 100. Smaller points mean better access.

| Component | Original units | Reference k | Scaled cost when x = k |
|---|---|---:|---:|
| Bus | Walking seconds | 600 seconds = 10 minutes | 50 |
| MTR | Walking seconds | 900 seconds = 15 minutes | 50 |
| Hospital | Horizontal network metres | 5,000 metres = 5 km | 50 |

These are midpoints, **not journey limits**. A hospital 10 km away remains eligible and receives approximately 66.67 points. A hospital 15 km away receives 75. An unreachable hospital is missing, not a distance above 5 km and not a score of 100.

The formula deliberately compresses large differences. Going from 5 km to 10 km adds about 16.67 points; going from 10 km to 15 km adds about 8.33. This makes the cost bounded, but it means differences between very poor connections have less influence. The raw measurements must remain visible. A finite but exceptionally large Tobler time remains a finite cost; do not cap, delete or silently repair it in Step 5.

### Steps we will take

- [X] Adopt `100 * (x / (x + k))` with bus/MTR/hospital references 600/900/5,000 in seconds/seconds/metres.
- [ ] Apply the fixed references identically across modes, scenarios, category filters and hospital selections. Do not fit them to the currently displayed estates.
- [ ] Keep valid zero costs. Preserve missing routes as missing values using the saved status/reason.
- [ ] Reject inconsistent inputs: an `ok` route with missing, negative or non-finite cost, or an unavailable route with a numeric cost. Do not disguise these as ordinary unreachability.
- [ ] Keep full precision for calculations and sorting. Round only in presentation; floating-point saturation near 100 must not be used to manufacture missing-route penalties or a new raw-cost tiebreaker.
- [ ] Add `bus_scaled_cost`, `mtr_scaled_cost` and `hospital_scaled_cost` columns alongside the original measurements and units.

## 3. Combine the converted costs

### Explanation for the team

The agreed starting point gives the three components equal influence:

```text
final_cost = (bus_scaled_cost + mtr_scaled_cost + hospital_scaled_cost) / 3
```

For example, scaled costs of 20 for bus, 40 for MTR and 60 for hospital give a final cost of 40. Good access to one component can compensate for poorer access to another. The formula does not guarantee a minimum standard for each component.

Weights will be settings. With weights 2, 1 and 1, bus receives half the influence and each other component receives a quarter. Normalisation means dividing each weight by their sum; users need not enter fractions that add exactly to one. Changing weights is a cheap scoring calculation over cached data, not new routing.

A zero weight means a component is displayed but not required for that particular total. For example, hospital weight zero allows a total based on bus and MTR even if hospital access is unavailable. Default weights are all positive, so all three routes are required by default.

### Steps we will take

- [X] Set default raw weights to `bus=1, mtr=1, hospital=1`; normalise to equal thirds.
- [ ] Accept a complete dictionary with exactly the keys `bus`, `mtr`, `hospital`. Reject missing/unknown keys, booleans, negative/non-finite values and an all-zero selection.
- [ ] Normalise safely by first dividing by the maximum weight, then by the resulting sum, avoiding overflow for large finite weights.
- [ ] Compute the weighted mean only when all positive-weight components are available. Select active components explicitly so `0 * missing` cannot contaminate a valid total.
- [ ] Record supplied weights, normalised weights, fixed references and active components in result metadata and saved scoring policy.
- [ ] Preserve connector, unknown-level and estimated-time warnings. Do not invent an additional quality penalty.

## 4. Put complete and incomplete estates in order

### Explanation for the team

A missing route must not look like a conveniently low cost. An estate missing a required component has no total cost that can be compared fairly with complete estates. We will still show its available information and why something is missing.

The user chose this ordering: complete estates first; incomplete estates afterward, with the greatest number of available required components first. For default weights, two available components come before one, and one comes before none. Within the same incomplete group, use estate name and then ID. Do not average only the available components, assign a score of 100 to missing values, or assign incomplete estates numerical ranks.

For complete estates, smaller final cost ranks better. Exactly equal unrounded final costs share a competition rank: costs ordered as 10, 20, 20, 30 receive ranks 1, 2, 2, 4. Name order only makes equal-cost rows display predictably; it does not break their shared rank.

Kam Peng remains in the data. Its unavailable hospital connection is accepted for this pedestrian-only model because reaching the mainland requires boats. Do not delete the estate, invent a walking link across water or substitute a straight-line hospital measurement. If its hospital component has positive weight, its ranking result is incomplete.

### Steps we will take

- [X] Agree complete-first ordering and incomplete ordering by most available required components, then name/ID.
- [X] Keep Kam Peng's hospital result unavailable without additional repair work.
- [ ] Add `required_component_count`, `available_required_component_count`, `missing_components` and `ranking_status` (`complete` or `incomplete`).
- [ ] Add nullable `final_cost` and nullable integer `rank`; incomplete rows have neither.
- [ ] Filter by `housing_district`, then calculate ranks within the returned candidate set. Sorting uses full precision, followed by `name_en.casefold()` and estate ID; use the preserved estate `name` if English name is missing.
- [ ] Return an empty GeoDataFrame with the same schema for a valid category with no records. Unknown category names are errors.
- [ ] Preserve all tied Step 4 winning destination IDs independently of estate-ranking ties.

## 5. Python interface, saved outputs and existing packages

### Explanation for the team

The public scoring function will return the ranking table directly. The normal settings use the selected amended Step 4 cache. A caller can supply an explicit historical directory to reproduce results from that version. Choosing weights or a hospital changes only the inexpensive calculation over the saved measurements.

The command-line build will save the default four views: primary/general, primary/wheelchair, baseline/general and baseline/wheelchair. Each view contains 244 estates when no category is selected. These outputs are spatial tables, not new graph files.

Existing NumPy and pandas already provide vectorised arithmetic, missing-value handling, stable sorting and competition ranking (`rank(method="min")`). GeoPandas and Pyogrio already handle spatial tables and GeoPackage storage. Reuse them. No additional pip, npm or Homebrew dependency is needed for these operations.

### Steps we will take

- [ ] Provide `rank_estates(housing_district=None, wheelchair=False, hospital_id=None, scenario="primary", weights=None, step_4_directory=None) -> GeoDataFrame`.
- [ ] Preserve all source estate and Step 4 columns, then add the scoring/ranking columns above. Metadata identifies the exact Step 4 run/manifest, mode, scenario, category, requested hospital and scoring policy.
- [ ] Provide a CLI using the project's `.venv`: `PYTHONPATH=work/src .venv/bin/python -m estate_ranking.step_5`. Optional `--hospital-id`, `--bus-weight`, `--mtr-weight`, `--hospital-weight` and `--step-4-directory` select one recorded policy for the saved views.
- [ ] Save under `work/precomputed/outputs/step_5/runs/<run_id>/`, with a successful atomic `current` selection. The four GeoPackage layers are `primary_general`, `primary_wheelchair`, `baseline_general`, `baseline_wheelchair`.
- [ ] Save `scoring_policy.json`, exact Step 4 references, validation report, implementation/artifact hashes and SUCCESS metadata. Preserve the referenced upstream run and earlier successful Step 5 runs.
- [ ] Provide `read_rankings(wheelchair=False, scenario="primary", directory=None)` for these saved whole-candidate views. It restores list/nullable types and GeoDataFrame metadata. Use `rank_estates` for category filtering, custom weights or a different hospital; do not filter a saved view and leave its old ranks unchanged.
- [ ] Serialize nested lists/dictionaries as JSON text in GeoPackage and restore them on reading. Keep unknown costs/ranks nullable. Successful spatial outputs stay tracked with the existing Git LFS GeoPackage rule.
- [ ] Default readers reject a Step 5 selection whose pinned Step 4 cache no longer matches the current selection. Explicit saved directories reopen their frozen history.
- [ ] Stage and validate before selection; a failed run leaves previous successful outputs selected. Do not commit, push or delete historical outputs automatically.

## 6. Tests and completion criteria

### Explanation for the team

Tests must check the scoring choices, not repeat routing work. The amended Step 4 cache is the source of truth for journey costs. Step 5 must preserve those costs and explain every missing score.

### Steps we will take

- [ ] Verify scaling at 0, k/2, k and 2k: expected scores are 0, approximately 33.3333, 50 and approximately 66.6667. Check increasing nonnegative costs never improve scores and test very large finite inputs.
- [ ] Verify equal weights, proportional weights, a zero-weight missing component, rejection of invalid weights and safe normalisation of large weights.
- [ ] Verify complete-first ordering, descending available-required count, missing total/rank, name/ID stability and exact competition ties. Test costs that display identically after rounding but differ at full precision.
- [ ] Verify category filtering does not change component scaling or surviving estates' total costs; ranks are recomputed within the category.
- [ ] Verify no hospital selection uses Step 4's nearest reachable institution; an explicit hospital uses its pair and retains its ID when unreachable. Verify all exact destination ties survive.
- [ ] Verify hospital costs and scaled hospital scores match across both modes/scenarios, while transport values follow the selected view.
- [ ] Verify Kam Peng remains visible and incomplete under the default positive hospital weight; Kwai Luen and Chun Shek use amended hospital costs.
- [ ] Disable Dijkstra while exercising all scoring/saved-result readers. Confirm no graph or Step 4 artifact is modified.
- [ ] Verify default four-view accounting (244 rows each), EPSG:2326 estate geometries, raw/converted costs, nullable/list metadata and save/reopen preservation.
- [ ] Test incompatible references, unknown IDs/categories, corrupt artifacts and failure preserving the previous selection. Run the repository suite once implementation is complete.
- [ ] Update the context, design and this checklist with actual results and HKT date/time. Do not mark implementation complete merely because the decisions or plan are recorded.
