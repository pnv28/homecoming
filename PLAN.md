# homecoming — proposed local web application

Status: implemented and locally verified on 16 October 2026. The source Step 1–5 snapshots remain unchanged. All 7,262 WebP/SVG map sets are prepared and verified. See README.md for launch instructions and docs/verification.json for test evidence. Live DeepSeek verification requires the operator's own API key; provider and review-flow tests use synthetic responses.

## Confirmed scope

- A local hackathon application using the completed Python estate-ranking pipeline.
- Lowercase `homecoming` branding, a large PDF upload area, and an API-key modal on opening.
- Support typed PDFs and scanned/handwritten forms. Use DeepSeek for document reading and for the explanation above the ranking.
- Show an applicant summary, AI Overview explaining the top three, and a scrollable estate list. Clicking an estate reveals its destinations, routes, measurements, and score explanation.
- Static PNG/WebP maps with standard/HD choices; an interactive SVG viewer with zoom and pan.
- Pre-generate WebP (standard and HD) and SVG route assets for all reachable estate/hospital pairs and all available winning bus/MTR access journeys, before the demo. WebP is the default static display format.
- Include precomputed pedestrian-network distance from every estate to every hospital, plus walking time to each estate's winning bus stop and MTR access point. These numeric measurements are already present in the selected Step 4 cache; verify coverage and reuse them. Calculate genuinely missing records during preparation if a future selected snapshot lacks them, while preserving explicit unreachable results.
- DeepSeek only prefills an editable parameter form. The human operator reviews it, optionally selects a preferred hospital, and explicitly presses “Yes, search” before any applicant-specific ranking or AI Overview request.
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

### Numeric precomputation verified in Step 4

The selected `results.json` was inspected directly after the user's clarification:

| Requested measurement | Already saved |
| --- | --- |
| Each estate → every hospital | All 244 × 44 = 10,736 pairs; exactly 44 hospital records for each estate. Distances are in metres. 6,323 pairs have a reachable distance; 4,413 explicitly record unavailability. |
| Each estate → winning bus stop, general mode | 244 records per scenario: 239 reachable walking times in seconds, 5 unavailable. |
| Each estate → winning MTR access point, general mode | 244 records per scenario: 239 reachable walking times in seconds, 5 unavailable. |
| Each estate → winning bus stop, wheelchair mode | 244 records per scenario: 227 reachable walking times in seconds, 17 unavailable. |
| Each estate → winning MTR access point, wheelchair mode | 244 records per scenario: 225 reachable walking times in seconds, 19 unavailable. |

Transport records exist in both primary and baseline scenarios, retaining winning target IDs and ties. The winning destination minimises modelled walking time; it is not necessarily the nearest by straight-line distance. Selecting a preferred hospital looks up the estate's already-saved distance to that hospital. The default hospital is the minimum reachable distance across its 44 records.

No new numeric route calculations are needed for these requests with the current snapshot. Preparing WebP/SVG maps is additional work: saved distances, times, and route links do not mean the route images already exist. An unavailable journey is a completed calculation with no modelled route, not a missing precomputation job.

### Plain-language explanation of project terms

- **Frozen dependencies:** records identifying the exact earlier data versions used to produce a saved result, with file fingerprints to detect changes. For example, Step 4 route links refer to particular Step 3 graph rows, so they must be reopened with that same graph version. Packaging carries the compatible versions together; it does not mean every old run must be copied.
- **Hospital origin overrides:** two reviewed exceptions that change where an estate joins the walking network for hospital-distance calculations. Kwai Luen and Chun Shek originally joined isolated path pockets; their hospital routes now start through reviewed nearby ordinary outdoor nodes. Their short straight connectors count toward distance. These exceptions do not alter their bus/MTR routes or manually set their rank, and do not establish surveyed accessible entrances.
- **Identity registry and selectors:** the earlier phrase “identity selectors” was imprecise. `work/config/entity_ids.json` is a filesystem shortcut to the currently selected ID registry. That registry keeps estate/hospital IDs and recorded name aliases consistent. Separately, `current` links and the rebuild registry choose which successful saved data versions readers open. Neither is an applicant filter.
- **Regression tests:** automated examples that check working behavior stays correct after changes, including previously fixed bugs—for example, charging one lift entry once when its geometry is split into multiple sections.
- **Full-data acceptance checks:** scripts that inspect the actual saved project-wide results, rather than only small artificial examples. They check coverage, costs, rankings, geometry preservation, compatible data versions, and file integrity. The Step 5 checker exercises all 44 hospital selections and confirms ranking uses cached costs without new route searches. These checks establish software/data consistency, not field verification of real-world walking conditions.

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
      ...pre-generated WebP/SVG route assets and route index
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
    precompute_maps.py
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
6. Prefill an editable review form with the extracted values. Always include the hospital dropdown, using the existing 44 stable IDs and “Nearest reachable hospital” as the default. The operator may select a preferred hospital even when it is absent from the PDF. Manual corrections take precedence.
7. Stop in the “Awaiting operator review” state. Extraction completion must never submit the form, click the search button, calculate an applicant-specific ranking, or request the AI Overview. The human operator reviews the parameters and explicitly presses “Yes, search” to submit a validated snapshot of the form.

The form flow is `Upload → Extract → Prefilled form awaiting review → Human presses Yes, search → Results and AI Overview`. Editing parameters after a search creates a new draft; require another explicit submission before replacing results. Keep previous results clearly associated with their last confirmed parameters.

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

After the human explicitly submits the reviewed form, rankings appear as soon as ready; the AI Overview may load afterward. An API failure leaves the list usable and offers a retry. Draft edits do not launch a new search or overview. On the next explicit submission, invalidate the old overview; stale responses cannot overwrite newer confirmed results.

## Map modes and exports

One route geometry feeds all display formats. HD changes raster size, not route selection or cost.

| Display | Proposed behavior |
| --- | --- |
| Static, standard | Pre-generated WebP by default, approximately 1,200 px on the longer side; PNG export available |
| Static, HD | Pre-generated WebP by default, approximately 3,000 px on the longer side; PNG export available |
| Interactive SVG | Vector route and local context, pan, wheel/pinch zoom, zoom buttons, reset-to-fit, endpoint labels, and section tooltips |

SVG is resolution independent rather than a higher-accuracy route. Preserve route vertices; simplify or limit background context only when necessary for browser performance. Clip background geography to the route's area. Do not ship the existing 50 MB whole-Hong-Kong SVG maps into every estate panel.

Use solid lines for network travel and dashed lines for assumed connectors. Add route markers and distinguish lifts/estimated sections where the data supports it. Offer downloadable SVG and static exports. Cache by snapshot, route identity, mode/scenario, format, resolution, and renderer version.

The offline default can reuse local pedestrian paths, coastlines, and nearby estate/facility labels. A street-map background remains an optional decision because it adds an online map dependency and a source/attribution choice. The interactive route itself must remain SVG in either case.

### Required map precomputation

Precompute assets during preparation, rather than rendering these known journeys when an estate is opened:

| Journey set | Coverage |
| --- | --- |
| Estate → hospital | Every reachable pair among 244 estates × 44 hospitals. This supports both the nearest-hospital default and any operator-selected preferred hospital immediately. |
| Estate → bus stop | Every winning target, including ties, for each estate and both general/wheelchair modes; include primary/baseline scenarios exposed by the app. |
| Estate → MTR access point | Every winning access point, including ties, for each estate and both general/wheelchair modes; include primary/baseline scenarios exposed by the app. |

The current hospital cache has 10,736 pair records: 6,323 reachable and 4,413 unavailable. Generate assets for the reachable routes; record unavailable pairs and their reasons in the map index rather than drawing a fictitious path. Hospital geometry is shared across wheelchair/general and transport scenarios, so it needs only one asset set per pair. The nearest-hospital view references these same assets. Bus/MTR winners retain the existing minimum-walking-time semantics.

For each distinct displayed route, produce a standard WebP, an HD WebP, and an SVG. Preserve destination labels, connector/estimate styles, and relevant route metadata consistently. PNG remains an available export and can be generated from the prepared scene on request; it need not duplicate the complete pre-generated WebP library.

Add a resumable `precompute_maps.py` preparation command. Load each frozen graph once, recover geometry from the existing Step 4 cache without new shortest-path searches, render routes with clipped context, and record asset paths, checksums, dimensions, renderer version, and status in an index under `precomputed/maps/`. Publish the index after coverage validation. Reuse byte-identical visual assets where route, labels, and styling match; map every logical request to the appropriate asset explicitly.

The build must cover all hospitals, not merely the currently nearest hospital: a preferred hospital is chosen at runtime. Category and weight changes reuse the same map library. Load only the selected route's requested asset in the browser, and fetch HD/SVG when selected. Measure total build time and disk usage on a sample before the full preparation pass; thousands of images require a resumable build and controlled output sizes.

Arbitrary Start → End journeys remain on-demand and use `runtime/route_cache/` and `runtime/map_cache/`. Keep the complete prepared estate/facility map library separate from those generated runtime caches.

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
- Load ranking measurements first. Serve known estate/facility maps directly from the prepared library, without loading graphs to render them at request time. Lazily load graphs for on-demand routes or detailed section inspection and retain them for reuse. Use a bounded shared executor for heavy route/map tasks and protect non-thread-safe rendering operations.
- Complete the required estate/facility WebP/SVG preparation before the demo. Store these versioned derivative assets under `precomputed/maps/`, separately from original stage snapshots. New arbitrary-coordinate maps/results and optional PNG export caches belong in `runtime/`.
- Keep uploads/extractions in temporary or session-scoped storage; clear them when the session is reset. Persist reusable geographic/map caches without applicant identity or API keys.
- Serve fonts, scripts, and map context locally. Rankings and local routing remain usable without the internet; DeepSeek features require connectivity.
- Include a synthetic demonstration profile so the hackathon walkthrough does not depend on possessing a completed personal form.

## Implementation sequence after discussion

1. **Package the engine and data.** Establish `final/`, dependency locking, snapshot manifest, independence checks, and launch instructions. Prove existing ranking and cached-route parity from the new location.
2. **Build the core interface.** API-key modal, upload/review shell, manual controls with a hospital selector and explicit “Yes, search” submission, applicant summary, complete scrollable rankings, and estate detail selection.
3. **Add route viewing and prepare the map library.** Destination lookup, cached geometry, local background context, resumable standard/HD WebP and SVG precomputation for all required journeys, PNG exports, and interactive SVG controls. Validate full asset coverage before the demo.
4. **Connect DeepSeek.** Vision extraction that only prefills the form, editable review, field validation, matching to supported IDs/categories, and overview grounded in rankings generated only after operator submission.
5. **Add Start → End routing.** Map/coordinate selection, mode controls, background jobs, caching, and the same route viewer/export options.
6. **Rehearse and verify.** Full local workflow with synthetic typed/scanned forms, visual checks, failure handling, and a clean startup without the original folder tree.

## Acceptance checks

- Packaged rankings match the current snapshot in both modes/scenarios, category filtering, a selected hospital, custom weights, ties, and incomplete handling. Default ranking requests perform no new Dijkstra searches.
- Cached route geometry and summed costs agree with the engine; hospital-origin amendments remain intact. Map exports all represent the same route.
- The prepared map index covers every reachable estate/hospital pair and every winning bus/MTR target for the supported modes/scenarios, including ties. Unavailable routes retain explicit statuses. All indexed WebP/SVG assets exist, pass checksum/format checks, and display without runtime rendering. Any preferred-hospital selection resolves to a prepared asset or an explicit unavailable result.
- Typed and scanned synthetic forms produce the expected fields; blanks, ambiguous checkboxes, conflicting choices, and unreadable writing lead to review rather than guessed values.
- Completing extraction and editing any parameter cause zero applicant-specific search or AI Overview calls. The hospital selector remains editable. Only explicit operator submission launches the ranking/overview flow, using the reviewed values rather than stale extraction output.
- API key errors, timeout, invalid structured output, and overview failures leave manual input/rankings usable. Session data and keys do not enter logs or shared caches.
- SVG zoom/pan/reset, PNG/WebP downloads, and standard/HD sizes work. Switching image formats does not rerun routing.
- Start/end routing covers valid directed routes, wheelchair restrictions, unattached/unreachable endpoints, identical points, and coordinate order. Cost sums match the search result.
- Run the existing applicable regression suite and focused new integration tests for extraction validation, API boundaries, routing jobs, and bundle independence. Verify the real DeepSeek integration with a key during implementation; no key is needed for this planning step.

## Confirmed implementation choices

The user closed the open-ended discussion and authorised implementation. Their inline answers below are preserved; the implementation uses household-wide wheelchair review, offline maps, and English.

1. Apply wheelchair mode when any household member needs it, with an editable confirmation. Code 1 explicitly indicates wheelchair dependence; other disability codes must not automatically imply an unsupported routing profile. -- answer yes
2. Use an offline route diagram with local geographic context, or add an online street-map background. --- offline route
3. English interface/overview first, or English plus Traditional Chinese. Original estate and destination names can retain the available Chinese names in either version. -- english app.

The requested “HD / Not HD” behavior is interpreted as static export resolution; SVG stays vector at every zoom. The plan does not add a new routing/scoring model or automatic PRH eligibility checks.

## External documentation checked

- [DeepSeek Vision](https://api-docs.deepseek.com/guides/vision/): image input, supported formats, and current vision-model interface.
- [DeepSeek Responses API guide](https://api-docs.deepseek.com/guides/responses_api/): image input is supported; file inputs are not supported in its documented input items.
- [DeepSeek JSON Output](https://api-docs.deepseek.com/guides/json_mode): structured JSON response workflow; application-side validation still required.
- [FastAPI templates and static files](https://fastapi.tiangolo.com/advanced/templates/): serving a Python-backed HTML interface.

Model/API capabilities will be checked again when implementation begins; this exploration did not make a paid DeepSeek request.
