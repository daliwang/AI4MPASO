"""Monthly NYF on oQU240 cells (shared across pairs)."""

from __future__ import annotations

import numpy as np

from oceanai.paths import DATM_GISS, DATM_GXGXS, DATM_NCEP, processed_dirs

NCEP_FIELDS = ["u_10", "v_10", "t_10", "slp_", "q_10", "dn10"]
NOLEAP_DAYS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def _monthly_from_subdaily(values: np.ndarray, steps_per_day: int) -> np.ndarray:
    """values: (time, ncol) with uniform sub-daily steps covering 365 noleap days."""
    months = []
    i = 0
    for nd in NOLEAP_DAYS:
        n = nd * steps_per_day
        months.append(values[i : i + n].mean(axis=0))
        i += n
    if i != values.shape[0]:
        raise ValueError(f"time length {values.shape[0]} != 365*{steps_per_day}")
    return np.stack(months, axis=0)


def _monthly_from_daily(values: np.ndarray) -> np.ndarray:
    months = []
    i = 0
    for nd in NOLEAP_DAYS:
        months.append(values[i : i + nd].mean(axis=0))
        i += nd
    if i != values.shape[0]:
        raise ValueError(f"daily time length {values.shape[0]} != 365")
    return np.stack(months, axis=0)


def build_datm_monthly() -> dict:
    from netCDF4 import Dataset

    with Dataset(DATM_NCEP, "r") as ds:
        ncep = {name: np.asarray(ds.variables[name][:], dtype=np.float32) for name in NCEP_FIELDS}
        lat = np.asarray(ds.variables["lat"][:], dtype=np.float64)
        lon = np.asarray(ds.variables["lon"][:], dtype=np.float64)
    ncep["q_10"] = np.clip(ncep["q_10"], 0.0, None)
    ncep_m = {k: _monthly_from_subdaily(v, 4) for k, v in ncep.items()}

    with Dataset(DATM_GXGXS, "r") as ds:
        prc = np.asarray(ds.variables["prc"][:], dtype=np.float32)  # (12, ncol)
    with Dataset(DATM_GISS, "r") as ds:
        giss = {
            name: _monthly_from_daily(np.asarray(ds.variables[name][:], dtype=np.float32))
            for name in ("lwdn", "swdn", "swup")
        }

    field_order = NCEP_FIELDS + ["prc", "lwdn", "swdn", "swup"]
    stacked = np.stack(
        [ncep_m[k] for k in NCEP_FIELDS] + [prc, giss["lwdn"], giss["swdn"], giss["swup"]],
        axis=-1,
    )  # (12, ncol, F)
    return {
        "fields": np.array(field_order),
        "monthly": stacked.astype(np.float32),
        "lat": lat,
        "lon": lon,
    }


def save_datm_monthly(pack: dict | None = None) -> None:
    pack = pack or build_datm_monthly()
    out = processed_dirs()["root"] / "datm_monthly.npz"
    np.savez_compressed(out, **pack)
    print(f"DATM monthly {pack['monthly'].shape} → {out}")


def load_datm_monthly(path=None) -> dict:
    from pathlib import Path

    src = Path(path) if path is not None else processed_dirs()["root"] / "datm_monthly.npz"
    z = np.load(src, allow_pickle=True)
    return {k: z[k] for k in z.files}
