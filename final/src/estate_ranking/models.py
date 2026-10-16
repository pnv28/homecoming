"""Columnar tables with explicit types and missing-value masks (Python 3.9)."""
from dataclasses import dataclass, field
from typing import Dict, Optional

import numpy as np


def identifier(value):
    """Never turn a nullable integer identifier into '117.0'."""
    if value is None or (isinstance(value, (float, np.floating)) and np.isnan(value)):
        return None
    if isinstance(value, (float, np.floating)):
        if not np.isfinite(value) or value != int(value):
            raise ValueError("Non-integral identifier: {!r}".format(value))
        return str(int(value))
    return str(value)


@dataclass
class Table:
    name: str
    columns: Dict[str, np.ndarray] = field(default_factory=dict)
    types: Dict[str, str] = field(default_factory=dict)
    masks: Dict[str, np.ndarray] = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)

    def __len__(self):
        return len(next(iter(self.columns.values()))) if self.columns else 0

    def add(self, name, values, kind="string", mask=None):
        values = list(values) if not isinstance(values, np.ndarray) else values
        if self.columns and len(values) != len(self):
            raise ValueError("Unequal column lengths: {}.{}".format(self.name, name))
        if mask is None:
            mask = np.array([v is None or (isinstance(v, (float, np.floating)) and
                            np.isnan(v)) for v in values], dtype=bool)
        else:
            mask = np.asarray(mask, dtype=bool)
        if len(mask) != len(values):
            raise ValueError("Unequal null-mask length")
        dtype = {"int32": "int32", "int64": "int64", "int16": "int16",
                 "float64": "float64", "bool": "bool"}.get(kind, object)
        if kind.startswith("int") or kind == "bool":
            clean = [0 if missing else v for v, missing in zip(values, mask)]
            if kind.startswith("int"):
                for v, missing in zip(values, mask):
                    if not missing and (not np.isfinite(v) or v != int(v)):
                        raise ValueError("Non-integral value for {}.{}".format(self.name, name))
        elif kind == "float64":
            clean = [np.nan if missing else v for v, missing in zip(values, mask)]
        else:
            clean = [None if missing else str(v) for v, missing in zip(values, mask)]
        self.columns[name] = np.asarray(clean, dtype=dtype)
        self.types[name] = kind
        self.masks[name] = mask
        return self

    def value(self, name, index):
        if self.masks[name][index]:
            return None
        v = self.columns[name][index]
        return v.item() if isinstance(v, np.generic) else v

    def rows(self):
        for i in range(len(self)):
            yield {name: self.value(name, i) for name in self.columns}

    @classmethod
    def from_rows(cls, name, rows, types=None, metadata=None):
        rows = list(rows)
        types = types or {}
        obj = cls(name, metadata=metadata or {})
        keys = list(dict.fromkeys(list(types) + [k for r in rows for k in r]))
        for k in keys:
            values = [r.get(k) for r in rows]
            present = next((v for v in values if v is not None), None)
            kind = types.get(k)
            if kind is None:
                kind = ("bool" if isinstance(present, bool) else "int64" if
                        isinstance(present, int) else "float64" if
                        isinstance(present, float) else "string")
            obj.add(k, values, kind)
        return obj


@dataclass
class SpatialDataset(Table):
    geometry: Optional[np.ndarray] = None
    crs: str = "EPSG:2326"
    vertical_crs: Optional[str] = None
    geometry_type: str = "Point"

    def check_contract(self):
        if self.geometry is None or len(self.geometry) != len(self):
            raise ValueError("Geometry/attribute length mismatch: " + self.name)
        for k, values in self.columns.items():
            if len(values) != len(self) or len(self.masks[k]) != len(self):
                raise ValueError("Column/mask length mismatch: " + k)
