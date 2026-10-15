# Lee Shau Kee Hall to the nearest MTR access point

Using the user-supplied hall coordinate **22.280111, 114.130386**, the saved pedestrian graph selects **Kennedy Town Station Exit A** for both shortest walking distance and fastest modelled time.

The general walking route is **319.1 metres** and **263.4 seconds**, approximately **4 minutes 23 seconds**. It follows footways and stairs towards Pokfield Road, then Smithfield and Exit A. It contains no lift use.

| MTR exit | Fastest route distance | Modelled walking time | Shortest walking distance |
|---|---:|---:|---:|
| Kennedy Town A | 319.1 m | 4 min 23 sec | 319.1 m |
| Kennedy Town C | 353.0 m | 4 min 50 sec | 353.0 m |
| Kennedy Town B | 519.3 m | 6 min 42 sec | 519.3 m |
| HKU C2 | 1,077.4 m | 13 min 15 sec | 1,075.8 m |
| HKU C1 | 1,040.1 m | 17 min 04 sec | 1,000.6 m |

Exit B is closest in straight-line distance (209.3 m versus Exit A's 219.4 m). Exit A wins when following the model's permitted pedestrian routes.

## Calculation and assumptions

The example compares all **598 general-mode eligible MTR access records** in Step 3 run `20261014T145819Z-4d15d1a3`. **131** have finite walking routes from this origin; the other eligible records remain in the comparison with infinite costs. No district or station filter selects the winner.

The origin uses the Step 3 attachment rules, including outdoor preference, the 200 m limit, direction/cost eligibility and node-reuse tolerances. Its original height remains unknown. The selected path position has a source HKPD height of 38.718 m; this is not assigned to the hall.

The route includes an assumed **57.7 m / 41.3 second** origin connector and a **4.5 m / 3.2 second** destination connector. The origin is flagged `level_uncertain;long_connector`. These straight flat connectors represent the accepted map-point approximation, not verified entrances or surveyed passages.

Network times use the saved directional Tobler costs, and routes respect permitted travel directions. The shortest-distance comparison uses the same MTR arrival attachment positions, with costs in metres. Origin profile evidence is verified against original Step 2, and the predecessor route's summed costs are checked against the shortest-path result. Published Step 3 artifacts are unchanged.

Times are estimates under the fixed model. Traffic-light waiting, temporary closures and walking-speed variation are not included. Stairs are permitted in this general-mode example.

## Files

- [Route map](route_map.png): blue network route, dashed orange assumed connectors and grey source pedestrian paths.
- [Result](result.json): coordinates, winners, exact costs, input run, assumptions and validation.
- [MTR comparison](mtr_comparison.csv): all 598 eligible records, fastest time, shortest distance and straight-line distance. Fastest-route lengths are additionally populated for the leading 12 time candidates.
- [Fastest route legs](fastest_route_legs.csv) and [shortest route legs](shortest_route_legs.csv): source path IDs, feature types, street names and costs for each movement.
- [Origin candidates](origin_candidates.csv): attachment review evidence for both modes and metrics; the demonstration uses general mode.
- `routes.gpkg`: original 2D origin, derived attachment points with source Z, and 2D route lines for map inspection. Route lines use horizontal EPSG:2326 coordinates.
- [Example script](../../../examples/lee_shau_kee_hall_mtr_demo.py): reproducible calculation using the existing saved graphs, with temporary departure states added in memory.

From the repository root:

```sh
.venv/bin/python work/examples/lee_shau_kee_hall_mtr_demo.py
```
