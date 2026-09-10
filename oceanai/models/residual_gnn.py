"""Cell-only residual GNN (mean-aggregate neighbors). No PyG required."""

from __future__ import annotations

import torch
from torch import nn


def scatter_mean(src: torch.Tensor, index: torch.Tensor, dim_size: int) -> torch.Tensor:
    out = src.new_zeros((dim_size, src.size(-1)))
    count = src.new_zeros((dim_size, 1))
    out.index_add_(0, index, src)
    ones = torch.ones(src.size(0), 1, device=src.device, dtype=src.dtype)
    count.index_add_(0, index, ones)
    return out / count.clamp(min=1.0)


class GraphSAGELayer(nn.Module):
    def __init__(self, dim: int):
        super().__init__()
        self.lin = nn.Linear(dim * 2, dim)
        self.norm = nn.LayerNorm(dim)

    def forward(self, h: torch.Tensor, edge_index: torch.Tensor) -> torch.Tensor:
        src, dst = edge_index[0], edge_index[1]
        agg = scatter_mean(h[src], dst, h.size(0))
        out = self.lin(torch.cat([h, agg], dim=-1))
        return self.norm(torch.relu(out)) + h


class ResidualGNN(nn.Module):
    """Predicts normalized (ΔT, ΔS) on deep levels from node features."""

    def __init__(self, in_dim: int, n_deep: int = 15, hidden: int = 64, n_layers: int = 6):
        super().__init__()
        self.n_deep = n_deep
        self.encoder = nn.Sequential(nn.Linear(in_dim, hidden), nn.ReLU(), nn.LayerNorm(hidden))
        self.layers = nn.ModuleList([GraphSAGELayer(hidden) for _ in range(n_layers)])
        self.head = nn.Linear(hidden, n_deep * 2)

    def forward(self, x: torch.Tensor, edge_index: torch.Tensor) -> torch.Tensor:
        h = self.encoder(x)
        for layer in self.layers:
            h = layer(h, edge_index)
        return self.head(h)


def weighted_huber(pred, target, valid, weight, delta: float = 1.0) -> torch.Tensor:
    err = pred - target
    abs_err = err.abs()
    huber = torch.where(abs_err < delta, 0.5 * err**2, delta * (abs_err - 0.5 * delta))
    w = weight * valid
    # broadcast if weight is (N, nDeep) and pred is (N, 2*nDeep)
    if w.shape != huber.shape:
        if w.shape[-1] * 2 == huber.shape[-1]:
            w = torch.cat([w, w], dim=-1)
        else:
            raise ValueError(f"weight {w.shape} vs pred {huber.shape}")
    denom = w.sum().clamp(min=1e-8)
    return (huber * w).sum() / denom
