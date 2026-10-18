# Northern Link overlay, revised

Deliverables:

- `hong_kong_estates_hospitals_northern_link_overlay.svg` and `.png`: full Hong Kong map, northern detail panel and complete estate / hospital name index. PNG: 4920 pixels wide.
- `hong_kong_northern_link_detail.svg` and `.png`: standalone northern detail sheet. PNG: 4920 × 2920 pixels.

The original `hong_kong_estates_hospitals_numbered.svg` remains unchanged. All 288 original numbered locations, original pedestrian path geometry, housing areas and index entries are retained in the full map. The detail sheet draws the same locations with symbols sized for its own scale.

## Sources and drawing method

- [MTR Northern Link SVG](https://mtrnorthernlink.hk/images/pages/about/map_en.svg): network connectivity, station names and line colours; saved as `mtr_northern_link_map_en.svg`.
- [Official Northern Link plan, LegCo brief dated 9 July 2025](https://www.legco.gov.hk/yr2025/english/brief/tlb102002001p002_20250709-e.pdf), Annex A, PDF page 12: geographic route and proposed station reference; saved as `northern_link_official_alignment.pdf`.
- Local official station dataset: `data/organized/core/mtr/official_igeocom/railway_stations.geojson`.

Version 2 redraws the railway as smooth SVG centerlines using the geographic plan. It replaces the previous warped schematic artwork entirely. Station rings have uniform sizes, with separate symbol sizes and text layouts for overview and detail. Labels are checked against numbered markers, station symbols, map edges and other station labels. The detail includes a north arrow and a scale bar.

Nine existing station landmarks register the geographic plan to Hong Kong 1980 Grid. The fitted plan has an RMS residual of approximately 158 metres. Existing stations themselves snap to the official local coordinates. Proposed stations and route curves are digitised from the plan and remain indicative; this is not surveyed track geometry or a station footprint dataset. Intermediate existing railway curves and continuations are generalised.

`northern_link_overlay_registration.json` records the fit, landmarks and label collision report. All map content is self-contained SVG vector geometry and text, with no embedded raster backgrounds or external assets.

## Rebuild

From the project root:

```sh
.venv/bin/python analysis/maps/overlay_northern_link.py
inkscape analysis/maps/hong_kong_estates_hospitals_northern_link_overlay.svg --export-type=png --export-width=4920 --export-filename=analysis/maps/hong_kong_estates_hospitals_northern_link_overlay.png
inkscape analysis/maps/hong_kong_northern_link_detail.svg --export-type=png --export-width=4920 --export-filename=analysis/maps/hong_kong_northern_link_detail.png
```
