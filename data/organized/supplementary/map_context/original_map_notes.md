# Terrain and individual path feature maps

Terrain: [hong_kong_dtm_districts.svg](hong_kong_dtm_districts.svg), with a PNG preview.
The SVG embeds the shaded elevation image and retains vector district outlines, labels,
scale, and coastline. It is standalone; no external image files are needed.

The source ASCII has 12,751 columns, 9,601 rows, 5 m cells, lower-left corner
(799997.5, 799997.5), and declared NoData -9999. All source rows are read and checked.
Observed values range from -26 to 958 m; no cells contain NoData. Rows are north to south.
The display averages 4 × 4 cells into 20 m cells, aligned to the source's northern and
western edges. An outer strip of 5 m south / 15 m east is trimmed for whole averaging
blocks, outside Hong Kong land. The colour scale spans 0–1000 m; negative elevations
use its lowest colour. Shaded relief uses a northwest light at 45° altitude, with no
vertical exaggeration. A coastline clip removes sea areas, which otherwise contain
many zero-valued cells; coastline vintage may differ from the 2019-dated source ZIP entry.
The source ASCII carries no CRS definition; Hong Kong 1980 Grid (EPSG:2326) is used,
consistent with this Lands Department product and the coordinate bounds.

The Lands Department describes this DTM as including some non-ground information,
such as elevated roads and bridges: https://data.gov.hk/en-data/dataset/hk-landsd-openmap-5m-grid-dtm

Individual maps, each with a PNG preview:

- [Escalators](feature_series/hong_kong_paths_precise_escalators.svg)
- [Elevators / lifts](feature_series/hong_kong_paths_precise_elevators.svg)
- [Ramps](feature_series/hong_kong_paths_precise_ramps.svg)
- [Travelators](feature_series/hong_kong_paths_precise_travelators.svg)
- [Stairlifts](feature_series/hong_kong_paths_precise_stairlifts.svg)
- [Slopes](feature_series/hong_kong_paths_precise_slopes.svg)

Every feature SVG includes the complete unsimplified path background: 465,892 routes,
1,963,912 XY vertices, matching hong_kong_paths_precise.svg. The background is muted grey,
with only the selected feature category highlighted. There is no separate staircase map.
All feature maps use the same projection, canvas, map extent, and original path coordinates.
Elevations are flattened. Coloured point markers are exact XY polyline midpoints; they
are exaggerated for visibility and do not represent connector footprints.
Slopes are routes with absolute Gradient >= 5 degrees, excluding all explicit connector
types (including staircases). This is a display cutoff, not a source feature class.
FeatureType codes: escalators 8/16; lifts 10/18; ramps 11/19; travelators 9/17; stairlifts 13/21.

Background path SVG group: pedestrian-path-overlay. Highlight and location-marker groups
are separately named pedestrian-<category> and pedestrian-<category>-location-markers.
The terrain image is named dtm-elevation-raster. JSON summaries record counts and grid metadata.

District source: https://www.had.gov.hk/psi/hong-kong-administrative-boundaries/hksar_18_district_boundary.json
Coastline: https://github.com/bmkor/hk_osm_map/blob/master/Hong_Kong.geojson
Coastline attribution: © OpenStreetMap contributors, https://www.openstreetmap.org/copyright

Reproduce: `.venv/bin/python analysis/maps/render_terrain_and_series.py`
Append `terrain` or `series` to render only that part. Existing maps are preserved.
