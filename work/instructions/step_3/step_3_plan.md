# Step 3: connect estates and destinations to the pedestrian graph

## 1. Purpose and agreed decisions

Explanation for the team

Step 2 created the pedestrian network. Step 3 connects estate, hospital, MTR access and bus-stop map points to that network. Step 4 can then calculate journeys.

A connector represents the assumed short walk between a supplied map point and a selected position on a pedestrian path. The original map point remains saved separately.

Agreed decisions

- [X] Use one closest suitable connection per point, mode and relevant cost metric.
- [X] Prefer ordinary outdoor paths. Allow ordinary indoor paths as a fallback, with a warning.
- [X] Do not automatically attach points to bridges, tunnels, stairs, escalators, travelators or lift interiors. These paths remain available for subsequent travel where the mode permits them.
- [X] Allow connectors up to 200 m for estates, hospitals and MTR access points, and 50 m for bus stops.
- [X] Count connector distance and assume flat Tobler walking time.
- [X] Choose the nearest suitable path when its level is uncertain, recording the uncertainty.
- [X] Use mature external packages where they provide the required operations.
- [X] Record the context file’s last update using date and time in HKT.

These checkmarks record agreed decisions and completed implementation verified against the frozen inputs.

Step 3 produces connections and augmented routing graphs. Estate subcosts and final ranking remain later work.

## 2. Freeze inputs, reuse packages and select candidates

Explanation for the team

Connections must use the same source data and rules as the network. Wheelchair selection and the cost metric can change which path is suitable.

We will reuse installed packages for standard geometry, spatial searches, storage and routing. Custom code will apply our project’s selection, height and cost-preservation rules.

Steps we will take

- [X] Freeze the successful Step 2 snapshot, currently 20261014T105436Z-8fe534aa, and its referenced Step 1 snapshot, 20261014T090829Z-20d0139c. Verify success records, policies and relevant artifact hashes.
- [X] Use the local .venv and installed packages:
   - Shapely: indexed nearest-path searches, projection, interpolation and suitable geometry extraction.
   - GeoPandas: spatial input and output tables.
   - Pyogrio: spatial file reading and writing.
   - NumPy/pandas: calculations and associated tables.
   - SciPy: sparse routing matrices, shortest paths and connected components.
- [X] Reuse the existing Step 2 graph and cost machinery. No additional dependency is currently required. If implementation reveals a concrete need, use a suitable mature package under the existing authorisation and record its purpose and version.
- [X] Load all 244 estates, 44 hospitals, 611 MTR access points and 9,264 bus stops as GeoDataFrames. Preserve identities, attributes, original coordinates and unknown heights.
- [X] Apply the existing destination rules:

   | Destination | General mode | Wheelchair mode |
   |---|---|---|
   | MTR | Currently 598 eligible records from the complete 611; exclude 11 stair-lift and two wheelchair-aid records | Accepted 276 mobility access points |
   | Bus | Currently 8,848 stops with qualifying KMB, CTB or GMB pickup service | Currently 4,130 stops with qualifying KMB or CTB pickup service |
   | Hospital | Preserve all 44 | Preserve all 44 |

   Preserve all original records, including mode-excluded records. Hospital preference is applied later. Candidate counts do not establish attachment or reachability.
- [X] Prepare estate connections for time and distance graphs, hospital connections for distance, and MTR/bus connections for time, in both modes.
- [X] Filter network pieces by mode eligibility, permitted direction and available costs. Exclude disabled paths.
- [X] Search eligible ordinary outdoor paths first: footways, ramps, crossings, service lanes, traffic islands, run-ins, park walkways, footpaths, village paths and tracks, including relevant legacy equivalents.
- [X] If no suitable outdoor path lies within the applicable limit, search ordinary indoor paths within that same limit. Record indoor_fallback; do not expand the limit.

## 3. Choose and record attachments

Explanation for the team

The supplied facility points have horizontal coordinates but no height. The selected network position has a height from the original 3D path. We will preserve that distinction.

A straight connector is our accepted map-point approximation. It does not establish a surveyed entrance, actual connector slope or unobstructed passage.

Steps we will take

- [X] Use Shapely’s spatial index to find candidate paths efficiently, with bounded searches and all equally close matches.
- [X] Calculate the closest horizontal position and recover its original source position. Use library projection/interpolation where unambiguous; handle repeated path visits using original segment identity rather than accepting an arbitrary first match.
- [X] Interpolate attachment height from original network XYZ vertices. Keep the facility’s height unknown; do not assign zero height or use terrain data.
- [X] Allow automatic interior attachment only where the selected segment has a usable horizontal run. Do not infer a facility level from a vertical segment.
- [X] Choose the closest suitable outdoor candidate, or the closest suitable indoor fallback. Apply the 200 m/50 m limits inclusively.
- [X] Resolve exact distance ties by lower attachment height, then stable source identity and source position. Record tied alternatives and the lower-height assumption.
- [X] Record an alternative-level warning when another candidate is within 1 m of the selected connector distance but differs by more than 2 m in height, or known floor information establishes different floors within the same building. These diagnostic defaults do not change Step 2’s junction tolerances.
- [X] Record indoor fallback, level uncertainty and estate/hospital/MTR connectors longer than 50 m. Save candidate details for review.
- [X] If nothing qualifies, retain the point with an unattached status and reason.
- [X] Calculate horizontal connector distance and flat Tobler walking time:

    ```text
    flat_speed_kmh = 6 × exp(-3.5 × 0.05)
    connector_time_seconds = connector_length_metres × 3.6 / flat_speed_kmh
    ```

- [X] Store original facility points as 2D points, derived attachment points as Point Z, and positive-length connectors as 2D lines.
- [X] Represent exact zero-distance attachments with zero cost and an explicit mapping, without creating degenerate line geometry.

## 4. Split paths and build terminal connections

Explanation for the team

An attachment in the middle of a path requires a new routing position. Splitting must preserve the original geometry, direction and costs.

Facility points also need defined roles: estates are departure points; hospitals, MTR access points and bus stops are arrival points. They must not become shortcuts connecting unrelated paths.

Steps we will take

- [X] Collect attachments across both modes and relevant metrics before splitting. Combine identical positions on the same source path.
- [X] Reuse an existing node associated with the selected path where the position satisfies the existing 0.10 m horizontal and 0.025 m height tolerances.
- [X] Otherwise split the selected physical edge at its original source position. Do not create new cross-path junctions merely because two paths cross near an attachment.
- [X] Preserve original source geometry, direction, eligibility and lift identity. Save each attachment’s parent source and edge references.
- [X] Recover affected source cost profiles from original geometry and the fixed policy. Verify classifications and samples against saved evidence; do not resample fragments.
- [X] Calculate each new piece’s costs from its overlapping original intervals. Preserve healthy sections beside unavailable intervals and verify distance and directional cost conservation.
- [X] Recompile the four general/wheelchair × time/distance routing graphs using Step 2 machinery.
- [X] Add estate terminal states with outgoing connectors only.
- [X] Add destination terminal states with incoming connectors only.
- [X] Preserve separate identities for coincident estates, stops and access records.
- [X] Permit destination arrival from appropriate lift states at the attachment node. Estate departure enters the network with no current lift identity.
- [X] Keep terminal states separate from physical XYZ nodes so facility heights remain unknown.

The existing lift rule remains: 30 seconds when entering an original lift identity, no additional charge for continuing its split pieces, another 30 seconds for a different lift, and zero waiting time.

## 5. Outputs, documentation and acceptance

Explanation for the team

Every input point must be accounted for, whether attached, excluded or unattached. Warnings will describe accepted approximations and incomplete connections without silently removing records.

Steps we will take

- [X] Provide attach_points(...) and read_attached_graph(..., wheelchair=False, metric="time").
- [X] Return physical node/edge, original entity, attachment and connector GeoDataFrames, alongside terminal mappings and a SciPy sparse routing matrix. Clearly distinguish physical nodes from terminal states.
- [X] Publish successful runs under work/precomputed/outputs/step_3/, using runs/ and a current selection.
- [X] Save policy, frozen upstream references, hashes, statuses, candidate reviews, matrices, mappings and validation reports. Reference unchanged upstream source geometry and profiles rather than duplicating them; retain those referenced inputs.
- [X] Update the Step 3 plan, project context and overall design instructions. Keep explanations separate from implementation actions, and mark only completed work [X].
- [X] Set the context header to Last updated: YYYY-MM-DD HH:mm:ss HKT (UTC+08:00) using the actual edit time. Refresh it whenever the context changes.
- [X] Keep successful outputs trackable in Git. Do not automatically commit or push.

Tests and full-data checks

- [X] Outdoor preference and flagged indoor fallback.
- [X] Inclusive distance limits and rejection immediately outside them.
- [X] Flat connector distance/time and zero-distance attachments.
- [X] Deterministic ties, repeated path visits and level warnings.
- [X] Mode-excluded targets, unavailable directions and unattached records.
- [X] Interior splitting, direction preservation and source cost conservation.
- [X] Preserved sampling, lift identities and charges for multiple lifts.
- [X] Correct departure/arrival directions and no shortcuts through terminals.
- [X] Distinct coincident identities, GeoDataFrame types, unknown heights and save/reopen preservation.
- [X] Full accounting of all 10,163 source points, with coverage by type, mode and metric, connector-distance distributions, warnings and resulting graph/component counts.

Required integrity checks must pass before selecting a successful run. Unattached points and accepted approximation warnings remain visible and do not automatically block publication. Failed builds preserve the previous successful selection and leave upstream outputs unchanged.

## Completed implementation

Selected successful run: `20261014T145819Z-4d15d1a3`. The full build accounts for all 10,163 source points and 20,814 mode/metric records. All 112 repository tests pass. Read [the implementation guide](step_3_implementation.md) and [the validation report](../../precomputed/outputs/step_3/current/validation_report.md) for coverage, warnings, component counts and preservation checks. Estate subcosts and ranking remain later work.
