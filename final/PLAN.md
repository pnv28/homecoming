# homecoming — proposed local web application

Status: exploration and planning only, 16 October 2026. No application implementation, data migration, dependency installation, or changes to Steps 1–5 have been made.

## Confirmed scope

- A local hackathon application using the completed Python estate-ranking pipeline.
- Lowercase `homecoming` branding, a large PDF upload area, and an API-key modal on opening.
- Support typed PDFs and scanned/handwritten forms. Use DeepSeek for document reading and for the explanation above the ranking.
- Show an applicant summary, AI Overview explaining the top three, and a scrollable estate list. Clicking an estate reveals its destinations, routes, measurements, and score explanation.
- Static PNG/WebP maps with standard/HD choices; an interactive SVG viewer with zoom and pan.
- A separate on-demand route planner: select a start point and an end point. No batch routing requirement.
- Deliver the runnable application and its necessary data inside this root-level `final/` folder. Existing project folders remain available as the development/research archive.

## What the existing project contains

| Location | Role and treatment |
| --- | --- |
| `work/src/estate_ranking/` | The completed Python engine, including ingestion, graph construction, attachments, route recovery, caching, ranking, and audits. Reuse it. |
| `work/precomputed/outputs/` | Versioned successful outputs and selectors. Package the selected runs and their necessary dependencies. |
| `work/config/` | Routing policy, fallback review, hospital-origin overrides, source configuration, and identity selectors. Carry the needed policy/configuration into the package. |
| `work/tests/` | Existing regression and full-data acceptance checks. Preserve meaningful coverage for the packaged engine. |
| `work/examples/walking_route.py` | Existing arbitrary-coordinate route calculation and PNG rendering. Extract reusable routing behavior into the application service. |
| `work/examples/` and `work/precomputed/demos/` | Useful route demonstrations and example artifacts. |
| `work/instructions/` | Project decisions and implementation guides. Latest decisions and selected manifests take precedence over older notes. |
| `work/original_data/` | Source snapshots and dictionaries. Retain in the existing archive; copy only runtime/reproducibility inputs needed by the final package. |
| `work/cache/` | Extracted sources, temporary builds, and staging diagnostics. Do not copy the entire directory into the app. |
| `analysis/` and root `data/` | Earlier investigations, map renderers, source copies, crosswalks, and background geography. Reuse selected geographic assets rather than whole generated maps. |
| `THIS FORM.pdf` | Four-page English PRH template at the project root. Text is extractable; there are no AcroForm fields or annotations. It supplies no preferred-hospital field. |

Exploration covered the folder layout, source-module responsibilities, implementation/decision documents, public readers, frozen dependency references, cache sizes, routing example, map renderer patterns, and form text/structure. Binary datasets were inspected through metadata and public-reader samples; historical binary runs were not exhaustively re-audited.

### Selected data snapshot

| Stage | Selected run | Purpose |
| --- | --- | --- |
| 1 | `20261014T090829Z-20d0139c` | Harmonised source data and identities |
| 2 | `20261016T075559Z-119a5636` | Directed pedestrian graphs, costs, and source evidence |
| 3 | `20261016T080509Z-4c604c82` | Estate/facility attachments and augmented graphs |
| 4 | `20261016T102523Z-8e69faad` | Amended journey cache, destinations, and route links |
| 5 | `20261016T122956Z-21343da6` | Saved ranking views |

- 244 estates: Urban 109; Extended Urban 70; New Territories 60; Islands 5.
- 44 hospitals, with every estate/hospital pair represented in the journey cache.
- General default ranking: 239 complete and 5 incomplete estates. Wheelchair default ranking: 225 complete and 19 incomplete. These counts hold in both primary/baseline scenarios.
- The selected Step 1–5 directories total approximately 2.52 GiB before any additional retained amendment evidence, geographic assets, or new map caches. All of `work/precomputed/` is approximately 5.7 GiB because it also retains historical material.
- The recorded Step 5 suite passed 162 tests. This exploration did not rerun the whole suite.
- Fresh smoke checks succeeded: saved ranking approximately 1.34 s; subsequent Urban wheelchair ranking approximately 0.04 s; first cached bus-route recovery approximately 17.29 s including graph loading. These are observations on this computer, not response-time guarantees.

## Recommended architecture

Use Python FastAPI, Jinja2 HTML templates, plain CSS, and a small JavaScript layer. Serve it on localhost with Uvicorn. Python owns the pipeline, DeepSeek requests, PDF rendering, and image exports; the browser owns form interactions, list selection, and SVG navigation.

This permits a designed interface and direct calls into the existing engine without introducing a second application backend. No Next.js build, hosted Sites deployment, user accounts, or external database is needed for the agreed local scope.

Proposed package:

```text
final/
  PLAN.md
  README.md
  pyproject.toml
  requirements.lock
  config/
    ...required model policies and packaged configuration
  precomputed/
    outputs/
      ...selected runs, required references, and compatible selectors
    maps/
      ...optional warmed map assets
    bundle_manifest.json
  assets/
    maps/
      ...selected local background geography
    samples/
      application-form.pdf
      ...synthetic demonstration inputs
  src/
    estate_ranking/
      ...reused engine
    homecoming/
      app.py
      settings.py
      schemas.py
      api/
      services/
        documents.py
        deepseek.py
        rankings.py
        routing.py
        maps.py
        jobs.py
      prompts/
      templates/
      static/
  scripts/
    package_data.py
    verify_bundle.py
  tests/
  runtime/                     # ignored, generated local state
    map_cache/
    route_cache/
    temporary_uploads/
```

The eventual README will provide one setup command and one launch command from `final/`. The environment itself does not need to be copied into the package.

### Packaging existing data safely

1. Trace the selected readers' complete dependency paths, including profiles needed to split arbitrary endpoint attachments, frozen Step 2/3 references, Step 1 references where required, and the hospital-amendment evidence chain.
2. Copy the required immutable artifacts while preserving their internal relative layout, run IDs, and file contents. Recreate selectors inside `final/`; no selector may point back outside it.
3. Copy the engine into `final/src/estate_ranking/`. Its existing `parents[2]` root convention then naturally resolves to `final/`. Check every exception and config/source reference before declaring the bundle independent.
4. Preserve original checksummed manifests. If packaging needs extra path metadata, put that in a separate bundle manifest rather than rewriting old frozen records.
5. Verify the application with the original `work/`, `analysis/`, and `data/` unavailable as dependencies. Do not rebuild Steps 1–5 merely to move their files.
6. Add appropriate Git LFS handling for packaged large artifacts before any future commit. Do not copy `.git`, the existing virtual environment, failed staging builds, or every old map/export.

## Proposed user experience

### Open and upload

- A restrained layout with warm white surfaces, deep teal accents, readable typography, and lowercase `homecoming` at the top.
- On opening, a modal requests the DeepSeek API key. Validate it with a small request and show clear connection status; allow replacement later.
- Keep the key in server session memory and associate it with an opaque browser session. Never place it in source files, logs, generated reports, or persistent browser storage.
- A large drag-and-drop PDF box accepts the application form. Include a sample-template download and manual input so a network/API problem does not prevent ranking.
- Show extraction progress, then an editable applicant/profile panel beside the relevant PDF preview.

### Extract and review the form

The supplied PDF includes names, per-member disability codes in Part 1, and one housing allocation category in Part 5. The residential-address district is a different field and must not become the housing preference automatically. Preferred hospital must be supplied separately unless a different uploaded document explicitly states it.

Proposed extraction flow:

1. Validate PDF type, size, page count, and readability.
2. Extract text locally where available, and render relevant PDF pages as images. Preserve the page layout because checkbox marks and household-member columns carry meaning that plain text can lose.
3. Send images and useful text to a currently supported DeepSeek vision model. For this template, Parts 1 and 5 are the relevant areas; avoid sending unrelated financial/declaration pages when possible. Allow a general page-selection fallback for other form layouts.
4. Request structured fields with source-page evidence: applicant name, household display details, allocation category, wheelchair evidence per member, and unresolved fields. Validate the result against the application schema.
5. Do not guess illegible or conflicting selections. Mark missing/uncertain values for editing. Detect blank templates and offer manual completion.
6. Review category and wheelchair mode before ranking. Manual corrections take precedence. A hospital dropdown uses the existing 44 stable IDs, with “Nearest reachable hospital” as the default.

DeepSeek performs the visual reading/OCR. A separate OCR service is not proposed. Its current documentation describes image input, while the Responses guide says file inputs are unsupported. Therefore the initial integration renders PDF pages to supported images rather than assuming raw PDF inference. If direct PDF support becomes documented and works with the user's chosen model, the document adapter can use it later.

Additional ranking controls: equal weights by default; an optional advanced panel for bus/MTR/hospital weights. Applicant name and household information are for display; income, assets, and priority schemes do not alter this accessibility model. No PRH eligibility decision is proposed.

### Results

Above the estate list:

- Applicant name and compact profile: allocation category, mode, hospital preference, and active weights.
- An AI Overview describing why the top three rank as they do, including meaningful tradeoffs.
- A count of complete and incomplete results.

Desktop layout: a scrollable ordered list beside an estate-detail panel. On smaller screens, stack the detail panel below the selected estate. Retain all matching estates; incomplete entries remain at the end without invented numeric ranks or scores. An “All areas” selection can show all 244 estates.

Each list entry shows rank where available, estate name, final cost, bus/MTR walking times, hospital distance, and availability. Clicking opens:

- Bus, MTR, and hospital destination tabs, including all tied winners where relevant.
- Destination names and actual MTR access/exit identity when available.
- Route map, modelled walking time for transport, route distance, and route sections.
- Raw component values, scaled values, weights, and weighted contributions.
- Plain-language labels for estimated sections, long assumed connectors, unknown entrance levels, and unavailable journeys when relevant to that result.

Use “fastest walk to bus/MTR” rather than implying the winning target is the geographically closest stop/station. Hospital results use shortest pedestrian-network distance. The hospital route in wheelchair mode is still the existing shared general-network distance calculation; label it accordingly and do not describe it as a verified wheelchair route.

## Ranking and AI Overview contract

Reuse `rank_estates(...)` for category, mode, hospital, and weight changes; use `read_rankings(...)` for the saved defaults. Reuse `read_route(...)` to recover cached winner geometry. Changing a preference does not require rebuilding the graph or running new shortest-path searches for rankings.

For each available component:

```text
scaled cost = 100 * x / (x + k)
k_bus = 600 seconds
k_mtr = 900 seconds
k_hospital = 5,000 metres
final cost = sum(normalised weight * scaled component cost)
```

Lower cost ranks better. Default weights are equal thirds. Positive-weight components are required. Complete results sort first; incomplete results have no total/rank. Preserve exact tie rules and unavailable values.

After calculating the ranking, send DeepSeek a compact structured version of the full matching result list, the top-three IDs, actual preferences, component costs/contributions, and relevant warning flags. The system prompt explains the formula, units, equal weighting, mode rules, shared hospital calculation, missing-data behavior, and accepted approximations.

DeepSeek explains the computed order; the engine remains responsible for ranking. Require the response to reference existing estate IDs and the actual top three. Do not permit invented facilities, travel claims, eligibility claims, or numerical values. Validate structured responses and use computed values in the rendered explanation where possible. Keep applicant identity, ID-card numbers, finances, and the original PDF out of the overview request.

Rankings appear as soon as ready; the AI Overview may load afterward. An API failure leaves the list usable and offers a retry. Changes to preferences invalidate the old overview; stale responses cannot overwrite newer results.

## Map modes and exports

One route geometry feeds all display formats. HD changes raster size, not route selection or cost.

| Display | Proposed behavior |
| --- | --- |
| Static, standard | PNG or WebP, approximately 1,200 px on the longer side |
| Static, HD | PNG or WebP, approximately 3,000 px on the longer side |
| Interactive SVG | Vector route and local context, pan, wheel/pinch zoom, zoom buttons, reset-to-fit, endpoint labels, and section tooltips |

SVG is resolution independent rather than a higher-accuracy route. Preserve route vertices; simplify or limit background context only when necessary for browser performance. Clip background geography to the route's area. Do not ship the existing 50 MB whole-Hong-Kong SVG maps into every estate panel.

Use solid lines for network travel and dashed lines for assumed connectors. Add route markers and distinguish lifts/estimated sections where the data supports it. Offer downloadable SVG and static exports. Cache by snapshot, route identity, mode/scenario, format, resolution, and renderer version.

The offline default can reuse local pedestrian paths, coastlines, and nearby estate/facility labels. A street-map background remains an optional decision because it adds an online map dependency and a source/attribution choice. The interactive route itself must remain SVG in either case.

## On-demand route planner

A separate “Plan a walk” view lets the user set Start and End by clicking the map or entering latitude/longitude. Named estate/facility selectors can provide convenient point locations. Include swap and clear controls, wheelchair mode, and clear start/end markers.

- Find the fastest permitted walk under the existing time/lift model; show distance as a second measurement.
- Extract and adapt the coordinate example's endpoint attachment, joint splitting, routing, and reconstruction functions. Preserve direction, barriers, lift identity, original geometry, and estimated-time evidence.
- Confirm the endpoint-selection policy explicitly in implementation: the example currently limits its local candidate set to 200 m, whereas the full precomputed attachment builder can expand farther. For arbitrary map clicks, propose a clear “no nearby suitable path” result instead of silently adding a very long connector.
- Preserve no-route, unattached, zero-length, and invalid-coordinate outcomes. Do not substitute a straight line for an unavailable walk.
- Arbitrary start/end searches use temporary graph changes and never modify the frozen graph or estate rankings.
- Run calculation through a bounded background job, show progress, and cache repeated identical inputs with the selected snapshot/mode/policy in the key. Do not assume endpoint order is interchangeable.

For estate-to-cached-winner requests, reuse cached routes when the requested semantics match. For arbitrary endpoints, calculate a new route. Batch/all-estate routing is outside the agreed first version.

## Performance and local operation

- Start with one application worker so multiple processes do not duplicate large graph structures.
- Verify the bundle during setup/startup and preserve the public readers' snapshot compatibility checks. Avoid unnecessary repeated full-data loading per web request.
- Load ranking measurements first; lazily load the route graph and retain it for reuse. Use a bounded shared executor for heavy route/map tasks and protect non-thread-safe rendering operations.
- Warm commonly used route/map assets for the demo after correctness is established. Generated maps and coordinate results belong in `runtime/`, not immutable snapshots.
- Keep uploads/extractions in temporary or session-scoped storage; clear them when the session is reset. Persist reusable geographic/map caches without applicant identity or API keys.
- Serve fonts, scripts, and map context locally. Rankings and local routing remain usable without the internet; DeepSeek features require connectivity.
- Include a synthetic demonstration profile so the hackathon walkthrough does not depend on possessing a completed personal form.

## Implementation sequence after discussion

1. **Package the engine and data.** Establish `final/`, dependency locking, snapshot manifest, independence checks, and launch instructions. Prove existing ranking and cached-route parity from the new location.
2. **Build the core interface.** API-key modal, upload/review shell, manual controls, applicant summary, complete scrollable rankings, and estate detail selection.
3. **Add route viewing and exports.** Destination lookup, cached geometry, local background context, PNG/WebP standard/HD exports, and interactive SVG controls.
4. **Connect DeepSeek.** Vision extraction, editable review, field validation, matching to supported IDs/categories, and overview grounded in the final computed rankings.
5. **Add Start → End routing.** Map/coordinate selection, mode controls, background jobs, caching, and the same route viewer/export options.
6. **Rehearse and verify.** Full local workflow with synthetic typed/scanned forms, visual checks, failure handling, and a clean startup without the original folder tree.

## Acceptance checks

- Packaged rankings match the current snapshot in both modes/scenarios, category filtering, a selected hospital, custom weights, ties, and incomplete handling. Default ranking requests perform no new Dijkstra searches.
- Cached route geometry and summed costs agree with the engine; hospital-origin amendments remain intact. Map exports all represent the same route.
- Typed and scanned synthetic forms produce the expected fields; blanks, ambiguous checkboxes, conflicting choices, and unreadable writing lead to review rather than guessed values.
- API key errors, timeout, invalid structured output, and overview failures leave manual input/rankings usable. Session data and keys do not enter logs or shared caches.
- SVG zoom/pan/reset, PNG/WebP downloads, and standard/HD sizes work. Switching image formats does not rerun routing.
- Start/end routing covers valid directed routes, wheelchair restrictions, unattached/unreachable endpoints, identical points, and coordinate order. Cost sums match the search result.
- Run the existing applicable regression suite and focused new integration tests for extraction validation, API boundaries, routing jobs, and bundle independence. Verify the real DeepSeek integration with a key during implementation; no key is needed for this planning step.

## Open decisions for discussion

Questions already sent in the conversation; proposed defaults if left open:

1. Apply wheelchair mode when any household member needs it, with an editable confirmation. Code 1 explicitly indicates wheelchair dependence; other disability codes must not automatically imply an unsupported routing profile.
2. Use an offline route diagram with local geographic context, or add an online street-map background.
3. English interface/overview first, or English plus Traditional Chinese. Original estate and destination names can retain the available Chinese names in either version.

The requested “HD / Not HD” behavior is interpreted as static export resolution; SVG stays vector at every zoom. The plan does not add a new routing/scoring model or automatic PRH eligibility checks.

## External documentation checked

- [DeepSeek Vision](https://api-docs.deepseek.com/guides/vision/): image input, supported formats, and current vision-model interface.
- [DeepSeek Responses API guide](https://api-docs.deepseek.com/guides/responses_api/): image input is supported; file inputs are not supported in its documented input items.
- [DeepSeek JSON Output](https://api-docs.deepseek.com/guides/json_mode): structured JSON response workflow; application-side validation still required.
- [FastAPI templates and static files](https://fastapi.tiangolo.com/advanced/templates/): serving a Python-backed HTML interface.

Model/API capabilities will be checked again when implementation begins; this exploration did not make a paid DeepSeek request.
