"""Deep-ocean mask: k=46…60 (1-based) where the column reaches >2000 m."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from oceanai.paths import DEEP_K0, FILL, N_DEEP, processed_dirs


def load_column_geometry(rst_path) -> dict:
    from netCDF4 import Dataset

    with Dataset(rst_path, "r") as ds:
        ref = np.asarray(ds.variables["refBottomDepth"][:], dtype=np.float64)
        bottom = np.asarray(ds.variables["bottomDepth"][:], dtype=np.float64)
        max_lev = np.asarray(ds.variables["maxLevelCell"][:], dtype=np.int32)
        min_lev = np.asarray(ds.variables["minLevelCell"][:], dtype=np.int32)
        area = np.asarray(ds.variables["areaCell"][:], dtype=np.float64)
        rest_h = np.asarray(ds.variables["restingThickness"][:], dtype=np.float64)
        lat = np.asarray(ds.variables["latCell"][:], dtype=np.float64)
        lon = np.asarray(ds.variables["lonCell"][:], dtype=np.float64)
    return {
        "refBottomDepth": ref,
        "bottomDepth": bottom,
        "maxLevelCell": max_lev,
        "minLevelCell": min_lev,
        "areaCell": area,
        "restingThickness": rest_h,
        "latCell": lat,
        "lonCell": lon,
    }


def deep_level_slice(ref_bottom: np.ndarray) -> slice:
    """Return 0-based slice for refBottomDepth > 2000 m."""
    deep = np.where(ref_bottom > 2000.0)[0]
    if deep.size != N_DEEP or deep[0] != DEEP_K0:
        raise ValueError(
            f"expected {N_DEEP} deep levels starting at k0={DEEP_K0}, got {deep}"
        )
    return slice(int(deep[0]), int(deep[-1]) + 1)


def build_deep_mask(geom: dict) -> dict:
    """Boolean mask (nCells, nDeep) plus 0-based level slice."""
    sl = deep_level_slice(geom["refBottomDepth"])
    n_cells = geom["bottomDepth"].shape[0]
    k = np.arange(sl.start, sl.stop)  # 0-based
    k1 = k + 1  # MPAS maxLevelCell is 1-based
    col_ok = geom["bottomDepth"] > 2000.0
    # (nCells, nDeep)
    level_ok = k1[None, :] <= geom["maxLevelCell"][:, None]
    mask = col_ok[:, None] & level_ok
    rest_h = geom["restingThickness"][:, sl]
    rest_h = np.where(np.isfinite(rest_h) & (np.abs(rest_h) < FILL / 10), rest_h, 0.0)
    return {
        "level_slice": sl,
        "mask": mask.astype(bool),
        "areaCell": geom["areaCell"],
        "restingThickness_deep": rest_h,
        "latCell": geom["latCell"],
        "lonCell": geom["lonCell"],
        "bottomDepth": geom["bottomDepth"],
        "n_cells": n_cells,
        "n_deep": int(mask.shape[1]),
        "n_deep_valid": int(mask.sum()),
        "k0": sl.start,
        "k1": sl.stop,
        "ref_deep": geom["refBottomDepth"][sl],
    }


def save_deep_mask(pack: dict, path: Path | None = None) -> Path:
    out = Path(path) if path is not None else processed_dirs()["root"] / "deep_mask.npz"
    sl = pack["level_slice"]
    np.savez_compressed(
        out,
        mask=np.asarray(pack["mask"], dtype=bool),
        areaCell=np.asarray(pack["areaCell"], dtype=np.float64),
        restingThickness_deep=np.asarray(pack["restingThickness_deep"], dtype=np.float64),
        latCell=np.asarray(pack["latCell"], dtype=np.float64),
        lonCell=np.asarray(pack["lonCell"], dtype=np.float64),
        bottomDepth=np.asarray(pack["bottomDepth"], dtype=np.float64),
        n_cells=np.int32(pack["n_cells"]),
        n_deep=np.int32(pack["n_deep"]),
        n_deep_valid=np.int32(pack["n_deep_valid"]),
        k0=np.int32(pack.get("k0", sl.start)),
        k1=np.int32(pack.get("k1", sl.stop)),
        ref_deep=np.asarray(pack["ref_deep"], dtype=np.float64),
    )
    return out


def load_deep_mask(path: Path | None = None) -> dict:
    src = Path(path) if path is not None else processed_dirs()["root"] / "deep_mask.npz"
    z = np.load(src, allow_pickle=False)
    k0 = int(z["k0"] if "k0" in z.files else z["level_slice_start"])
    k1 = int(z["k1"] if "k1" in z.files else z["level_slice_stop"])
    return {
        "level_slice": slice(k0, k1),
        "mask": z["mask"].astype(bool),
        "areaCell": z["areaCell"],
        "restingThickness_deep": z["restingThickness_deep"],
        "latCell": z["latCell"],
        "lonCell": z["lonCell"],
        "bottomDepth": z["bottomDepth"],
        "n_cells": int(z["n_cells"]),
        "n_deep": int(z["n_deep"]),
        "n_deep_valid": int(z["n_deep_valid"]),
        "k0": k0,
        "k1": k1,
        "ref_deep": z["ref_deep"],
    }
