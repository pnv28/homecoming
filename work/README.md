# Step 1: prepare the estate-ranking data

This Python pipeline reads the selected local sources, aligns horizontal locations to Hong Kong 1980 Grid (EPSG:2326), prepares stable identities, adds estate allocation categories, reconciles MTR references, and validates/export the result. It follows both documents in [instructions/step_1](instructions/step_1/).

**All routes are assumed always open.** `AccessTime` and `AccessTimeDetails` are not loaded, checked, or exported. Any original `AccessTimeID` is retained only as an unused source attribute. The pipeline builds no graph, computes no walking distances, and makes no access-policy decisions about stairs or assisted equipment.

From the repository root:

```sh
cd work
PYTHONPATH=src ../.venv/bin/python -m estate_ranking.step_1 --config config/step_1.json
```

The command uses the installed `.venv` packages and needs no installation or network access. Configuration paths are relative to the `work_root` declared in the configuration (resolved from the configuration file), not the current shell directory.

The selected supplementary inputs are copied to `data/reference/` and verified against their original checksums. If a reference copy and its selected origin later differ, the run stops so the intended snapshot can be selected explicitly. Source publication/download dates are kept separate from file modification dates; missing source dates remain unknown.

The finished result is available under `precomputed/step_1/`:

- `harmonised.gpkg`: six spatial layers, including all original network vertices/heights.
- `reference_tables.sqlite`: five non-schedule network tables, MTR relationships, estate crosswalk, and lossless raw bus route-stop records.
- `schema.json`: field types, missing-value rules, CRS, original source schemas and coded domains.
- `source_manifest.json`: selected inputs, hashes, provenance, assumptions and software versions.
- `validation_report.md` and `.json`: checks and remaining issues.
- `mtr_match_review.csv`: station/exit cases needing further review.
- `rejected_records.jsonl`: blocking-record diagnostics (empty for successful runs).
- `entity_ids.json`: the successful run's persistent identity/alias registry snapshot.

Each candidate run is staged under `cache/step_1_staging/`. Only a run that passes validation and full read-back checks moves to `precomputed/step_1_runs/` and becomes current. `precomputed/step_1` is a link to the successful run. `config/entity_ids.json` links to that run's registry, so changing the current-run link publishes both the prepared data and identities together. Failed runs retain diagnostics in cache without changing the previous current result. A local process lock prevents simultaneous runs. Successful precomputed data and reports are not excluded from Git; temporary/cache files and the local registry link are ignored.

The registry supports explicit name aliases through `IdentityRegistry.alias(namespace, new_name, original_name)`. Renames must be recorded deliberately; row order never determines estate/hospital IDs. A fresh Git checkout without the local registry link restores IDs and aliases from the versioned current output snapshot. To change a committed registry, stage the edits in a new candidate snapshot and publish it with a successful run. Do not replace the managed registry link with an unrelated file.

MTR override CSVs are initially empty. For station overrides, use `dataset` = `mtr_exits` or `railway_stations`, the bare iGeoCom `GEONAMEID` in `source_id`, a valid MTR CSV `station_id`, and a reason. Exit overrides use bare `access_id`, `station_id`, an explicit `exit_code` (for example `A1`), and a reason. IDs remain strings. Unknown/ambiguous matches and blank access categories are retained rather than guessed. Facility evidence linked to one named exit never propagates to every entrance at a station.

WGS84 is an explicit, reported assumption for estate, hospital and bus point sources: their supplied provider specifications identify latitude/longitude but do not explicitly name the datum. iGeoCom's dictionary explicitly confirms WGS84 point geometry and HK1980 grid attributes. The original network's HKPD height reference is preserved separately from its horizontal grid. Map points for estates and hospitals remain unverified entrance locations.

The supplied `3DPN_DataDictionary_v2.2.pdf` confirms **Gradient in radians** (PDF page 12) and **SHAPE_Length as horizontal length in metres** (PDF page 14). The pipeline records these definitions and checks every source horizontal length against the preserved XY polyline. Gradient sign convention and within-path aggregation are not explicitly documented. This snapshot has no negative gradient values even though ordered path vertices include both rising and falling paths. Later directional cost calculations must derive uphill/downhill direction from the ordered Z coordinates or adopt a documented policy; the `Direction` field specifies permitted travel, not uphill/downhill sign.

Focused tests, from `work/`:

```sh
PYTHONPATH=src ../.venv/bin/python -m unittest discover -s tests -v
```

Later Python stages can load a prepared layer through:

```python
from estate_ranking.export import read_spatial_dataset

estates = read_spatial_dataset("precomputed/step_1", "estates")
network = read_spatial_dataset("precomputed/step_1", "network")
```

The loader restores declared nullable integer/boolean types and height metadata from the saved schema. Original network timestamps are retained as exact text (including timezone suffixes), avoiding an undocumented timezone conversion.

iGeoCom's original `EASTING` and `NORTHING` attributes are saved as `source_grid_easting` and `source_grid_northing`, with the original field-name mapping documented in layer metadata. This keeps them separate from the transformed `easting` and `northing` fields: GeoPackage/SQLite treats field names as case-insensitive. The complete original property names and values also remain in each point's `raw_json`.

Reference tables retain native geodatabase FIDs as `source_fid` and a separate `record_id`. Source entity IDs in these tables can have multiple versions: this snapshot has two Castle Peak Hospital site-reference records with the same `SiteID` and different source dates/name capitalisation. Both are preserved and flagged; the pipeline does not silently choose one version. The unique source-record identity is separate from the shared entity reference.
