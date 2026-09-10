"""Deep OHC from restart T/S/h vs history AM / monthly stats."""

from __future__ import annotations

import numpy as np

from oceanai.data.extract import read_deep_state
from oceanai.paths import CP, RHO0, monthly_hist, ohc_am


def ohc_from_state(t: np.ndarray, h: np.ndarray, valid: np.ndarray, area: np.ndarray) -> dict:
    """t,h,valid: (nCells, nDeep) with T in °C; area: (nCells,) m².

    MPAS AM `oceanHeatContent*` uses T in Kelvin (T_C + 273.15) so the
    global sum matches history (J). Training residuals stay in native °C.
    """
    t_k = t + 273.15
    col = np.where(valid, t_k * h, 0.0).sum(axis=1)
    per_cell = RHO0 * CP * area * col
    return {
        "per_cell": per_cell,
        "global": float(per_cell.sum()),
        "n_valid": int(valid.sum()),
    }


def ohc_from_restart(rst_path, mask_pack: dict) -> dict:
    st = read_deep_state(rst_path, mask_pack)
    out = ohc_from_state(st["temperature"], st["layerThickness"], st["valid"], mask_pack["areaCell"])
    out["xtime"] = st["xtime"]
    return out


def _global_history_ohc(path, varname: str) -> float | None:
    from netCDF4 import Dataset

    if path is None or not path.exists():
        return None
    with Dataset(path, "r") as ds:
        if varname not in ds.variables:
            return None
        v = np.asarray(ds.variables[varname][:], dtype=np.float64)
    v = np.squeeze(v)
    v = np.where(np.isfinite(v), v, 0.0)
    return float(v.sum())


def compare_restart_to_history(rst_path, year: int, month: int, mask_pack: dict) -> dict:
    rst = ohc_from_restart(rst_path, mask_pack)
    hist_m = monthly_hist(year, month)
    am = ohc_am(year, month)
    h_monthly = _global_history_ohc(hist_m, "timeMonthly_avg_oceanHeatContent2000mToBot")
    h_am = _global_history_ohc(am, "oceanHeatContent2000mToBot")
    out = {
        "xtime": rst["xtime"],
        "restart_global_J": rst["global"],
        "history_monthly_global_J": h_monthly,
        "history_am_global_J": h_am,
        "n_valid": rst["n_valid"],
    }
    if h_monthly is not None and abs(h_monthly) > 0:
        out["rel_err_monthly"] = abs(rst["global"] - h_monthly) / abs(h_monthly)
    if h_am is not None and abs(h_am) > 0:
        out["rel_err_am"] = abs(rst["global"] - h_am) / abs(h_am)
    return out
