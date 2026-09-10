"""Load mesh / mask / DATM / scalers from an AI-ready processed tree."""

from __future__ import annotations

from oceanai.data.datm_encoder import load_datm_monthly
from oceanai.data.scalers import load_scalers
from oceanai.mesh.deep_mask import load_deep_mask
from oceanai.mesh.graph import load_cell_graph
from oceanai.paths import processed_dirs


def load_training_assets(root=None) -> dict:
    """Everything the residual GNN needs besides a pair npz. No raw NetCDF."""
    base = processed_dirs(root)["root"]
    return {
        "mesh": load_cell_graph(base / "mesh_graph.npz"),
        "mask": load_deep_mask(base / "deep_mask.npz"),
        "datm": load_datm_monthly(base / "datm_monthly.npz"),
        "scalers": load_scalers(root),
        "root": base,
    }
