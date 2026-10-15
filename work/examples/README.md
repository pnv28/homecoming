# Walking route between two coordinates

`walking_route.py` finds the fastest route under the saved Tobler walking and lift model, using the successful Step 3 pedestrian graph. It creates a PNG map, a JSON result and a CSV of route movements. Input coordinate order is **latitude, longitude**.

Run from the repository root with the existing local environment:

```sh
.venv/bin/python work/examples/walking_route.py \
  --start 22.280111 114.130386 \
  --end 22.28113 114.12856 \
  --start-label "Lee Shau Kee Hall" \
  --end-label "Kennedy Town Exit A" \
  --output work/precomputed/demos/coordinate_route/route.png
```

To enter the coordinates when prompted:

```sh
.venv/bin/python work/examples/walking_route.py
```

Enter a pair such as `22.280111, 114.130386`; spaces are also accepted. Add `--wheelchair` for the existing wheelchair rules. `--graph-directory` can select another successful Step 3 run. The default image is `work/precomputed/demos/coordinate_route/route.png`; its `.json` and `.csv` files are saved alongside it.

Blue lines show the network route, orange dashed lines show assumed connections from the input points to the network, and grey lines show supplied pedestrian paths. If a point cannot attach within 200 m or no directed route connects the two attachments, the program still creates a map explaining the problem and exits with status 2. Identical start/end coordinates produce a zero-distance result.

Both points use the Step 3 ordinary-path rules, with outdoor preference, indoor fallback, height/tie warnings and direction/cost checks. The program collects both selected positions before subdividing their source pieces, so points on the same path can connect directly. It verifies original source profiles, preserves costs and lift identities, and keeps starts and arrivals as separate one-way terminals. Work happens in memory; saved input runs remain unchanged.

The endpoint heights remain unknown. Connections are assumed flat walks to the selected path level. Estimates include slope-dependent Tobler time and the agreed lift charges, with no traffic-light waits, temporary closures or measured personal walking speed. The JSON includes attachment warnings and source references.

The installed environment already contains the required plotting package. For a separate environment, `requirements.txt` in this directory lists the example dependencies, including Matplotlib 3.9.4.

The earlier [Lee Shau Kee Hall-to-nearest-MTR example](lee_shau_kee_hall_mtr_demo.py) compares all eligible MTR access points; `walking_route.py` instead routes to the destination coordinate you supply.
