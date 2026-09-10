#!/usr/bin/env python3
"""Pilot end-to-end: pair index → DATM/mesh → persistence → tiny GNN → ML restart.

Usage (Frontier):
  module load cray-python/3.11.7
  source .venv/bin/activate
  python -m oceanai.run_prototype --stage all
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch

# repo root on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from oceanai.baselines.persistence import evaluate_persistence, pair_metrics, persistence_on_pair
from oceanai.data.datm_encoder import load_datm_monthly, save_datm_monthly
from oceanai.data.dataset import pair_to_tensors
from oceanai.data.extract import extract_pair, load_pair, save_pair
from oceanai.data.pair_index import load_pair_index, write_pair_index
from oceanai.data.scalers import fit_scalers, load_scalers, unzscore
from oceanai.io.write_restart import write_deep_ts
from oceanai.mesh.deep_mask import build_deep_mask, load_column_geometry, load_deep_mask, save_deep_mask
from oceanai.mesh.graph import build_cell_graph, load_cell_graph, save_cell_graph
from oceanai.models.residual_gnn import ResidualGNN, weighted_huber
from oceanai.paths import N_DEEP, early_rst, late_rst, processed_dirs
from oceanai.qc.ohc import compare_restart_to_history, ohc_from_restart


def _template_rst(row: dict):
    if row.get("path_x"):
        return Path(row["path_x"])
    return early_rst(int(row["year_x"]), int(row["month"]))


def stage_prepare(smoke: bool) -> tuple[list[dict], dict, dict]:
    dirs = processed_dirs()
    rows = load_pair_index() if (dirs["pairs"] / "index.json").exists() else None
    if rows is None:
        write_pair_index()
        rows = load_pair_index()
    else:
        print(f"pair index already present ({len(rows)} rows)")

    if smoke:
        keep = {"0051-01", "0052-01", "0053-01", "0054-01", "0055-01"}
        rows = [r for r in rows if r["pair_id"] in keep]
        print(f"smoke: {len(rows)} January pairs")

    rst0 = early_rst(51, 1)
    mask_path = dirs["root"] / "deep_mask.npz"
    graph_path = dirs["root"] / "mesh_graph.npz"
    if not mask_path.exists():
        geom = load_column_geometry(rst0)
        mask_pack = build_deep_mask(geom)
        save_deep_mask(mask_pack, mask_path)
        print(
            f"deep mask: nCells={mask_pack['n_cells']} nDeep={mask_pack['n_deep']} "
            f"valid={mask_pack['n_deep_valid']} ref={mask_pack['ref_deep'][0]:.1f}–{mask_pack['ref_deep'][-1]:.1f} m"
        )
    mask_pack = load_deep_mask(mask_path)

    if not graph_path.exists():
        mesh = build_cell_graph(rst0)
        save_cell_graph(mesh, graph_path)
        print(
            f"graph: nCells={mesh['n_cells']} directed_edges={mesh['n_directed_edges']} "
            f"max_degree={mesh['max_degree']}"
        )
    mesh = load_cell_graph(graph_path)

    datm_path = dirs["root"] / "datm_monthly.npz"
    if not datm_path.exists():
        save_datm_monthly()
    else:
        d = load_datm_monthly()
        print(f"DATM monthly already present {d['monthly'].shape}")

    for r in rows:
        npz = dirs["pairs"] / f"{r['pair_id']}.npz"
        if npz.exists():
            continue
        print(f"extract {r['pair_id']} …")
        save_pair(extract_pair(r, mask_pack))
    missing_scaler = not (dirs["scalers"] / "scalers.json").exists()
    train_ids = [r["pair_id"] for r in rows if r["split"] == "train"]
    if missing_scaler:
        fit_scalers(train_ids)
    else:
        print("scalers already present")
    return rows, mask_pack, mesh


def stage_qc(mask_pack: dict) -> dict:
    dirs = processed_dirs()
    reports = {
        "0051-01": compare_restart_to_history(early_rst(51, 1), 51, 1, mask_pack),
        "0601-01": compare_restart_to_history(late_rst(601, 1), 601, 1, mask_pack),
    }
    path = dirs["baselines"] / "ohc_qc.json"
    path.write_text(json.dumps(reports, indent=2))
    print("OHC QC (restart vs history):")
    for k, v in reports.items():
        print(f"  {k} xtime={v.get('xtime')} rst={v['restart_global_J']:.6e} J  {v}")
    return reports


def stage_baseline(rows: list[dict], mask_pack: dict) -> dict:
    return evaluate_persistence(rows, mask_pack["areaCell"])


def stage_truth_writeback(mask_pack: dict) -> dict:
    """Copy Y deep T/S into X template — proves the restart contract without a net."""
    dirs = processed_dirs()
    pair = load_pair("0051-01")
    out = dirs["restarts_ml"] / "rst.0051-01-01.truthY.nc"
    write_deep_ts(early_rst(51, 1), out, pair["t_y"], pair["s_y"], mask_pack)
    ohc_ml = ohc_from_restart(out, mask_pack)
    ohc_y = ohc_from_restart(late_rst(601, 1), mask_pack)
    rel = abs(ohc_ml["global"] - ohc_y["global"]) / max(abs(ohc_y["global"]), 1.0)
    report = {
        "out": str(out),
        "ohc_written_J": ohc_ml["global"],
        "ohc_Y_J": ohc_y["global"],
        "rel_err": rel,
    }
    (dirs["baselines"] / "truthY_writeback.json").write_text(json.dumps(report, indent=2))
    print(f"truth-Y writeback rel_err={rel:.3e} → {out}")
    return report


def _in_dim(mesh, mask_pack) -> int:
    # 15 T + 15 S + 7 static + DATM fields
    n_f = int(load_datm_monthly()["monthly"].shape[-1])
    return N_DEEP + N_DEEP + 7 + n_f


def stage_train(rows: list[dict], mesh: dict, mask_pack: dict, epochs: int, hidden: int, layers: int) -> Path:
    dirs = processed_dirs()
    train_rows = [r for r in rows if r["split"] == "train"]
    hold_rows = [r for r in rows if r["split"] == "holdout"]
    device = torch.device("cpu")
    model = ResidualGNN(_in_dim(mesh, mask_pack), n_deep=N_DEEP, hidden=hidden, n_layers=layers).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-4)
    ckpt = dirs["checkpoints"] / "track_a_proto.pt"

    best = float("inf")
    log = []
    for epoch in range(1, epochs + 1):
        model.train()
        losses = []
        for r in train_rows:
            batch = pair_to_tensors(r["pair_id"], mesh, mask_pack)
            x = batch["x"].to(device)
            y = batch["y"].to(device)
            valid = batch["valid"].to(device)
            w = batch["weight"].to(device)
            ei = batch["edge_index"].to(device)
            pred = model(x, ei)
            loss = weighted_huber(pred, y, valid, w)
            opt.zero_grad()
            loss.backward()
            opt.step()
            losses.append(float(loss.detach()))
        model.eval()
        hold_rmse = []
        with torch.no_grad():
            for r in hold_rows:
                m = _eval_pair(model, r["pair_id"], mesh, mask_pack, device)
                hold_rmse.append(m["rmse_t"])
        mean_hold = float(np.mean(hold_rmse)) if hold_rmse else float("nan")
        rec = {"epoch": epoch, "train_huber": float(np.mean(losses)), "holdout_rmse_t": mean_hold}
        log.append(rec)
        print(f"epoch {epoch:03d}  train={rec['train_huber']:.4f}  holdout_rmse_T={mean_hold:.4f}")
        if mean_hold < best:
            best = mean_hold
            torch.save({"model": model.state_dict(), "in_dim": _in_dim(mesh, mask_pack),
                        "hidden": hidden, "layers": layers}, ckpt)
    (dirs["checkpoints"] / "train_log.json").write_text(json.dumps(log, indent=2))
    print(f"best holdout RMSE T={best:.4f}  ckpt={ckpt}")
    return ckpt


def _load_model(ckpt: Path, mesh, mask_pack, device) -> ResidualGNN:
    blob = torch.load(ckpt, map_location=device, weights_only=False)
    model = ResidualGNN(blob["in_dim"], n_deep=N_DEEP, hidden=blob["hidden"], n_layers=blob["layers"])
    model.load_state_dict(blob["model"])
    model.to(device).eval()
    return model


def _predict_ts(model, pair_id, mesh, mask_pack, device) -> tuple[np.ndarray, np.ndarray]:
    sc = load_scalers()
    batch = pair_to_tensors(pair_id, mesh, mask_pack)
    with torch.no_grad():
        pred = model(batch["x"].to(device), batch["edge_index"].to(device)).cpu().numpy()
    n = N_DEEP
    dt = unzscore(pred[:, :n], sc["dt"])
    ds = unzscore(pred[:, n:], sc["ds"])
    p = load_pair(pair_id)
    t_hat = np.where(p["valid"], p["t_x"] + dt, p["t_x"])
    s_hat = np.where(p["valid"], p["s_x"] + ds, p["s_x"])
    return t_hat, s_hat


def _eval_pair(model, pair_id, mesh, mask_pack, device) -> dict:
    t_hat, s_hat = _predict_ts(model, pair_id, mesh, mask_pack, device)
    p = load_pair(pair_id)
    return pair_metrics(p, t_hat, s_hat, mask_pack["areaCell"])


def stage_infer(rows: list[dict], mesh: dict, mask_pack: dict) -> dict:
    dirs = processed_dirs()
    ckpt = dirs["checkpoints"] / "track_a_proto.pt"
    device = torch.device("cpu")
    model = _load_model(ckpt, mesh, mask_pack, device)
    hold = [r for r in rows if r["split"] == "holdout"]
    report = {"holdout": {}, "demo": {}}
    for r in hold:
        p = load_pair(r["pair_id"])
        t_hat, s_hat = _predict_ts(model, r["pair_id"], mesh, mask_pack, device)
        m_ml = pair_metrics(p, t_hat, s_hat, mask_pack["areaCell"])
        m_p = persistence_on_pair(p, mask_pack["areaCell"])
        report["holdout"][r["pair_id"]] = {"model": m_ml, "persistence": m_p}

    # demo writeback: 0055-01 if present else first holdout
    demo_id = "0055-01" if any(r["pair_id"] == "0055-01" for r in hold) else hold[0]["pair_id"]
    demo_row = next(r for r in hold if r["pair_id"] == demo_id)
    t_hat, s_hat = _predict_ts(model, demo_id, mesh, mask_pack, device)
    out = dirs["restarts_ml"] / "rst.0055-01-01.ml.nc"
    write_deep_ts(_template_rst(demo_row), out, t_hat, s_hat, mask_pack)
    ohc_ml = ohc_from_restart(out, mask_pack)
    report["demo"] = {
        "pair_id": demo_id,
        "out": str(out),
        "xtime_kept_from_template": True,
        "ohc_ml_J": ohc_ml["global"],
        "metrics": report["holdout"][demo_id],
    }
    path = dirs["baselines"] / "model_holdout.json"
    path.write_text(json.dumps(report, indent=2))
    print(f"holdout metrics → {path}")
    print(f"ML restart → {out}  OHC={ohc_ml['global']:.6e} J")
    return report


def main():
    ap = argparse.ArgumentParser(description="OceanAISpinup QU240 pilot workflow")
    ap.add_argument("--stage", default="all",
                    choices=["all", "prepare", "qc", "baseline", "truth-writeback", "train", "infer"])
    ap.add_argument("--smoke", action="store_true", help="January-only 5 pairs (faster demo)")
    ap.add_argument("--epochs", type=int, default=25)
    ap.add_argument("--hidden", type=int, default=64)
    ap.add_argument("--layers", type=int, default=6)
    args = ap.parse_args()

    rows, mask_pack, mesh = stage_prepare(args.smoke)
    if args.stage in ("all", "qc", "prepare"):
        stage_qc(mask_pack)
    if args.stage in ("all", "baseline"):
        bl = stage_baseline(rows, mask_pack)
        j = bl["summary"].get("jan1") or {}
        print(f"persistence 0051-01 RMSE T={j.get('rmse_t')}  OHC rel={j.get('ohc_rel_err')}")
        print(f"persistence holdout RMSE T={bl['summary'].get('holdout_rmse_t')}")
    if args.stage in ("all", "truth-writeback"):
        stage_truth_writeback(mask_pack)
    if args.stage in ("all", "train"):
        stage_train(rows, mesh, mask_pack, args.epochs, args.hidden, args.layers)
    if args.stage in ("all", "infer"):
        stage_infer(rows, mesh, mask_pack)
    print("done.")


if __name__ == "__main__":
    main()
