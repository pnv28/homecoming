# Chat Export: Hong Kong Public Housing Estate Ranking Algorithm

> **Scope note:** This Markdown export reconstructs the conversation available in the current chat context. It includes the user's questions and the assistant's substantive answers, plus relevant project context carried forward in the conversation summary. It may not reproduce every original message verbatim where the earlier messages were available only as summarized context.

---

## Project context

The project concerns a ranking algorithm for Hong Kong public housing estates. The goal is to rank estates by walking access through the pedestrian network to hospitals and public transport.

### Data mentioned

- Hospital locations: `facility-hosp.json`
- Public rental housing estates: `prh-estates (1).json`
- MTR station and line data in CSV files
- Accessibility-related CSV files
- MTR exit coordinates from official iGeoCom CSV/GeoJSON data
- Terrain digital terrain model (DTM) raster
- Pedestrian network File Geodatabase: `3D_Pedestrian_Network_FGDB.zip`
- Bus stops in GeoJSON-like `.json` data

### Intended algorithm

A user selects one of four Hong Kong Housing Authority districts and may optionally select a hospital. The algorithm ranks estates by walking access to a preferred hospital or to any public hospital, and to MTR and/or bus stops. The walking network should account for paths, ramps, and lifts, and exclude stairs where barrier-free access is required.

The pedestrian network contains polylines with two or more vertices. The spatial datasets need to be harmonized before building the graph.

---

## 1. Loading the pedestrian network

### What should `load_network(gdb_path)` do?

The function should read the relevant layer or layers from the File Geodatabase and return the loaded data.

- If the geodatabase has one relevant path layer, it can return one GeoDataFrame.
- If it has multiple relevant layers, such as paths and nodes, it can return a dictionary of GeoDataFrames.
- Inspect the actual geodatabase layer names first. Do not assume a node layer exists.
- Loading is separate from building the graph. The loader reads the data; a later step converts network features into graph nodes and edges.

A GeoDataFrame is a table that includes geographic geometry, such as points, lines, or polygons. GeoPandas is a Python library for reading and working with this kind of data.

A typical pattern is:

```python
import geopandas as gpd

network = gpd.read_file(
    gdb_path,
    layer="actual_layer_name"
)
```

A File Geodatabase commonly appears as a `.gdb` directory. If the data arrives in a ZIP archive, extract it first.

---

## 2. Coordinate reference systems and harmonization

### What does `always_xy=True` mean?

When using `pyproj.Transformer.from_crs`, `always_xy=True` enforces the conventional x-y order:

- Geographic coordinates: longitude, latitude.
- Projected coordinates: easting, northing.

For example:

```python
from pyproj import Transformer

transformer = Transformer.from_crs(
    "EPSG:4326",
    "EPSG:2326",
    always_xy=True
)

easting, northing = transformer.transform(
    114.17,
    22.32
)
```

EPSG:2326 is Hong Kong 1980 Grid System. Its official axis order can differ from the common x-y order, so `always_xy=True` can prevent coordinate-order confusion when using PyProj directly.

GeoPandas' `.to_crs()` generally handles coordinate transformations without requiring you to set `always_xy=True` yourself.

### What does harmonization return?

Harmonization means making the spatial datasets consistent enough to work together. It may include:

- Reprojecting data into a common CRS, such as EPSG:2326.
- Standardizing field names and data types.
- Handling missing or duplicate records.
- Checking for points outside the study area.
- Joining related MTR tables.
- Validating geometry and coordinates.

The result is usually several GeoDataFrames, not one merged table. For example:

- Pedestrian network paths
- Housing estates
- Hospitals
- MTR exits
- Bus stops

Harmonization does not automatically create the graph or the final distance table. It also does not mean that a raster's resolution has been changed.

---

## 3. Snapping facilities and estates to the network

### Do the points and network need to be in the same file?

No. They can be stored in separate GeoDataFrames or files. They do need to use the same CRS, with compatible coordinate units, so that nearest-point calculations make sense.

A function such as:

```python
snap_points(points_gdf, edges_gdf)
```

can accept one GeoDataFrame of points and another of network edges.

### What does snapping mean?

Snapping means finding a suitable nearby point on the pedestrian network for a hospital, estate, MTR exit, or bus stop, then connecting that location to the graph.

A common method is to:

1. Find the nearest suitable walkable edge.
2. Find the nearest position along that edge.
3. Record the offset or split the edge and add a virtual graph node.
4. Connect the facility or estate to that node.

Keep the original facility coordinates. Also set a maximum snapping distance and check that the connector is plausible. A straight-line connector should not cross a wall, road barrier, or other inaccessible feature.

The target network should exclude unsuitable edges, such as stairs when the algorithm is intended to model barrier-free walking. MTR exits should also be filtered for accessibility where required.

---

## 4. Building the graph and assigning edge costs

The pedestrian network is converted into a graph:

- **Nodes** represent junctions, endpoints, or other connection points.
- **Edges** represent walkable segments between nodes.
- **Edge costs** represent the cost of travelling along each segment.

Edge costs could represent physical length, walking time, or a generalized walking cost that accounts for gradient. If uphill and downhill travel have different costs, use a directed graph so the cost can differ by direction.

This is different from the later scoring weights:

- **Graph edge costs** determine how expensive it is to travel along the network.
- **Criteria weights** determine how important hospital, MTR, and bus access are in the final estate ranking.

---

## 5. Multi-source Dijkstra

### What does multi-source Dijkstra return?

Multi-source Dijkstra starts from several source nodes at once and calculates the lowest cost from the source set to every reachable node in the graph.

If the sources are all hospitals, the result gives every reachable node's cost to the nearest hospital in that group. The result includes costs for graph nodes that are not estates, such as junctions, MTR exits, and bus stops. For the estate ranking, look up only the estate nodes.

A single multi-source run with all hospitals does **not** give a separate distance to each hospital. It gives the minimum cost to any hospital in the source set.

### Why does `min(d_mtr, d_bus)` cause a problem?

If you calculate the minimum of the distance to the nearest MTR exit and the distance to the nearest bus stop, the result means “distance to whichever mode is closer.”

Bus stops are often more densely distributed than MTR stations. The bus distance may therefore dominate, hiding differences in MTR access.

If both modes matter, score MTR and bus access separately and combine their scores later.

---

## 6. Calculating the distance from every hospital to every estate

### Approach

Run Dijkstra separately for each hospital. Each run returns the lowest cost from that hospital to every reachable graph node. Extract the costs at the estate nodes and combine them into a table.

For example, with three hospitals, run three calculations. With ten hospitals, run ten calculations.

### Example result

The following values are illustrative only. They are not measured results from the actual datasets.

| Estate | Hospital A | Hospital B | Hospital C |
|---|---:|---:|---:|
| Estate 1 | 850 m | 1,200 m | 600 m |
| Estate 2 | 1,400 m | 500 m | 900 m |
| Estate 3 | 300 m | 1,700 m | 1,100 m |
| Estate 4 | 950 m | 800 m | 1,500 m |

Each cell represents the shortest walking-network distance from an estate to a particular hospital, assuming the graph's edge weights represent distance in metres.

### Python implementation

This version runs Dijkstra once per hospital, then extracts costs for all estates.

```python
import networkx as nx
import pandas as pd

reversed_graph = G.reverse(copy=False)
hospital_costs = {}

# Run Dijkstra once per hospital.
for hospital_id, hospital_node in hospital_nodes.items():
    hospital_costs[hospital_id] = (
        nx.single_source_dijkstra_path_length(
            reversed_graph,
            hospital_node,
            weight="cost"
        )
    )

# Build a table with one row per estate.
rows = []

for estate_id, estate_node in estate_nodes.items():
    row = {"estate_id": estate_id}

    for hospital_id, costs in hospital_costs.items():
        row[hospital_id] = costs.get(
            estate_node,
            float("inf")
        )

    rows.append(row)

distance_table = pd.DataFrame(rows)
```

To export the result as a CSV file:

```python
distance_table.to_csv(
    "estate_hospital_distances.csv",
    index=False
)
```

### Why reverse the graph?

If the graph is directed, the cost from node A to node B may differ from the cost from node B to node A. This can happen when edge costs account for slope or walking direction.

Reversing the graph and running Dijkstra from the hospital calculates the cost of travelling from each estate to that hospital in the original graph.

If the graph is undirected, or all edge costs are symmetric, reversing it is unnecessary.

### Unreachable estates

The code uses `float("inf")` when an estate cannot be reached in the graph. This means no route was found. It should not be treated as an extremely long but valid route. Keep it distinct and flag it in the final ranking.

### Individual hospital distance versus nearest-hospital distance

- **Individual hospital distances:** Run one calculation per hospital. The table has one column per hospital.
- **Nearest-hospital distance:** Run multi-source Dijkstra with all hospitals as sources. The result gives only the minimum cost to any hospital.

Keeping the individual-hospital table supports both use cases. A user can select a specific hospital, or the algorithm can compare access to the nearest hospital.

### Important note about units

The result is a physical distance in metres only if edge weights represent lengths in metres. If edge weights represent walking time or another generalized cost, the table contains that cost instead. Label the columns and units accordingly.

---

## 7. Normalizing access scores

Normalization turns different measurements into comparable scores. It does not mean converting geographic coordinates into another CRS.

For example, you might convert distance into an access score from 0 to 100, where a higher score means better access.

### Capped distance-decay scoring

A capped distance-decay score uses policy thresholds. For example, for bus access:

- At or within 300 metres: score 100.
- Between 300 and 1,500 metres: score decreases linearly.
- At or beyond 1,500 metres: score 0.

These thresholds are examples, not established policy values. They should be selected and documented for the project.

This approach is relatively easy to explain because the score has an absolute meaning tied to walking distance.

### Other options

- **Min-max scaling:** Scales observed values relative to the minimum and maximum. It can be sensitive to outliers.
- **Percentile scoring:** Scores estates relative to other estates. An estate can rank well even if access is poor in absolute terms.

Capped distance decay is a reasonable starting point when the score should reflect meaningful real-world walking distances.

---

## 8. Combining hospital, MTR, and bus access

First calculate a separate access score for each criterion. Then combine the scores.

### Weighted sum

A weighted sum multiplies each criterion's score by its importance weight and adds the results.

For example:

- Hospital access weight: 0.5
- MTR access weight: 0.3
- Bus access weight: 0.2

Suppose an estate has:

- Hospital score: 80
- MTR score: 90
- Bus score: 40

Its total score is:

`(80 × 0.5) + (90 × 0.3) + (40 × 0.2) = 75`

The weights should be visible and configurable. They represent policy priorities, not values automatically discovered by the algorithm. The weights normally sum to 1.

A weighted sum allows strong performance on one criterion to compensate for weaker performance on another. If a criterion must meet a strict minimum, implement that as a separate rule.

### Alternatives

- **Pareto ranking:** Identifies estates that are not worse than another estate on every criterion. It may produce groups rather than one complete ordered list.
- **Lexicographic ordering:** Ranks by a strict priority order. A lower-priority criterion cannot compensate for a worse result on a higher-priority criterion.

---

## 9. Suggested end-to-end workflow

1. Load the source datasets.
2. Inspect the File Geodatabase's actual layer names.
3. Harmonize the spatial data and coordinate reference systems.
4. Filter the pedestrian network to suitable walkable edges.
5. Build the graph and assign edge costs.
6. Snap estates, hospitals, MTR exits, and bus stops to suitable graph locations.
7. Run Dijkstra separately for each hospital if individual hospital distances are required.
8. Run separate calculations for accessible MTR exits, bus stops, and all hospitals if nearest-target distances are needed.
9. Extract the costs for estate nodes.
10. Convert the relevant distances into access scores.
11. Combine criteria using documented weights or another ranking rule.
12. Filter estates by the selected Housing Authority district.
13. Rank estates and clearly flag unreachable destinations.

## Summary

For a table of distances from every hospital to every estate, run one Dijkstra calculation per hospital and extract the costs at the estate nodes. Use multi-source Dijkstra when you only need the cost to the nearest facility in a group. Keep individual hospital distances if users may select a particular hospital.
