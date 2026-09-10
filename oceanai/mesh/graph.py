"""Cell–cell graph from MPAS `cellsOnCell` (1-based; 0 = missing)."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from oceanai.paths import processed_dirs


def build_cell_graph(rst_path) -> dict:
    from netCDF4 import Dataset

    with Dataset(rst_path, "r") as ds:
        coc = np.asarray(ds.variables["cellsOnCell"][:], dtype=np.int32)
        n_edges_on_cell = np.asarray(ds.variables["nEdgesOnCell"][:], dtype=np.int32)
        area = np.asarray(ds.variables["areaCell"][:], dtype=np.float64)
        lat = np.asarray(ds.variables["latCell"][:], dtype=np.float64)
        lon = np.asarray(ds.variables["lonCell"][:], dtype=np.float64)
        x = np.asarray(ds.variables["xCell"][:], dtype=np.float64)
        y = np.asarray(ds.variables["yCell"][:], dtype=np.float64)
        z = np.asarray(ds.variables["zCell"][:], dtype=np.float64)

    n_cells = coc.shape[0]
    src, dst = [], []
    for i in range(n_cells):
        n_nb = int(n_edges_on_cell[i])
        for e in range(n_nb):
            j1 = int(coc[i, e])
            if j1 <= 0:
                continue
            j = j1 - 1
            if 0 <= j < n_cells and j != i:
                src.append(i)
                dst.append(j)
    edge_index = np.stack([np.asarray(src, dtype=np.int64), np.asarray(dst, dtype=np.int64)])
    deg = np.bincount(edge_index[0], minlength=n_cells)
    return {
        "n_cells": n_cells,
        "edge_index": edge_index,
        "degree": deg,
        "max_degree": int(deg.max()) if deg.size else 0,
        "n_directed_edges": int(edge_index.shape[1]),
        "areaCell": area,
        "latCell": lat,
        "lonCell": lon,
        "xyz": np.stack([x, y, z], axis=1),
    }


def save_cell_graph(pack: dict, path: Path | None = None) -> Path:
    out = Path(path) if path is not None else processed_dirs()["root"] / "mesh_graph.npz"
    np.savez_compressed(
        out,
        n_cells=np.int32(pack["n_cells"]),
        edge_index=np.asarray(pack["edge_index"], dtype=np.int64),
        degree=np.asarray(pack["degree"], dtype=np.int32),
        max_degree=np.int32(pack["max_degree"]),
        n_directed_edges=np.int32(pack["n_directed_edges"]),
        areaCell=np.asarray(pack["areaCell"], dtype=np.float64),
        latCell=np.asarray(pack["latCell"], dtype=np.float64),
        lonCell=np.asarray(pack["lonCell"], dtype=np.float64),
        xyz=np.asarray(pack["xyz"], dtype=np.float64),
    )
    return out


def load_cell_graph(path: Path | None = None) -> dict:
    src = Path(path) if path is not None else processed_dirs()["root"] / "mesh_graph.npz"
    z = np.load(src, allow_pickle=False)
    return {
        "n_cells": int(z["n_cells"]),
        "edge_index": z["edge_index"],
        "degree": z["degree"],
        "max_degree": int(z["max_degree"]),
        "n_directed_edges": int(z["n_directed_edges"]),
        "areaCell": z["areaCell"],
        "latCell": z["latCell"],
        "lonCell": z["lonCell"],
        "xyz": z["xyz"],
    }
