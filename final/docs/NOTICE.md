# Third-party assets

DejaVu Sans is bundled for offline rendering and interface typography. Its license is in `assets/fonts/LICENSE_DEJAVU` and `src/homecoming/static/LICENSE_DEJAVU`.

Hong Kong land geometry and pedestrian/facility data are retained from this project’s previously selected source snapshots. Original source manifests, dictionaries, attribution, and source provenance are retained in the packaged Step 1 snapshot. The UI uses no online map tiles.

Route maps display the original 3D Pedestrian Network paths from the Hong Kong Lands Department, before routing-graph filtering, and terrain derived from the project's `Whole_HK_DTM_5m.zip` Lands Department DTM. The prepared relief uses a 20 m mean grid with north-west illumination; its source fingerprint, grid bounds, resolution and processing settings are recorded in `assets/maps/terrain_relief.json`. Terrain is for display only. Land boundaries are attributed to OpenStreetMap contributors (https://www.openstreetmap.org/copyright), as in the existing `analysis/maps` renderer.
