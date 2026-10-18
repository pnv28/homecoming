# Step 5 implementation and ranking reader guide

> **Archived development guide.** This copy preserves the original implementation record, workspace paths, commands, and relative links. Some linked plans, project-context documents, and reports were omitted from the standalone application, so those links may not resolve here.
>
> See [this guide in its original location on `development`](https://github.com/pnv28/homecoming/blob/development/work/instructions/step_5/step_5_implementation.md), the [development plans and project context](https://github.com/pnv28/homecoming/tree/development/work/instructions), and the [development reports](https://github.com/pnv28/homecoming/tree/development/work/precomputed/docs). For current standalone usage and implementation status, follow the [README](../../README.md) and [current implementation status](../implementation-status.md).

Updated 2026-10-16 20:34:38 HKT (UTC+08:00). Selected run: `20261016T122956Z-21343da6`, frozen to amended Step 4 `20261016T102523Z-8e69faad`.

All **162 tests** and the independent full-data acceptance pass. Each of the four views contains **244 estates**: general has **239 complete / 5 incomplete**, wheelchair has **225 complete / 19 incomplete**, in both scenarios. Missing default components are general bus/MTR/hospital **5/5/1** and wheelchair **17/19/1**. Counts overlap across components and are inherited reachability, not scoring errors. The build used **zero routing searches**, took **4.94 seconds** through save/reopen checks before final publication checks, and saved **5,152,539 bytes (4.91 MiB)** of payload before small report/manifest/success overhead.

The implementation is `work/src/estate_ranking/step_5.py`. It reads the amended Step 4 cache and returns actual EPSG:2326 GeoDataFrames. It performs no route searches and preserves every original estate/subcost field, geometry, target list, missing reason and warning.

## Use the ranking functions

From the repository root, use the existing local environment:

```sh
PYTHONPATH=work/src .venv/bin/python
```

```python
from estate_ranking.step_5 import rank_estates, read_rankings

# Read the published all-estate, equal-weight, nearest-hospital ranking.
all_estates = read_rankings()
wheelchair_estates = read_rankings(wheelchair=True)

# Recalculate ranks within one allocation category using cached journey costs.
urban = rank_estates("Urban", wheelchair=False)
print(urban[["name_en", "bus_time_s", "mtr_time_s", "hospital_distance_m",
             "final_cost", "rank", "ranking_status", "missing_components"]])

# Different weights do not require new routes or a new Step 4 cache.
custom = rank_estates("Urban", weights={"bus": 2, "mtr": 1, "hospital": 1})

# Supply an actual hospital ID from Step 4 to select that hospital explicitly.
# chosen = rank_estates("Urban", hospital_id=hospital_id)

# The separately saved baseline excludes reviewed estimated-time sections.
baseline = rank_estates("Urban", wheelchair=True, scenario="baseline")
```

`rank_estates(housing_district=None, wheelchair=False, hospital_id=None, scenario="primary", weights=None, step_4_directory=None)` calculates inexpensive scores from saved measurements. `housing_district` accepts Urban, Extended Urban, New Territories, Islands or `None` for all estates. Use an explicit Step 4 saved-run directory for historical scoring. Unknown IDs/categories, nonboolean mode flags and invalid scenarios/weights raise errors.

`read_rankings(wheelchair=False, scenario="primary", directory=None)` opens one of the four published whole-candidate views, restoring list fields, nullable types, geometry and metadata. Its optional directory is a **Step 5** saved-run directory. For a category, hospital or weight change, call `rank_estates`; merely filtering a saved table would leave its ranks relative to the original larger candidate set.

## How a score becomes a rank

Each available cost becomes `100*x/(x+k)` with bus `k=600 seconds`, MTR `k=900 seconds`, hospital `k=5000 metres`. Zero gives zero points, each midpoint gives 50, and increasing costs approach 100. These reference values never filter routes or change with the selected estate category.

Default weights are equal thirds. A supplied dictionary must contain exactly `bus`, `mtr` and `hospital`, with finite nonnegative numeric values and at least one positive weight. Dividing by the maximum before normalising avoids overflow. Every positive supplied weight makes that component required, including a positive weight so small that its normalised float underflows. A zero-weight component remains displayed but is excluded from the total and completeness count.

Complete estates receive a weighted cost, sorted ascending. Exact unrounded equal totals share competition rank (`1,2,2,4`); display order within equal totals uses case-folded English estate name, falling back to `name`, then ID. No raw-cost tiebreaker is introduced when the bounded formula saturates at floating-point precision. The final numerical value is bounded to 0–100 to remove floating-point accumulation noise; original costs are never capped or changed.

Incomplete estates follow, ordered by the most available required components, then name/ID. Their total and numerical rank remain missing. Do not interpret missing as zero or 100. Source statuses and reasons explain which route is unavailable. An `ok` input with missing/non-finite/negative cost, or an unavailable input with numeric cost, stops scoring as inconsistent data.

| Added field | Meaning |
|---|---|
| `bus_scaled_cost`, `mtr_scaled_cost`, `hospital_scaled_cost` | Component costs on the common 0–100 scale; unavailable components stay missing |
| `required_component_count` | Number of positive-weight components |
| `available_required_component_count` | How many required components have available routes |
| `missing_components` | List of unavailable required component names |
| `ranking_status` | `complete` or `incomplete` |
| `final_cost` | Weighted bounded cost, nullable `Float64` |
| `rank` | Competition rank within the requested category/candidate set, nullable `Int64` |

Metadata records supplied/normalised weights, active components, fixed references/units, requested hospital, category, mode/scenario and the exact Step 4 run/manifest. Saved readers also expose the Step 5 run ID. Destination/warning lists returned by scoring are independently copied, so caller edits cannot change the in-memory source cache.

## Build and saved files

```sh
PYTHONPATH=work/src .venv/bin/python -m estate_ranking.step_5
```

The CLI also accepts `--hospital-id`, `--bus-weight`, `--mtr-weight`, `--hospital-weight`, `--step-4-directory` and `--output-root`. Each run saves the four views for one recorded hospital/weight policy. Defaults are no hospital selection and equal weights. Without a selected hospital, use the minimum reachable distance among all 44 and preserve all exactly tied hospital IDs.

The current output is `work/precomputed/outputs/step_5/current`, an atomic link to a successful `runs/<run_id>/` directory. Candidates and failure diagnostics stay in ignored `work/cache/step_5_staging/`. Existing rebuild/Step 4 locks and a Step 5 lock coordinate CLI publishers. Failed builds leave the prior selection intact. No commit, push or historical deletion occurs automatically.

| File | Contents |
|---|---|
| `rankings.gpkg` | Layers `primary_general`, `primary_wheelchair`, `baseline_general`, `baseline_wheelchair`, with all 244 estates per layer |
| `schema.json` | Original column order, logical/nullable types, JSON-encoded fields, CRS, row counts and GeoDataFrame metadata for each layer |
| `scoring_policy.json` | Formula, fixed references/units, supplied/normalised weights and missing/tie rules |
| `frozen_inputs.json` | Exact retained Step 4 path/manifest and its Step 2/3 pair |
| `validation_report.json` | Complete/incomplete and missing-component counts, exact save/reopen checks, runtime and output size |
| `SUCCESS.json`, `manifest.json` | Successful run identity, implementation hashes and artifact checksums |

Nested lists/dictionaries are JSON text inside GeoPackage; use the public reader to restore Python objects. Nullable rank/count/cost columns are restored from `schema.json`. The existing Git LFS GeoPackage rule covers successful spatial outputs; no additional dependency or storage format is required.

Default readers reject an incompatible selected Step 4 cache, including a changed selected graph pair. Explicit Step 5 directories can reopen historical outputs while their frozen dependencies remain intact. Building from an explicit historical Step 4 directory is allowed; if it differs from the current Step 4 selection, reopen that Step 5 result explicitly rather than expecting the default reader to accept it.

## Validation and accepted limitations

The build compares **every field, geometry, logical type and metadata value** after reopening each saved view. It verifies shared hospital measurements across all modes/scenarios, frozen upstream hashes, public-reader results and code identity before selection.

Run the unit/regression suite and independent full-data acceptance with:

```sh
PYTHONPATH=work/src .venv/bin/python -m unittest discover -s work/tests -v
PYTHONPATH=work/src .venv/bin/python work/tests/check_step_5_outputs.py
```

The independent check disables Dijkstra; compares all original costs/fields/geometries against Step 4; recomputes scoring, ordering and ranks; tests all category views, all 44 hospital selections and additional weight profiles; verifies the two amended hospital distances and Kam Peng; checks GeoPackage integrity; and confirms Step 4/graph artifacts are unchanged. Reports are [step_5_test_report.json](../../precomputed/docs/step_5_test_report.json), [step_5_tests.txt](../../precomputed/docs/step_5_tests.txt) and [step_5_reader_acceptance.json](../../precomputed/docs/step_5_reader_acceptance.json).

These scores inherit the accepted map-point/straight-connector approximations, uncertain entrance levels and shared wheelchair walking-time approximation from earlier stages. The bounded formula compresses large-cost differences and permits compensation between components. Hospital costs remain pedestrian-network distances, with no boat/vehicle links. Kam Peng remains visible and incomplete under default weights. No source route or accessibility evidence is repaired by ranking it.

The five general-mode incomplete estates are Cheung Kwai, Chun Shek, Kwai Luen, Nga Ning Court and Kam Peng. The first four lack bus and MTR results in the existing transport cache; Kam Peng also lacks a hospital result. Kwai Luen and Chun Shek's hospital-only correction is preserved, but their transport records remain unavailable, so they still have no default total/rank. In wheelchair mode, 17 estates lack both transport components and two more lack MTR access; the total incomplete count is 19. These missing-route outcomes are preserved source-cache results, not scoring failures.
