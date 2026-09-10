"""Persistence baseline from AI-ready pair tensors (no raw NetCDF)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from oceanai.data.extract import load_pair
from oceanai.data.pair_index import load_pair_index
from oceanai.mesh.deep_mask import load_deep_mask
from oceanai.paths import processed_dirs
from oceanai.qc.ohc import ohc_from_state


def pair_metrics(
    p: dict,
    t_hat: np.ndarray,
    s_hat: np.ndarray,
    area: np.ndarray,
    h_hat: np.ndarray | None = None,
) -> dict:
    """Area × layer-thickness RMSE of a predicted deep T/S vs Y."""
    valid = np.asarray(p["valid"], dtype=bool)
    h = np.asarray(p["h_x"] if h_hat is None else h_hat, dtype=np.float64)
    w = np.where(valid, area[:, None] * h, 0.0)
    wsum = float(w.sum())
    if wsum <= 0:
        raise ValueError("no valid deep mass for metrics weights")
    dt = np.asarray(p["t_y"], dtype=np.float64) - np.asarray(t_hat, dtype=np.float64)
    ds = np.asarray(p["s_y"], dtype=np.float64) - np.asarray(s_hat, dtype=np.float64)
    ohc_hat = ohc_from_state(t_hat, h, valid, area)
    ohc_y = ohc_from_state(p["t_y"], p["h_y"], valid, area)
    ohc_err = ohc_hat["global"] - ohc_y["global"]
    rmse_t = float(np.sqrt((w * dt**2).sum() / wsum))
    rmse_s = float(np.sqrt((w * ds**2).sum() / wsum))
    bias_t = float((w * dt).sum() / wsum)
    bias_s = float((w * ds).sum() / wsum)
    rel = abs(ohc_err) / max(abs(ohc_y["global"]), 1.0)
    return {
        "rmse_t": rmse_t,
        "rmse_s": rmse_s,
        "bias_t": bias_t,
        "bias_s": bias_s,
        "rmse_t_C": rmse_t,
        "bias_t_C": bias_t,
        "ohc_hat_J": ohc_hat["global"],
        "ohc_y_J": ohc_y["global"],
        "ohc_err_J": ohc_err,
        "ohc_rel_err": rel,
        "n_valid": int(valid.sum()),
    }


def persistence_on_pair(p: dict, area: np.ndarray) -> dict:
    """Persistence: predict Y from X (deep T/S unchanged)."""
    m = pair_metrics(p, p["t_x"], p["s_x"], area, h_hat=p["h_x"])
    ohc_x = ohc_from_state(p["t_x"], p["h_x"], np.asarray(p["valid"], dtype=bool), area)
    m["ohc_x_J"] = ohc_x["global"]
    m["ohc_persist_minus_y_J"] = ohc_x["global"] - m["ohc_y_J"]
    return m


def pair_persistence(p: dict, area: np.ndarray) -> dict:
    return persistence_on_pair(p, area)


def evaluate_persistence(rows: list[dict], area: np.ndarray, root: Path | None = None) -> dict:
    by_pair = {}
    for r in rows:
        p = load_pair(r["pair_id"], root=root)
        m = persistence_on_pair(p, area)
        m["split"] = r["split"]
        m["month"] = int(r["month"])
        m["year_x"] = int(r.get("year_x", 0))
        by_pair[r["pair_id"]] = m

    def _mean(split: str, key: str) -> float:
        vals = [v[key] for v in by_pair.values() if v["split"] == split]
        return float(np.mean(vals)) if vals else float("nan")

    summary = {
        "train_rmse_t": _mean("train", "rmse_t"),
        "holdout_rmse_t": _mean("holdout", "rmse_t"),
        "train_rmse_s": _mean("train", "rmse_s"),
        "holdout_rmse_s": _mean("holdout", "rmse_s"),
        "jan1": by_pair.get("0051-01"),
        "holdout_0055-01": by_pair.get("0055-01"),
    }
    out_obj = {
        "formula": "persistence = predict Y from X; RMSE area×layerThickness on deep valid cells",
        "pairs": by_pair,
        "summary": summary,
        "train": {
            "n": sum(v["split"] == "train" for v in by_pair.values()),
            "rmse_t_C": summary["train_rmse_t"],
            "rmse_s": summary["train_rmse_s"],
        },
        "holdout": {
            "n": sum(v["split"] == "holdout" for v in by_pair.values()),
            "rmse_t_C": summary["holdout_rmse_t"],
            "rmse_s": summary["holdout_rmse_s"],
        },
    }
    dest = processed_dirs(root)["baselines"] / "persistence.json"
    dest.write_text(json.dumps(out_obj, indent=2))
    print(
        f"persistence train RMSE T={summary['train_rmse_t']:.4f} C  "
        f"holdout RMSE T={summary['holdout_rmse_t']:.4f} C → {dest}"
    )
    return out_obj


def compute_persistence(root: Path | None = None) -> dict:
    mask = load_deep_mask(processed_dirs(root)["root"] / "deep_mask.npz")
    rows = load_pair_index(root)
    return evaluate_persistence(rows, mask["areaCell"], root=root)
