"""Copy-template restart writeback: overwrite deep temperature and salinity only."""

from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np
from netCDF4 import Dataset

from oceanai.paths import FILL


def write_deep_ts(
    template_rst: str | Path,
    out_rst: str | Path,
    t_deep: np.ndarray,
    s_deep: np.ndarray,
    mask_pack: dict,
    xtime: str | None = None,
) -> Path:
    """t_deep, s_deep: (nCells, nDeep). Invalid points keep template values."""
    template_rst = Path(template_rst)
    out_rst = Path(out_rst)
    out_rst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(template_rst, out_rst)

    sl = mask_pack["level_slice"]
    valid = mask_pack["mask"]
    with Dataset(out_rst, "r+") as ds:
        t = np.asarray(ds.variables["temperature"][:])
        s = np.asarray(ds.variables["salinity"][:])
        # (Time, nCells, nVertLevels)
        t0 = t[0]
        s0 = s[0]
        t_new = t0.copy()
        s_new = s0.copy()
        block_t = t_deep
        block_s = s_deep
        t_new[:, sl] = np.where(valid, block_t, t_new[:, sl])
        s_new[:, sl] = np.where(valid, block_s, s_new[:, sl])
        # preserve fills on inactive
        t_new = np.where(np.isfinite(t_new) & (np.abs(t_new) < FILL / 10), t_new, t0)
        s_new = np.where(np.isfinite(s_new) & (np.abs(s_new) < FILL / 10), s_new, s0)
        ds.variables["temperature"][0, :, :] = t_new
        ds.variables["salinity"][0, :, :] = s_new
        if xtime is not None and "xtime" in ds.variables:
            raw = np.array(xtime, dtype="S64")
            ds.variables["xtime"][0] = raw
        try:
            prev = getattr(ds, "history", "")
            ds.setncattr("history", (str(prev) + " | OceanAISpinup pilot: deep T/S overwrite k=46..60").strip(" |"))
        except Exception:
            pass
    return out_rst
