# Step 3: connect estates and destinations to the pedestrian graph

## 1. Purpose and agreed rules

Explanation for the team: Step 2 created the pedestrian network. Step 3 gives each estate and destination a connection to that network, so Step 4 can calculate journeys.

A connector represents the assumed short walk between a supplied map point and its selected network position. The original point remains unchanged.

Recorded decisions

- [x] Use one closest suitable connection per point, mode and relevant metric.
- [x] Prefer ordinary outdoor paths; allow ordinary indoor paths as a fallback with a warning.
- [x] Do not automatically attach to bridges, tunnels, stairs, moving equipment or lift interiors. Those paths remain available for subsequent travel where the mode permits them.
- [x] Allow connectors up to 200 m for estates, hospitals and MTR access points, and 50 m for bus stops.
- [x] Count connector distance and assume flat Tobler walking time.
- [x] Choose the nearest suitable path when its level is uncertain, retaining a warning.

Step 3 prepares connections and augmented routing graphs. Estate-to-destination subcosts and final ranking remain later work.

The eventual documentation file will be work/instructions/step_3_plan.md, with explanations, implementation steps and accurate checkboxes. No files are changed during this planning turn.

## 2. Freeze inputs and select candidates

Explanation for the team: connections must use the same source data and rules as the graph. Selecting a different mode can change the nearest usable path or target.

Steps we will take

1. Resolve and freeze the successful audited Step 2 snapshot, currently 20261014T105436Z-8fe534aa, and its referenced Step 1 input. Verify their success records, policy and relevant artifact hashes.
2. Use the existing local .venv and installed GeoPandas, Shapely, NumPy, Pyogrio and SciPy. No additional dependency is planned.
3. Load all 244 estates, 44 hospitals, 611 MTR access points and 9,264 bus stops as GeoDataFrames. Preserve identities, attributes, original coordinates and unknown heights.
4. Apply the existing target rules:
   - General MTR: preserve all 611 records; currently 598 pass equipment selection.
   - Wheelchair MTR: use the accepted 276 mobility access points.
   - Bus: retain the existing service/operator/boarding selection, currently 8,848 general and 4,130 wheelchair candidates.
   - Hospital: preserve all 44 targets. Hospital preference is applied later.
5. Prepare estate connections for both time and distance graphs. Hospital targets need distance connections; MTR and bus targets need time connections.
6. Filter candidate network pieces by mode eligibility and permitted, available travel costs. Disabled paths remain excluded.
7. Prefer eligible outdoor ordinary paths: footways, ramps, crossings, service lanes, traffic islands, run-ins, park walkways, footpaths, village paths and tracks, including relevant legacy equivalents.
8. If none falls within the point’s distance limit, search ordinary indoor paths within that same limit and record indoor_fallback. Do not expand the radius automatically.

Original records that are mode-excluded or cannot be attached remain in the output with explicit statuses.

## 3. Choose and record each attachment

Explanation for the team: a supplied point has an X/Y map position but no height. We can identify a position on a selected path and know that path’s height, while keeping the original point’s height unknown.

Steps we will take

1. Use Shapely’s spatial index to find nearby candidate pieces, avoiding comparisons against the entire network for every point.
2. Calculate closest positions on candidate geometry and interpolate their heights from original network XYZ vertices. Do not assign zero height or use the terrain raster.
3. Restrict automatic interior attachments to pieces with a usable horizontal run. Do not use a vertical segment to guess a point’s level.
4. Select the closest candidate in the preferred outdoor tier, or the indoor fallback tier if necessary. Distance limits are inclusive.
5. Resolve exact distance ties by lower attachment height, then stable source identity and source position. Record tied alternatives; the lower-height choice is an external-access assumption.
6. Record alternative-level warnings when a candidate is within 1 m of the selected connector distance but differs by more than 2 m in height, or available floor information establishes a different level in the same building. These are diagnostic defaults; they do not alter Step 2’s junction tolerances.
7. Record indoor fallback, level uncertainty and connectors longer than 50 m for estate/hospital/MTR points. Preserve candidate details for review.
8. If nothing qualifies, record an unattached status and reason. This must not become a zero-cost connection or a silent deletion.
9. Calculate the connector’s horizontal length and flat walking time:

   flat_speed_kmh = 6 × exp(-3.5 × 0.05)
connector_time_seconds = connector_length_metres × 3.6 / flat_speed_kmh
10. Store original point geometry separately from the derived XYZ attachment point. Connector lines remain two-dimensional because the original endpoint height is unknown.
11. Represent zero-distance connections explicitly with zero cost, without creating invalid zero-length line geometry.

The connector is an accepted map-point approximation. Its straight line does not certify a surveyed entrance, unobstructed passage or actual slope.

## 4. Split edges and build terminal connections

Explanation for the team: attaching to the middle of a path requires a new routing position. This must preserve the original travel rules. Estate and destination points must also not become shortcuts between unrelated paths.

Steps we will take

1. Collect attachments across both modes and relevant metrics before splitting, so shared positions are handled consistently.
2. Reuse an existing node where the selected network position matches it under the existing 0.10 m horizontal / 0.025 m height rules.
3. Otherwise split the selected physical edge at its original source position. New point attachments do not create cross-path junctions at middle-to-middle crossings.
4. Preserve source geometry, travel direction, mode eligibility and original lift identity. Preserve every attachment’s parent source and edge references.
5. Recover cost profiles for affected sources from their original geometry and fixed policy. Verify classifications and samples against saved evidence; do not resample split fragments.
6. Recalculate piece costs using only overlapping source intervals, preserving healthy sections beside unavailable intervals. Verify distance and directional cost conservation.
7. Recompile the four mode/metric routing graphs using the existing Step 2 machinery.
8. Add estate terminal states with outgoing connectors only. These represent departures from estates.
9. Add destination terminal states with incoming connectors only. These represent arrival at hospitals, MTR access points or bus stops.
10. Preserve distinct estate, stop and access identities even when their coordinates or attachments coincide.
11. Allow destination arrival from every appropriate lift state at its attachment node. Estate departures enter the network with no current lift identity.
12. Keep terminal states separate from physical XYZ nodes, so unknown facility heights are never fabricated.

These directions prevent travel through an estate or destination point from bridging otherwise separate network paths.

## 5. Interfaces, outputs and acceptance

Implementation interfaces

Provide attach_points(...) and read_attached_graph(..., wheelchair=False, metric="time").

The returned bundle will contain physical node/edge GeoDataFrames, original entity GeoDataFrames, attachment and connector GeoDataFrames, terminal-state mappings and a SciPy routing matrix. Its interface must distinguish physical nodes from estate/destination terminal states.

Publish successful runs under work/precomputed/outputs/step_3/, with separate runs/ and current/ selections. Save policy, input references/hashes, attachment statuses, candidate reviews, sparse matrices, source mappings and validation reports. Reference frozen upstream sources/profiles rather than duplicating bulky unchanged artifacts.

Update the project context and design instructions when implementation occurs. Keep successful outputs trackable in Git; do not commit or push automatically.

Tests

Verify:

- Outdoor preference and flagged indoor fallback.
- Inclusive 200 m/50 m limits and rejection immediately outside them.
- Flat connector distance/time, including exact zero-distance connections.
- Nearest selection, deterministic ties and alternative-level warnings.
- Mode-excluded targets, unavailable time pieces and unattached records.
- Interior splitting, direction preservation and source cost conservation.
- Original sampling and lift identities remaining unchanged.
- Correct costs when entering a split lift and using multiple lift identities.
- Estate departure and destination arrival directions.
- No shortcut through terminal points.
- Distinct coincident identities, GeoDataFrame types, nullable heights and save/reopen preservation.

Full-data acceptance

Account for every input point and report attachment coverage by point type, mode and metric; connector-distance distributions; fallbacks; uncertainties; unattached records; and resulting graph/component counts.

Required integrity checks must pass before selecting a run. Unattached points and accepted approximation warnings remain visible without automatically blocking publication. Failed builds preserve the previous successful Step 3 selection and leave upstream outputs unchanged.