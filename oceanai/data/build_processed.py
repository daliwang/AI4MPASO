"""Build processed QU240 tensors from Kang's raw Frontier dump.

Writes mesh, deep mask, monthly DATM, 60 pair npz files, train-only scalers,
and persistence JSON under ``OCEANAI_PROCESSED`` (default:
``data/processed/QU240`` on Frontier).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from oceanai.baselines.persistence import compute_persistence
from oceanai.data.datm_encoder import build_datm_monthly, save_datm_monthly
from oceanai.data.extract import extract_pair, save_pair
from oceanai.data.pair_index import build_pair_index, write_pair_index
from oceanai.data.scalers import fit_scalers
from oceanai.mesh.deep_mask import build_deep_mask, load_column_geometry, save_deep_mask
from oceanai.mesh.graph import build_cell_graph, save_cell_graph
from oceanai.paths import CASE, REPO_ROOT, early_rst, processed_dirs, raw_available


PHYSICS_THETA = {
    "case": CASE,
    "mesh": "QU240",
    "nCells": 7153,
    "nVertLevels": 60,
    "calendar": "noleap",
    "forcing": "CORE2_NYF",
    "config_dt": "01:00:00",
    "config_mom_del2": 4000.0,
    "config_use_mom_del2": True,
    "config_mom_del4": 2.0e14,
    "config_use_mom_del4": True,
    "config_redi_closure": "constant",
    "config_redi_constant_kappa": 900.0,
    "config_gm_closure": "constant",
    "config_gm_constant_kappa": 900.0,
    "config_submesoscale_enable": True,
    "config_submesoscale_ce": 0.08,
    "note": (
        "Single namelist for this pack. Encode as a constant vector; do not treat "
        "theta as causal until a second physics case exists."
    ),
    "source": str(REPO_ROOT / "data" / "OceanSpin_sample" / "mpaso_variables"),
}


def _jan1_only(rows: list[dict]) -> list[dict]:
    return [r for r in rows if int(r["month"]) == 1]


def build_processed(*, jan1_only: bool = False, skip_existing_pairs: bool = True) -> dict:
    if not raw_available():
        raise FileNotFoundError(
            "Raw restarts not found. Set OCEANAI_RAW to Kang's Dali/ tree "
            "(needs rst.0051-01 and rst.0601-01)."
        )
    dirs = processed_dirs()
    rows = build_pair_index()
    if jan1_only:
        rows = _jan1_only(rows)
    write_pair_index(rows)

    geom = load_column_geometry(early_rst(51, 1))
    mask = build_deep_mask(geom)
    mask_path = save_deep_mask(mask)
    print(
        f"deep mask {mask['n_cells']} cells × {mask['n_deep']} levels, "
        f"{mask['n_deep_valid']} valid → {mask_path}"
    )

    graph = build_cell_graph(early_rst(51, 1))
    graph_path = save_cell_graph(graph)
    print(
        f"mesh graph n={graph['n_cells']} directed_edges={graph['n_directed_edges']} "
        f"→ {graph_path}"
    )

    save_datm_monthly(build_datm_monthly())

    theta_path = dirs["root"] / "physics_theta.json"
    theta_path.write_text(json.dumps(PHYSICS_THETA, indent=2))

    extracted = []
    for i, row in enumerate(rows, 1):
        out = dirs["pairs"] / f"{row['pair_id']}.npz"
        if skip_existing_pairs and out.exists():
            print(f"[{i}/{len(rows)}] skip {row['pair_id']} (exists)")
            extracted.append(row["pair_id"])
            continue
        pack = extract_pair(row, mask)
        save_pair(pack)
        print(f"[{i}/{len(rows)}] {row['pair_id']} {row['split']}")
        extracted.append(row["pair_id"])

    scalers = fit_scalers([r["pair_id"] for r in rows if r["split"] == "train"])
    persistence = compute_persistence()
    summary = {
        "n_pairs": len(rows),
        "n_extracted": len(extracted),
        "n_deep_valid": mask["n_deep_valid"],
        "n_directed_edges": graph["n_directed_edges"],
        "scalers": scalers,
        "persistence_train_rmse_t_C": persistence["train"]["rmse_t_C"],
        "persistence_holdout_rmse_t_C": persistence["holdout"]["rmse_t_C"],
        "root": str(dirs["root"]),
    }
    (dirs["root"] / "build_summary.json").write_text(json.dumps(summary, indent=2))
    return summary


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Extract AI tensors from raw QU240 restarts")
    p.add_argument("--jan1-only", action="store_true", help="5 Jan-1 pairs only (smoke)")
    p.add_argument("--force", action="store_true", help="re-extract pairs even if npz exists")
    args = p.parse_args(argv)
    summary = build_processed(jan1_only=args.jan1_only, skip_existing_pairs=not args.force)
    print(json.dumps({k: v for k, v in summary.items() if k != "scalers"}, indent=2))


if __name__ == "__main__":
    main()
