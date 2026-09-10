"""Per-variable z-score on train pairs only (deep valid points)."""

from __future__ import annotations

import json

import numpy as np

from oceanai.data.extract import load_pair
from oceanai.data.pair_index import load_pair_index
from oceanai.paths import processed_dirs


def _stats(vals: np.ndarray) -> dict:
    return {"mean": float(vals.mean()), "std": float(max(vals.std(), 1e-6))}


def fit_scalers(pair_ids: list[str] | None = None) -> dict:
    rows = load_pair_index()
    if pair_ids is None:
        pair_ids = [r["pair_id"] for r in rows if r["split"] == "train"]
    t_x, s_x, d_t, d_s = [], [], [], []
    for pid in pair_ids:
        p = load_pair(pid)
        v = p["valid"]
        t_x.append(p["t_x"][v])
        s_x.append(p["s_x"][v])
        d_t.append((p["t_y"] - p["t_x"])[v])
        d_s.append((p["s_y"] - p["s_x"])[v])
    scalers = {
        "t_x": _stats(np.concatenate(t_x)),
        "s_x": _stats(np.concatenate(s_x)),
        "dt": _stats(np.concatenate(d_t)),
        "ds": _stats(np.concatenate(d_s)),
        "n_train_pairs": len(pair_ids),
    }
    out = processed_dirs()["scalers"] / "scalers.json"
    out.write_text(json.dumps(scalers, indent=2))
    print(f"scalers → {out}")
    return scalers


def load_scalers(root=None) -> dict:
    return json.loads((processed_dirs(root)["scalers"] / "scalers.json").read_text())


def zscore(x, spec: dict) -> np.ndarray:
    return (x - spec["mean"]) / spec["std"]


def unzscore(z, spec: dict) -> np.ndarray:
    return z * spec["std"] + spec["mean"]
