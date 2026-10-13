# Bus stop list

`bus_stops.csv` contains one row per distinct stop ID from `JSON_BUS.json.1` and `JSON_GMB.json`, downloaded by the user on 13 October 2026. Original files are unchanged.

- `bus_stop` and `bus_stop_zh`: English and Chinese names from the first source record for that ID. Naming variants may occur across routes.
- `latitude`, `longitude`: original stop coordinates.
- `GMB`, `KMB`, `CTB`: lowercase `true` if any route-stop record for the ID includes that operator/service category; otherwise `false` in these supplied snapshots. Joint operation codes are split, so `KMB+CTB` contributes to both flags.
- `operators`: all service codes found, including operators outside the three requested flags. Stops served only by other operators remain in the list with all three flags false. LWB is retained as LWB, not reclassified as KMB. GMB is a green-minibus service category covering multiple operators, not one corporation.

Repeated route records are deduplicated by stop ID. Different IDs are kept separate even when names or coordinates match: colocated or nearby records do not establish the same boarding point. There are no overlapping IDs between the two source files. This list contains no route rows and does not establish wheelchair boarding access, current service availability, or pickup permission for every service.

Reproduce with `python3 analysis/create_bus_stop_list.py` from the project directory.
