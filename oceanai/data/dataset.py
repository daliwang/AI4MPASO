"""Full-graph samples for the residual GNN."""

from __future__ import annotations

import numpy as np
import torch

from oceanai.data.datm_encoder import load_datm_monthly
from oceanai.data.extract import load_pair
from oceanai.data.scalers import load_scalers, zscore


def pair_to_tensors(pair_id: str, mesh: dict, mask_pack: dict) -> dict:
    p = load_pair(pair_id)
    sc = load_scalers()
    datm = load_datm_monthly()
    month = int(np.asarray(p["month"]).reshape(-1)[0])
    f = datm["monthly"][month - 1]  # (nCells, nF)
    lat = mask_pack["latCell"]
    lon = mask_pack["lonCell"]
    static = np.stack(
        [
            np.sin(lat),
            np.cos(lat),
            np.sin(lon),
            np.cos(lon),
            np.log1p(np.clip(mask_pack["bottomDepth"], 0, None)) / 10.0,
            np.sin(2 * np.pi * (month - 1) / 12.0) * np.ones_like(lat),
            np.cos(2 * np.pi * (month - 1) / 12.0) * np.ones_like(lat),
        ],
        axis=1,
    ).astype(np.float32)

    t_x = zscore(p["t_x"], sc["t_x"])
    s_x = zscore(p["s_x"], sc["s_x"])
    dt = zscore(p["t_y"] - p["t_x"], sc["dt"])
    ds = zscore(p["s_y"] - p["s_x"], sc["ds"])
    node = np.concatenate([t_x, s_x, static, f.astype(np.float32)], axis=1)
    target = np.concatenate([dt, ds], axis=1)
    valid = p["valid"].astype(np.float32)
    w = (mask_pack["areaCell"][:, None] * p["h_x"]).astype(np.float32)
    w = np.where(p["valid"], w, 0.0)

    return {
        "pair_id": pair_id,
        "month": month,
        "x": torch.from_numpy(node),
        "y": torch.from_numpy(target.astype(np.float32)),
        "valid": torch.from_numpy(valid),
        "weight": torch.from_numpy(w),
        "edge_index": torch.from_numpy(mesh["edge_index"]),
        "t_x": p["t_x"],
        "s_x": p["s_x"],
        "t_y": p["t_y"],
        "s_y": p["s_y"],
        "h_x": p["h_x"],
        "valid_np": p["valid"],
    }
