# homecoming

A local website for reviewing a PRH application, ranking Hong Kong estates, exploring their walking connections, and calculating a walk between two selected points.

## Run locally

From this project's `final/` directory, with Python **3.9–3.12**:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python run.py
```

Open **http://127.0.0.1:8000**. Keep that terminal running. Stop with Ctrl+C.

On the development computer, the already-installed parent environment can also run it:

```sh
cd final
../.venv/bin/python run.py
```

The data, application code, form template, fonts, and geographic context are included here. The parent `work/`, `data/`, and `analysis/` folders are not runtime dependencies. This is a source-folder application: keep `src/`, `assets/`, `config/`, and `precomputed/` together when copying it to another computer. A fresh Git checkout requires Git LFS to retrieve the large saved artifacts.

## Operator workflow

1. Enter a DeepSeek API key in the opening modal, or continue with manual input.
2. Upload a completed PDF. Typed, scanned, and handwritten forms are sent as relevant rendered page images to DeepSeek for extraction. Handwriting/checkbox accuracy needs operator review.
3. Review the prefilled name, household size, allocation area, and wheelchair mode. Choose a preferred hospital if needed. All fields are editable; unknown wheelchair evidence requires an explicit choice.
4. Press **Yes, search**. Extraction never clicks this button. Editing preferences also does not automatically run another search.
5. Explore the complete estate list. Click an estate, then its Bus stop, MTR access, or Hospital tab. Choose standard/HD WebP, PNG, or interactive SVG. SVG supports drag, wheel/pinch zoom, zoom buttons, reset, and section-cost tooltips.
6. The AI Overview appears after the confirmed search when DeepSeek is connected. It explains the computed top three; it does not calculate the ranks. API failures leave the ranking usable.

For an offline demonstration, enter `Alex Chan`, choose `Urban`, leave general walking and the nearest hospital selected, then press Yes, search. This synthetic profile exercises the real saved results without sending an application or buying an API request.

The upload panel also offers synthetic typed and scanned PDFs. Both describe fictional Alex Chan, a two-member household, Urban, and a family member with wheelchair-dependence code 1. With DeepSeek connected, they should prefill wheelchair routing for operator review. The scanned example has no extractable text, so it exercises image reading.

**Plan a walk** accepts map clicks, coordinates in latitude/longitude order, or named estates/hospitals/MTR access points. Start and destination can be swapped. The Kennedy Town example fills two real points, then waits for you to press **Find a walk**. Arbitrary endpoints need a suitable mapped path within 200 m. Unreachable routes are reported explicitly.

## What is already computed

- Every estate/hospital pair: **244 × 44 = 10,736** distance/status records. **6,323** are reachable in the saved pedestrian model.
- Fastest eligible bus-stop and MTR-access walking times for every estate, both modes and primary/baseline evidence scenarios. Missing routes retain their reasons.
- The selected Step 4 run is `20261016T102523Z-8e69faad`, including the two reviewed hospital-origin corrections. Compatible earlier graphs and source evidence are packaged alongside it.
- Standard/HD WebP and SVG maps are indexed in `precomputed/maps/index.json`. Identical displays share files. `progress.json` records full preparation coverage.

Serving a prepared map does not run a new shortest-path search or render a new image. PNG exports convert a prepared WebP. Arbitrary Start → End routes are calculated on demand and cached under `runtime/`.

Route backgrounds use the **complete original pedestrian geometry** underlying `analysis/maps/hong_kong_paths_precise`, with no random sampling or wheelchair filtering. Brown paths provide geographic context; the selected route uses a heavier blue line with a white outline. Dashed brown connections, green lifts, and purple estimated-time sections retain their original meanings. The background is decorative and does not imply that every visible path is eligible for the selected mode.

The local 5 m Hong Kong DTM is averaged into a georeferenced **20 m shaded-relief display layer**, clipped to the land boundary. It changes only the appearance. Route geometry, elevations used by the model, costs, distances, times, and rankings remain those of the existing graphs. Terrain and original path data are bundled for offline use.

Interactive SVGs include twice the initial viewport width and height of surrounding context. Zoom and pan stay inside that coverage. At close zoom, the local app adds original vector paths for the visible area, keeping the network sharp; larger views use the complete offline background. Selected routes are vector geometry at every zoom. The interactive legend stays below the map, and endpoint markers keep a readable screen size while zooming. Downloaded SVGs retain their title, legend and scale; they are self-contained, with embedded raster terrain/context and vector routes, and require no online tile service. See the [terrain route preview](docs/terrain-route-preview.webp) and [wider interactive context](docs/route-surroundings-preview.png).

## Prepare and verify maps

The map-generation command is resumable. It reads saved route links, checks summed costs, and produces standard WebP (1,200 px), HD WebP (3,000 px), and SVG for every distinct reachable cached display, including all hospital choices and tied transport winners:

```sh
PYTHONPATH=src .venv/bin/python scripts/precompute_maps.py --workers 3
PYTHONPATH=src .venv/bin/python scripts/verify_bundle.py --maps
```

It records unavailable routes without making fictitious images. Original Steps 1–5 outputs remain unchanged. The full asset build is a preparation task; ordinary app startup does not repeat it. Do not run two preparation processes against the same map directory simultaneously. Ctrl+C finishes pending renders and saves a checkpoint for a later resume.

`assets/maps/terrain_relief.png` and its georeferencing/provenance JSON are already prepared. To recreate them from the original parent `data/organized/supplementary/terrain/Whole_HK_DTM_5m.zip`, install `requirements-dev.txt` and run `scripts/prepare_basemap.py` before regenerating maps. The source archive is needed only for this development step. Shared original-network/terrain tiles are cached in `precomputed/maps/basemap/`; on-demand route cache keys include the map-renderer version so older displays cannot be returned after a renderer update.

After a renderer update, `scripts/prune_maps.py` previews obsolete generated files; add `--apply` to remove them. It retains all current route identities, including maps still pending in a resumable build, and never visits the original graph artifacts.

`scripts/package_data.py` is a development utility for assembling this folder from the original `work/` tree; it is not needed to run the copied application. `scripts/verify_bundle.py` checks packaged fingerprints and numeric parity without requiring that original tree.

## Model interpretation

Bus and MTR destinations minimise **walking time**, not straight-line distance. Vehicle journeys, fares, waiting, opening hours, and live lift outages are outside this model. Endpoint connections are approximate and entrance levels are unknown; relevant saved warnings appear in the interface.

Hospital distances use the **shared general walking network**, including when wheelchair transport mode is selected. These are not certified wheelchair-accessible hospital journeys. General and wheelchair transport use the existing adopted speed approximation; wheelchair mode changes path/destination eligibility.

Each component cost scales as `100*x/(x+k)` with bus `k=600 seconds`, MTR `k=900 seconds`, and hospital `k=5000 metres`. The total is the normalised weighted sum, lower is better. Equal weights are the default. A zero weight excludes that component from the total. Missing positive-weight components produce an incomplete estate with no total/rank; all such estates remain listed after complete ones. Category filtering recomputes ranks. This is an accessibility comparison, not a PRH eligibility or allocation decision.

## DeepSeek and session data

The adapter uses the documented vision-capable `deepseek-flash` model at `https://api.deepseek.com`. It validates a supplied key through the models endpoint. No key is embedded in the project. Real provider availability and OCR accuracy must be checked with your own key; automated provider checks use synthetic responses.

API keys, confirmed applicant profiles, extraction outputs, and overview results are kept in server memory for the local session. Uploaded PDFs are rendered in memory; browser previews use a local object URL. Recognised HD300E templates send the name/disability and allocation-choice regions of pages 1–2; other layouts send rendered page regions up to the 12-page/15 MB limit. Relevant images leave the computer for DeepSeek when extraction is requested. Overview requests omit applicant identity and finances.

**Clear session** removes the session's key, results, and jobs. Restarting the server clears in-memory sessions. Geographic map assets and arbitrary-route caches are reusable, non-applicant data and remain on disk. Bind only to localhost for the intended hackathon use.

## Checks and project layout

The delivered build passed **162 existing engine tests**, **17 application/routing/map tests**, full fingerprints/format/dimension checks for **21,786 prepared map files**, and browser checks covering operator review, hospital selection, exports, SVG controls, a newly calculated walk, and mobile layout. Twenty-five cached-route samples also matched the public engine reader's section costs and coordinates exactly. The background's 465,892 features and 1,963,912 XY vertices matched the original FGDB used by `analysis/maps` exactly. See [the verification report](docs/verification.json), [interface preview](docs/preview.png), [results preview](docs/results-preview.png), and [walking preview](docs/walk-preview.png).

```sh
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
PYTHONPATH=src .venv/bin/python scripts/verify_bundle.py --maps
PYTHONPATH=src .venv/bin/python scripts/verify_routes.py
```

`tests/browser_check.py` exercises the actual UI, operator gate, exports, SVG controls, and mobile layout using Playwright and an isolated browser profile. It currently uses the development computer's Helium browser executable; change that path or use an installed Playwright Chromium for another computer. Browser dependencies are listed separately in `requirements-dev.txt`. QA reports/screenshots are generated in ignored `runtime/qa/`.

```text
src/homecoming/       Web app, browser interface, document/AI/map/route services
src/estate_ranking/   Reused engine, copied unchanged
precomputed/outputs/  Compatible successful Step 1–5 runs and amendment history
precomputed/maps/     Prepared WebP/SVG library and coverage index
config/              Existing policies, stable-ID registry link, reviewed overrides
assets/              Local map geography, fonts, and blank application template
scripts/             Bundle preparation, map generation, verification
tests/               Application integration and browser checks
docs/engine/         Copied engine implementation guides
runtime/             Ignored temporary caches and QA output
```

The copied engine guides preserve their original relative links and refer to the earlier workspace layout. [PLAN.md](PLAN.md) records the agreed design and decisions.
