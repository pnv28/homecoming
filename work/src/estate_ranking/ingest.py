"""Explicit sources, safe geodatabase extraction, source schemas and readers."""
from collections import OrderedDict
from datetime import datetime, timezone
import csv
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import shutil
import stat
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from pypdf import PdfReader

import numpy as np
import pyogrio
import pyogrio.raw
import shapely
from pyproj import CRS

from .models import SpatialDataset, Table, identifier
from .validate import require


def read_json(path):
    with Path(path).open(encoding="utf-8-sig") as f:
        return json.load(f)


def read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_config(path):
    path = Path(path).resolve()
    config = read_json(path)
    root = (path.parent / config["work_root"]).resolve()
    config["_root"] = str(root)
    config["_config_path"] = str(path)
    return config


def inventory_sources(config, report):
    root = Path(config["_root"])
    manifest = {"created_utc": datetime.now(timezone.utc).isoformat(),
                "config_sha256": sha256(config["_config_path"]),
                "configuration": {k: v for k, v in config.items() if not k.startswith("_")},
                "python": platform.python_version(),
                "libraries": {k: importlib.metadata.version(k) for k in
                              ["numpy", "pyogrio", "shapely", "pyproj", "pypdf", "geopandas", "pandas"]},
                "gdal": pyogrio.__gdal_version_string__, "sources": {}}
    paths = {}
    for name, spec in config["sources"].items():
        path = root / spec["path"]
        origin = root / spec["copy_from"] if "copy_from" in spec else None
        if origin is not None:
            if not origin.is_file():
                raise FileNotFoundError("Missing reference source: " + str(origin))
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(origin, path)
            elif sha256(path) != sha256(origin):
                raise ValueError("Reference copy differs from origin; select the intended snapshot explicitly: " + str(path))
        if not path.is_file():
            raise FileNotFoundError("Missing selected input: " + str(path))
        paths[name] = path
        entry = dict(spec, sha256=sha256(path), size_bytes=path.stat().st_size,
                     file_modified_utc=datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
                     source_date=None)
        if origin:
            entry["original_absolute_path"] = str(origin.resolve())
        if spec.get("crs_assumption"):
            if spec.get("crs_assumption_accepted"):
                report.checks[name + ":accepted_crs_assumption"] = spec["crs_assumption"]
            else:
                report.warning("crs_assumption", name, spec["crs_assumption"])
        manifest["sources"][name] = entry
    manifest["sources"]["mtr_exits"]["extraction_provenance"] = read_json(paths["mtr_source_manifest"])
    manifest["sources"]["mtr_exits"]["retrieved_utc"] = manifest["sources"]["mtr_exits"]["extraction_provenance"].get("retrieved_utc")
    manifest["sources"]["railway_stations"]["retrieved_utc"] = manifest["sources"]["mtr_exits"]["retrieved_utc"]
    report.checks["inventory"] = {"selected_files": len(paths), "reference_copies_verified":
                                   sum("copy_from" in v for v in config["sources"].values())}
    return paths, manifest


def safe_extract_network(archive, cache, digest):
    """Validate all members before writing; reuse only an unchanged extraction."""
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    destination = cache / ("network_" + digest[:16])
    marker = destination / "extraction_manifest.json"
    if marker.is_file():
        saved = read_json(marker)
        if saved["archive_sha256"] == digest and all(
                (destination / n).is_file() and sha256(destination / n) == h
                for n, h in saved["files"].items()):
            return destination / saved["gdb"], saved
        raise ValueError("Cached extraction changed; preserve it and use a fresh cache directory")
    with zipfile.ZipFile(archive) as z:
        members = z.infolist()
        if len({m.filename for m in members}) != len(members):
            raise ValueError("Duplicate archive paths")
        gdbs = set()
        for member in members:
            name = member.filename
            parts = Path(name).parts
            if (Path(name).is_absolute() or ".." in parts or "\\" in name or
                    stat.S_ISLNK(member.external_attr >> 16)):
                raise ValueError("Unsafe archive member: " + name)
            for i, part in enumerate(parts):
                if part.endswith(".gdb"):
                    gdbs.add(str(Path(*parts[:i + 1])))
        if len(gdbs) != 1:
            raise ValueError("Expected exactly one File Geodatabase")
        if sum(m.file_size for m in members) > 4 * 1024 ** 3:
            raise ValueError("Archive exceeds the configured extraction safety limit")
        # An incomplete directory is never mistaken for a reusable extraction.
        stage = Path(tempfile.mkdtemp(prefix=".extract-", dir=str(cache)))
        z.extractall(stage)
        files = {m.filename: sha256(stage / m.filename) for m in members if not m.is_dir()}
        saved = {"archive_sha256": digest, "gdb": next(iter(gdbs)), "files": files}
        (stage / "extraction_manifest.json").write_text(json.dumps(saved, indent=2) + "\n")
        if destination.exists():
            raise ValueError("Incomplete cache directory already exists: " + str(destination))
        os.replace(stage, destination)
    return destination / saved["gdb"], saved


def extract_domains(gdb):
    domains = {}
    for path in sorted(Path(gdb).glob("*.gdbtable")):
        for block in re.findall(rb"<GPCodedValueDomain2\b.*?</GPCodedValueDomain2>", path.read_bytes(), re.S):
            if len(block) > 1024 * 1024:
                raise ValueError("Oversized domain definition")
            root = ET.fromstring(block)
            name = root.findtext("DomainName")
            domain = {"description": root.findtext("Description"), "source": path.name,
                      "values": {v.findtext("Code"): v.findtext("Name")
                                 for v in root.findall(".//CodedValue")}}
            if name in domains and domains[name]["values"] != domain["values"]:
                raise ValueError("Conflicting domain definitions: " + name)
            domains[name] = domain
    if not domains:
        raise ValueError("No readable coded domains in selected archive")
    return domains


def inspect_network(gdb):
    layers = {}
    for name, geometry_type in pyogrio.list_layers(gdb):
        info = pyogrio.read_info(gdb, layer=name)
        layers[name] = {"fields": info["fields"].tolist(), "dtypes": info["dtypes"].tolist(),
                        "source_count": int(info["features"]), "geometry_type": geometry_type,
                        "crs": info["crs"], "bounds": info["total_bounds"]}
    if "PedestrianRoute" not in layers:
        raise ValueError("PedestrianRoute layer missing")
    crs = CRS(layers["PedestrianRoute"]["crs"])
    horizontal = crs.sub_crs_list[0] if crs.is_compound else crs
    if horizontal.to_epsg() != 2326:
        raise ValueError("Unexpected network horizontal CRS")
    if not crs.is_compound or crs.sub_crs_list[1].to_epsg() != 5738:
        raise ValueError("Expected HKPD vertical CRS for the 3D network")
    return {"layers": layers, "domains": extract_domains(gdb),
            "original_compound_crs_wkt": layers["PedestrianRoute"]["crs"],
            "horizontal_crs": "EPSG:2326", "vertical_crs": "EPSG:5738",
            "domain_extraction": "Bounded GPCodedValueDomain2 blocks from source .gdbtable files"}


def confirm_network_definitions(dictionary_path):
    """Bind confirmed definitions to the selected provider PDF, not a guess."""
    pages = PdfReader(dictionary_path).pages
    checks = [(7, "Hong Kong 1980 Grid"), (11, "The gradient of the segment in radian"),
              (13, "Horizontal length of the feature in meter")]
    for index, phrase in checks:
        text = re.sub(r"\s+", " ", pages[index].extract_text() or "")
        if phrase not in text:
            raise ValueError("Selected 3DPN dictionary no longer matches verified definitions: " + phrase)
    return {
        "gradient": {"unit": "radians", "source": "network_dictionary", "pdf_page": 12,
                     "provider_definition": "The gradient of the segment in radian",
                     "sign_convention": "not explicitly documented", "aggregation_method": "not explicitly documented"},
        "shape_length": {"unit": "metres", "measurement": "horizontal XY polyline length",
                         "source": "network_dictionary", "pdf_page": 14,
                         "provider_field": "SHAPE_Length", "gdb_field": "Shape_Length"},
        "height": {"unit": "metres above Hong Kong Principal Datum", "source": "network_dictionary", "pdf_page": 8}}


def load_network(gdb, inspection):
    datasets, tables = [], []
    for name, description in inspection["layers"].items():
        if name in {"AccessTime", "AccessTimeDetails"}:
            continue
        spatial = description["geometry_type"] is not None
        if spatial and name != "PedestrianRoute":
            raise ValueError("Unexpected spatial layer needs an explicit loader: " + name)
        meta, fids, geometry, columns = pyogrio.raw.read(
            gdb, layer=name, read_geometry=spatial, datetime_as_string=True, return_fids=True)
        cls = SpatialDataset if spatial else Table
        obj = cls("network" if spatial else name, metadata={
            "source": "network", "source_layer": name,
            "source_count": description["source_count"],
            "source_schema": dict(zip(description["fields"], description["dtypes"])),
            "timestamp_policy": "Original GDAL string representation retained, including time-zone suffixes"})
        for field_name, source_type, values in zip(meta["fields"], description["dtypes"], columns):
            kind = "timestamp_text" if source_type.startswith("datetime") else source_type
            if kind not in {"int16", "int32", "int64", "float64", "timestamp_text"}:
                kind = "string"
            obj.add(field_name, values, kind)
        if spatial:
            obj.geometry = shapely.from_wkb(geometry)
            obj.geometry_type = description["geometry_type"]
            obj.vertical_crs = "EPSG:5738"
            require(obj.columns, ["PedestrianRouteID", "Gradient", "Shape_Length", "FeatureType",
                                 "WheelchairBarrier", "WheelchairAccess", "Enabled", "Direction",
                                 "TerminalID", "FloorID", "SiteID",
                                 "BuildingID_1", "BuildingID_2"], "network")
            obj.add("id", ["path:" + identifier(v) for v in obj.columns["PedestrianRouteID"]])
            obj.add("source_id", [identifier(v) for v in obj.columns["PedestrianRouteID"]])
            obj.add("name_en", obj.columns["AliasNameEN"])
            obj.add("name_zh_hant", obj.columns["AliasNameTC"])
            obj.add("name", [en or zh for en, zh in zip(obj.columns["AliasNameEN"], obj.columns["AliasNameTC"])])
            obj.add("entity_type", ["pedestrian_path"] * len(obj))
            obj.add("provenance", ["network:PedestrianRoute:PedestrianRouteID"] * len(obj))
            obj.add("gradient_raw", obj.columns["Gradient"], "float64", obj.masks["Gradient"])
            definitions = inspection.get("field_definitions", {})
            obj.metadata.update(gradient_units=definitions.get("gradient", {}).get("unit", "unresolved"),
                                gradient_direction=definitions.get("gradient", {}).get("sign_convention", "unresolved"),
                                gradient_aggregation=definitions.get("gradient", {}).get("aggregation_method", "unresolved"),
                                shape_length_semantics=definitions.get("shape_length", {}).get("measurement", "unresolved"),
                                field_definition_evidence=definitions,
                                vertical_datum="Hong Kong Principal Datum",
                                access_policy="always_open; AccessTimeID unused; schedule tables excluded")
            datasets.append(obj)
        else:
            # Relationship tables can contain multiple source versions of one
            # entity. Native feature IDs identify source records without
            # collapsing repeated entity references or choosing a version.
            obj.add("source_fid", fids, "int64")
            obj.add("record_id", ["network:{}:{}".format(name, identifier(fid)) for fid in fids])
            obj.metadata["record_identity"] = "Native GDB FID; entity references may have multiple versions"
            tables.append(obj)
    return datasets[0], tables
