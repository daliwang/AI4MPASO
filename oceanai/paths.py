"""Paths for Kang's Frontier dump and local processed / AI-ready output.

Override on any machine:

    export OCEANAI_RAW=/path/to/Dali          # raw restarts + remapped DATM
    export OCEANAI_PROCESSED=/path/to/QU240   # tensors the trainer reads

Training on a second cluster only needs ``OCEANAI_PROCESSED`` (the AI-ready
pack). ``OCEANAI_RAW`` is required only to rebuild pairs from NetCDF.
"""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _path_from_env(name: str, default: Path) -> Path:
    v = os.environ.get(name, "").strip()
    return Path(v).expanduser().resolve() if v else default


DALI = _path_from_env(
    "OCEANAI_RAW",
    Path("/lustre/orion/cli115/world-shared/hgkang/data4others/Dali"),
)
EARLY_RST = DALI / "QU240_Restart_Hist_051-055" / "restart"
LATE_RST = DALI / "QU240_Restart_Hist_601-605" / "restart_files"
EARLY_HIST = DALI / "QU240_Restart_Hist_051-055" / "hist"
LATE_HIST = DALI / "QU240_Restart_Hist_601-605" / "history"
EARLY_OHC = DALI / "QU240_Restart_Hist_051-055" / "ocean_heat_content"
LATE_OHC = DALI / "QU240_Restart_Hist_601-605" / "ocean_heat_content"
DATM_REMAPPED = DALI / "remapped_datm" / "QU240-NYF" / "remapped"
MESH_NC = DALI / "QU240_Restart_Hist_601-605" / "mesh" / "ocean.QU.240km.151209.nc"

PROCESSED = _path_from_env(
    "OCEANAI_PROCESSED",
    Path("/lustre/orion/lrn105/proj-shared/wangd/AI4MPAS/data/processed/QU240"),
)
AIREADY_DEFAULT = REPO_ROOT / "data" / "aiready" / "QU240"

CASE = "v3.GMPAS-NYF_QU240"
RST_PREFIX = f"{CASE}.mpaso.rst."
RST_SUFFIX = "_00000.nc"
HIST_MONTHLY_PREFIX = f"{CASE}.mpaso.hist.am.timeSeriesStatsMonthly."
OHC_AM_PREFIX = f"{CASE}.mpaso.hist.am.oceanHeatContent."

DATM_NCEP = DATM_REMAPPED / "nyf.ncep.oQU240.050923.nc"
DATM_GXGXS = DATM_REMAPPED / "nyf.gxgxs.oQU240.051007.nc"
DATM_GISS = DATM_REMAPPED / "nyf.giss.oQU240.051007.nc"

RHO0 = 1026.0
CP = 3996.0
FILL = 9.969209968386869e36
DEEP_K0 = 45  # 0-based; 1-based k=46
N_DEEP = 15  # k=46..60

DATASET_NAME = "OceanAISpinup-QU240-aiready"
DATASET_VERSION = "1.0.0"


def rst_name(year: int, month: int) -> str:
    return f"{RST_PREFIX}{year:04d}-{month:02d}-01{RST_SUFFIX}"


def early_rst(year: int, month: int) -> Path:
    return EARLY_RST / rst_name(year, month)


def late_rst(year: int, month: int) -> Path:
    return LATE_RST / rst_name(year, month)


def monthly_hist(year: int, month: int) -> Path:
    name = f"{HIST_MONTHLY_PREFIX}{year:04d}-{month:02d}-01.nc"
    root = EARLY_HIST if year < 300 else LATE_HIST
    return root / name


def ohc_am(year: int, month: int) -> Path:
    name = f"{OHC_AM_PREFIX}{year:04d}-{month:02d}-01.nc"
    root = EARLY_OHC if year < 300 else LATE_OHC
    p = root / name
    if p.exists():
        return p
    # year-1–105 series lives next to early monthly stats
    alt = EARLY_HIST / name
    return alt


def raw_available() -> bool:
    return early_rst(51, 1).is_file() and late_rst(601, 1).is_file()


def processed_dirs(root: Path | None = None) -> dict[str, Path]:
    base = Path(root) if root is not None else PROCESSED
    dirs = {
        "root": base,
        "pairs": base / "pairs",
        "scalers": base / "scalers",
        "baselines": base / "baselines",
        "checkpoints": base / "checkpoints",
        "restarts_ml": base / "restarts_ml",
        "templates": base / "templates",
    }
    for p in dirs.values():
        p.mkdir(parents=True, exist_ok=True)
    return dirs
