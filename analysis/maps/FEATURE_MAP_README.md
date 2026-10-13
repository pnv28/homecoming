# Precise pedestrian feature map

Output: hong_kong_paths_precise_features.svg (plus a PNG preview).
FeatureType codes come from the FGDB's dPedFeatureType coded domain:
lift 10/18, ramp 11/19, staircase 12/20, escalator 8/16, travelator 9/17,
stairlift 13/21. Both regular and M_ variants are included where present.
Explicit feature types take priority. Remaining routes with |Gradient| >= 5 degrees
are highlighted as slopes; this is a chosen display cutoff, not a source feature class
or an accessibility assessment. Gradient is stored in radians, converted for this cutoff.
All other routes remain visible in grey, including mild nonzero slopes.
Lift and stairlift markers are placed at the original XY polyline midpoint, without jitter.
Markers and line strokes are exaggerated for visibility; underlying geometry is unchanged.
Each feature category is a separate named SVG group (pedestrian-<category>).
Category masks are checked to cover each route exactly once; vertex totals are checked.
All 465,892 routes and 1,963,912 vertices are retained. Z is flattened.
Reproduce: .venv/bin/python analysis/maps/render_feature_map.py

Original base-map methodology:

Four deliverables: `hong_kong_paths_overview.{svg,png}` and `hong_kong_paths_precise.{svg,png}`.
Each includes the district map and path overlay. SVG groups marked `pedestrian-path-overlay`
contain the network as vector geometry; SVG text remains text.

All 465,892 source routes are included in both versions. Overview simplifies route bends
with 35 m Douglas–Peucker tolerance and uses thicker lines. Precise retains every original
XY vertex. Elevation is flattened; overlapping paths at different heights appear together.
Districts are projected from WGS84 into the routes' native EPSG:2326 grid. No path snapping,
warping, or clipping to district boundaries is performed. Alignment is limited by the input
datasets' accuracy and vintage; this is not a surveyed accuracy guarantee. District outlines
are administrative polygons and include marine areas. Land fills use a separate historical
OpenStreetMap-derived coastline; reclamation may differ from the newer path data. Coastline
geometry affects only the background, never path coordinates.

Boundary source: https://www.had.gov.hk/psi/hong-kong-administrative-boundaries/hksar_18_district_boundary.json
Catalogue: https://data.gov.hk/en-data/dataset/hk-had-json1-hong-kong-administrative-boundaries
Downloaded 2026-10-12. The downloaded JSON is preserved alongside the outputs.
Land source: https://github.com/bmkor/hk_osm_map/blob/master/Hong_Kong.geojson
Land attribution: OpenStreetMap contributors (https://www.openstreetmap.org/copyright).

Reproduce from repository root: `.venv/bin/python analysis/maps/render_maps.py`
Packages: numpy, pyogrio, shapely, pyproj, matplotlib, pillow.
