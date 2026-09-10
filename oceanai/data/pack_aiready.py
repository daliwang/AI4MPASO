"""Export a portable AI-ready QU240 pack for a second GPU cluster.

Training on the destination machine needs numpy + torch and this pack.
Raw Frontier restarts (~19 GB) and netCDF4 are not required unless you
also copy restart templates for writeback.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tarfile
from datetime import date, datetime, timezone
from pathlib import Path

from oceanai.data.build_processed import PHYSICS_THETA, build_processed
from oceanai.data.pair_index import load_pair_index, write_portable_index
from oceanai.paths import (
    AIREADY_DEFAULT,
    DATASET_NAME,
    DATASET_VERSION,
    early_rst,
    processed_dirs,
    rst_name,
)

TEMPLATE_PRESETS = {
    "none": [],
    "jan1-holdout": [(55, 1)],
    "holdout": [(55, m) for m in range(1, 13)],
    "all-x": [(y, m) for y in range(51, 56) for m in range(1, 13)],
}

_COPY_ROOT_FILES = (
    "mesh_graph.npz",
    "deep_mask.npz",
    "datm_monthly.npz",
    "physics_theta.json",
    "build_summary.json",
)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _copy_if_exists(src: Path, dst: Path) -> bool:
    if not src.is_file():
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return True


def _ensure_processed(*, jan1_only: bool, force_extract: bool, skip_build: bool) -> None:
    root = processed_dirs()["root"]
    ready = (root / "mesh_graph.npz").is_file() and (root / "pairs" / "index.json").is_file()
    n_npz = len(list((root / "pairs").glob("????-??.npz"))) if ready else 0
    need = 5 if jan1_only else 60
    if skip_build and not ready:
        raise FileNotFoundError(f"Nothing to pack under {root}; run without --skip-build")
    if skip_build:
        return
    if force_extract or not ready or n_npz < need:
        build_processed(jan1_only=jan1_only, skip_existing_pairs=not force_extract)


def _write_pack_readme(out: Path, manifest: dict) -> None:
    n_train = manifest["split"]["train"]
    n_hold = manifest["split"]["holdout"]
    text = f"""# {manifest["name"]} {manifest["version"]}

AI-ready QU240 spinup pairs for the early→equilibrium restart operator.
This directory is **self-contained for training**. It is not Kang's raw
Frontier dump.

## What this is

| Item | Value |
|---|---|
| Mesh | QU240, {manifest["n_cells"]} cells, deep k=46…60 ({manifest["n_deep"]} levels) |
| Pairs | {manifest["n_pairs"]} month-aligned, Δ = {manifest["delta_years"]} yr |
| Split | train {n_train} (years 51–54 → 601–604); holdout {n_hold} (55 → 605) |
| Forcing | monthly CORE2 NYF on the same cells (shared; NYF cycles) |
| Created | {manifest["created"]} |

Each `pairs/YYYY-MM.npz` holds deep `t_x,s_x,h_x` (year ~50) and
`t_y,s_y,h_y` (year ~600), plus a boolean `valid` mask.

## What this is not

- Not the ~19 GB raw restart / history / DATM NetCDF tree
- Not history monthly-mean T/S (those are QC-only and are omitted)
- Not a continuous year-56…600 archive
- `templates/` (if present) are **X restart copies for writeback**, not training labels

## Use on another cluster

```bash
# 1. copy this tree (or the .tar.gz) and the git repo
export OCEANAI_PROCESSED=/path/to/QU240
cd /path/to/AI4MPAS
python - <<'PY'
from oceanai.data.pair_index import load_pair_index
from oceanai.data.extract import load_pair
from oceanai.data.assets import load_training_assets
from oceanai.data.pack_aiready import verify_pack

verify_pack()
print("pairs", len(load_pair_index()))
print("sample", load_pair("0051-01")["t_x"].shape)
print("graph", load_training_assets()["mesh"]["edge_index"].shape)
PY
```

Training needs **numpy** and **pytorch**. `netCDF4` is only required to
write an MPAS restart from `templates/`.

Do not set `OCEANAI_RAW` unless you are rebuilding from Frontier restarts.
"""
    (out / "DATASET.md").write_text(text)


def _holdout_rmse(persist: dict) -> float | None:
    hold = persist.get("holdout") or {}
    for key in ("rmse_t_C", "rmse_t"):
        if key in hold:
            return hold[key]
    summary = persist.get("summary") or {}
    if "holdout_rmse_t" in summary:
        return summary["holdout_rmse_t"]
    return None


def pack_aiready(
    out_dir: Path | None = None,
    *,
    templates: str = "jan1-holdout",
    tar: bool = True,
    jan1_only: bool = False,
    skip_build: bool = False,
    force_extract: bool = False,
) -> dict:
    if templates not in TEMPLATE_PRESETS:
        raise ValueError(f"templates must be one of {list(TEMPLATE_PRESETS)}")
    _ensure_processed(jan1_only=jan1_only, force_extract=force_extract, skip_build=skip_build)

    src = processed_dirs()["root"]
    out = Path(out_dir) if out_dir is not None else AIREADY_DEFAULT
    if out.resolve() == src.resolve():
        raise ValueError("AI-ready out dir must differ from OCEANAI_PROCESSED working tree")
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    for name in _COPY_ROOT_FILES:
        _copy_if_exists(src / name, out / name)
    if not (out / "physics_theta.json").exists():
        (out / "physics_theta.json").write_text(json.dumps(PHYSICS_THETA, indent=2))

    (out / "pairs").mkdir()
    rows = load_pair_index()
    for r in rows:
        npz_name = r.get("npz", f"{r['pair_id']}.npz")
        npz = src / "pairs" / npz_name
        if not npz.exists():
            raise FileNotFoundError(npz)
        shutil.copy2(npz, out / "pairs" / Path(npz_name).name)
    write_portable_index(rows, out / "pairs")

    (out / "scalers").mkdir()
    _copy_if_exists(src / "scalers" / "scalers.json", out / "scalers" / "scalers.json")
    (out / "baselines").mkdir()
    for name in ("persistence.json", "ohc_qc.json"):
        _copy_if_exists(src / "baselines" / name, out / "baselines" / name)

    copied_templates = []
    for year, month in TEMPLATE_PRESETS[templates]:
        src_rst = early_rst(year, month)
        if not src_rst.exists():
            raise FileNotFoundError(src_rst)
        dest = out / "templates" / rst_name(year, month)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_rst, dest)
        copied_templates.append(dest.name)

    n_train = sum(r["split"] == "train" for r in rows)
    n_hold = sum(r["split"] == "holdout" for r in rows)
    files = sorted(
        p.relative_to(out).as_posix()
        for p in out.rglob("*")
        if p.is_file()
    )
    checksums = {rel: _sha256(out / rel) for rel in files}
    (out / "SHA256SUMS").write_text(
        "".join(f"{digest}  {rel}\n" for rel, digest in checksums.items())
    )

    persist = {}
    persist_path = out / "baselines" / "persistence.json"
    if persist_path.exists():
        persist = json.loads(persist_path.read_text())

    bytes_total = sum((out / rel).stat().st_size for rel in files)
    manifest = {
        "name": DATASET_NAME,
        "version": DATASET_VERSION,
        "created": date.today().isoformat(),
        "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "mesh": "QU240",
        "case": PHYSICS_THETA["case"],
        "n_cells": 7153,
        "n_deep": 15,
        "k_levels_1based": [46, 60],
        "delta_years": 550,
        "n_pairs": len(rows),
        "split": {"train": n_train, "holdout": n_hold},
        "pair_ids": [r["pair_id"] for r in rows],
        "datm_fields": [
            "u_10",
            "v_10",
            "t_10",
            "slp_",
            "q_10",
            "dn10",
            "prc",
            "lwdn",
            "swdn",
            "swup",
        ],
        "pair_arrays": [
            "t_x",
            "s_x",
            "h_x",
            "t_y",
            "s_y",
            "h_y",
            "valid",
            "month",
            "year_x",
            "split",
            "xtime_x",
            "xtime_y",
        ],
        "templates": copied_templates,
        "bytes": bytes_total,
        "files": files,
        "sha256": checksums,
        "persistence_holdout_rmse_t_C": _holdout_rmse(persist),
        "requires_for_train": ["numpy", "torch"],
        "requires_for_writeback": ["netCDF4"],
        "env": {"OCEANAI_PROCESSED": "<unpack-dir>/QU240"},
        "source_raw": "Frontier Kang Dali/ tree; not included",
        "repo_docs": "data/docs/AIREADY_DATASET.md",
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    # checksums were computed before manifest/DATASET.md; rewrite SHA256SUMS to include them
    _write_pack_readme(out, manifest)
    files2 = sorted(p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file())
    checksums2 = {rel: _sha256(out / rel) for rel in files2}
    (out / "SHA256SUMS").write_text(
        "".join(f"{digest}  {rel}\n" for rel, digest in checksums2.items())
    )
    manifest["files"] = files2
    manifest["sha256"] = checksums2
    manifest["bytes"] = sum((out / rel).stat().st_size for rel in files2)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    # manifest changed after hashing itself — freeze checksums excluding SHA256SUMS/manifest loop
    checksums_final = {
        rel: _sha256(out / rel)
        for rel in files2
        if rel not in {"SHA256SUMS", "manifest.json"}
    }
    checksums_final["DATASET.md"] = _sha256(out / "DATASET.md")
    (out / "SHA256SUMS").write_text(
        "".join(f"{digest}  {rel}\n" for rel, digest in sorted(checksums_final.items()))
    )
    manifest["sha256"] = checksums_final
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))

    tar_path = None
    tar_meta = {}
    if tar:
        tar_path = out.parent / f"{DATASET_NAME}-v{DATASET_VERSION}.tar.gz"
        if tar_path.exists():
            tar_path.unlink()
        with tarfile.open(tar_path, "w:gz") as tf:
            tf.add(out, arcname="QU240")
        tar_meta = {
            "tarball": str(tar_path),
            "tarball_bytes": tar_path.stat().st_size,
            "tarball_sha256": _sha256(tar_path),
        }
        print(
            f"tarball {tar_path} ({tar_meta['tarball_bytes'] / 1e6:.1f} MB) "
            f"sha256={tar_meta['tarball_sha256'][:12]}…"
        )

    print(
        f"AI-ready pack {len(rows)} pairs, {manifest['bytes'] / 1e6:.1f} MB unpacked → {out}"
    )
    return {**manifest, **tar_meta}


def verify_pack(root: Path | None = None) -> dict:
    """Load tensors without touching OCEANAI_RAW. Raises on a broken pack."""
    import numpy as np

    from oceanai.data.assets import load_training_assets
    from oceanai.data.extract import load_pair

    dirs = processed_dirs(root)
    base = dirs["root"]
    man_path = base / "manifest.json"
    if not man_path.exists():
        raise FileNotFoundError(f"missing manifest.json under {base}")
    man = json.loads(man_path.read_text())
    rows = load_pair_index(root)
    if len(rows) != man["n_pairs"]:
        raise ValueError(f"index {len(rows)} vs manifest {man['n_pairs']}")
    for r in rows:
        p = base / "pairs" / r["npz"]
        if not p.exists():
            raise FileNotFoundError(p)
    sample = load_pair(rows[0]["pair_id"], root=root)
    assets = load_training_assets(root)
    n_cells = int(assets["mask"]["n_cells"])
    n_deep = int(assets["mask"]["n_deep"])
    if sample["t_x"].shape != (n_cells, n_deep):
        raise ValueError(f"t_x shape {sample['t_x'].shape} != {(n_cells, n_deep)}")
    if assets["mesh"]["edge_index"].shape[0] != 2:
        raise ValueError("edge_index must be (2, E)")
    monthly = np.asarray(assets["datm"]["monthly"])
    if monthly.shape[0] != 12 or monthly.shape[1] != n_cells:
        raise ValueError(f"datm monthly shape {monthly.shape}")
    print(
        f"verify ok: {len(rows)} pairs, t_x {sample['t_x'].shape}, "
        f"edges {assets['mesh']['n_directed_edges']}"
    )
    return {"n_pairs": len(rows), "t_x": list(sample["t_x"].shape), "root": str(base)}


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(
        description="Build/export a portable AI-ready QU240 dataset"
    )
    p.add_argument(
        "--out",
        type=Path,
        default=AIREADY_DEFAULT,
        help="unpacked pack directory (default: data/aiready/QU240)",
    )
    p.add_argument(
        "--templates",
        choices=sorted(TEMPLATE_PRESETS),
        default="jan1-holdout",
        help="X restart copies for writeback on the destination cluster",
    )
    p.add_argument("--no-tar", action="store_true", help="skip .tar.gz")
    p.add_argument("--jan1-only", action="store_true", help="5 Jan-1 pairs only")
    p.add_argument("--skip-build", action="store_true", help="pack existing processed/ only")
    p.add_argument("--force-extract", action="store_true", help="re-read raw restarts")
    p.add_argument(
        "--verify-only",
        action="store_true",
        help="check OCEANAI_PROCESSED pack; do not export",
    )
    args = p.parse_args(argv)
    if args.verify_only:
        verify_pack()
        return
    pack_aiready(
        args.out,
        templates=args.templates,
        tar=not args.no_tar,
        jan1_only=args.jan1_only,
        skip_build=args.skip_build,
        force_extract=args.force_extract,
    )


if __name__ == "__main__":
    main()
