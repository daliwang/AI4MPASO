"""Read deep T/S/h from a restart; extract compact pair tensors."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from oceanai.paths import FILL, early_rst, late_rst, processed_dirs


def _read_xtime(ds) -> str:
    raw = np.asarray(ds.variables["xtime"][0])
    if np.ma.isMaskedArray(raw):
        raw = np.ma.filled(raw, b" ")
    if raw.dtype.kind in ("S", "a"):
        s = raw.tobytes().decode("ascii", "replace")
    else:
        s = "".join(
            (c.decode("ascii", "replace") if isinstance(c, (bytes, np.bytes_)) else str(c))
            for c in np.ravel(raw)
        )
    return s.replace("\x00", "").strip()


def _squeeze_time(v: np.ndarray) -> np.ndarray:
    if v.ndim == 3 and v.shape[0] == 1:
        return v[0]
    return v


def read_deep_state(rst_path, mask_pack: dict) -> dict:
    from netCDF4 import Dataset

    sl = mask_pack["level_slice"]
    with Dataset(rst_path, "r") as ds:
        t = _squeeze_time(np.asarray(ds.variables["temperature"][:], dtype=np.float64))
        s = _squeeze_time(np.asarray(ds.variables["salinity"][:], dtype=np.float64))
        h = _squeeze_time(np.asarray(ds.variables["layerThickness"][:], dtype=np.float64))
        xtime = _read_xtime(ds)
    t = t[:, sl]
    s = s[:, sl]
    h = h[:, sl]
    finite = (
        np.isfinite(t)
        & np.isfinite(s)
        & np.isfinite(h)
        & (np.abs(t) < FILL / 10)
        & (np.abs(s) < FILL / 10)
        & (np.abs(h) < FILL / 10)
        & (h > 0)
    )
    valid = mask_pack["mask"] & finite
    t = np.where(valid, t, 0.0)
    s = np.where(valid, s, 0.0)
    h = np.where(valid, h, 0.0)
    return {"temperature": t, "salinity": s, "layerThickness": h, "valid": valid, "xtime": xtime}


def _rst_paths(row: dict) -> tuple[Path, Path]:
    if row.get("path_x") and row.get("path_y"):
        return Path(row["path_x"]), Path(row["path_y"])
    return early_rst(int(row["year_x"]), int(row["month"])), late_rst(
        int(row.get("year_y", int(row["year_x"]) + 550)), int(row["month"])
    )


def extract_pair(row: dict, mask_pack: dict) -> dict:
    px, py = _rst_paths(row)
    x = read_deep_state(px, mask_pack)
    y = read_deep_state(py, mask_pack)
    valid = x["valid"] & y["valid"]
    return {
        "pair_id": row["pair_id"],
        "month": np.int32(row["month"]),
        "year_x": np.int32(row["year_x"]),
        "split": row["split"],
        "xtime_x": x["xtime"],
        "xtime_y": y["xtime"],
        "t_x": x["temperature"],
        "s_x": x["salinity"],
        "h_x": x["layerThickness"],
        "t_y": y["temperature"],
        "s_y": y["salinity"],
        "h_y": y["layerThickness"],
        "valid": valid,
    }


def save_pair(pack: dict, out_dir=None) -> Path:
    dest = Path(out_dir) if out_dir is not None else processed_dirs()["pairs"]
    dest.mkdir(parents=True, exist_ok=True)
    out = dest / f"{pack['pair_id']}.npz"
    np.savez_compressed(
        out,
        month=pack["month"],
        year_x=pack["year_x"],
        t_x=pack["t_x"].astype(np.float32),
        s_x=pack["s_x"].astype(np.float32),
        h_x=pack["h_x"].astype(np.float32),
        t_y=pack["t_y"].astype(np.float32),
        s_y=pack["s_y"].astype(np.float32),
        h_y=pack["h_y"].astype(np.float32),
        valid=pack["valid"],
        xtime_x=np.array(pack["xtime_x"]),
        xtime_y=np.array(pack["xtime_y"]),
        split=np.array(pack["split"]),
    )
    return out


def load_pair(pair_id: str, root=None) -> dict:
    path = processed_dirs(root)["pairs"] / f"{pair_id}.npz"
    z = np.load(path, allow_pickle=False)
    return {k: z[k] for k in z.files}
