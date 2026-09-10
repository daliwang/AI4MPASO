# AI-ready QU240 dataset (portable pack)

**Command:** `python -m oceanai.data.pack_aiready`  
**Default output:** `data/aiready/QU240/` plus `data/aiready/OceanAISpinup-QU240-aiready-v1.0.0.tar.gz`  
**Why:** train and iterate on a dedicated GPU cluster without Kang’s ~19 GB Frontier NetCDF dump.

Raw restarts stay on Frontier. This pack is the **tensors the model actually consumes**: deep T/S/h pairs, mesh graph, deep mask, monthly NYF, train-only scalers, persistence numbers, and (optional) one X restart template for writeback.

---

## What you copy to the other cluster

| Item | Where | Needed for |
|---|---|---|
| Git repo (`oceanai/`, docs, `requirements.txt`) | this project | code |
| AI-ready pack (`QU240/` or the `.tar.gz`) | `data/aiready/` after the command below | training |
| Optional: more X restart templates | `--templates holdout` or `all-x` | writeback of every holdout month |

Do **not** copy `QU240_Restart_Hist_*`, remapped 6-hourly DATM, or monthly history unless you are rebuilding the pack or running MPAS-Analysis.

Size (order of magnitude, measured when packed): tens to a few hundred MB for tensors; +~57 MB per X restart template. Raw dump is ~19 GB.

---

## Build on Frontier (once)

Use the project venv (needs `netCDF4` to *read* raw restarts):

```bash
cd /lustre/orion/lrn105/proj-shared/wangd/AI4MPAS
source .venv/bin/activate
export PYTHONPATH="$PWD"
# optional; these are the defaults on Frontier
# export OCEANAI_RAW=/lustre/orion/cli115/world-shared/hgkang/data4others/Dali
# export OCEANAI_PROCESSED=/lustre/orion/lrn105/proj-shared/wangd/AI4MPAS/data/processed/QU240

python -m oceanai.data.pack_aiready --templates jan1-holdout
```

That will:

1. Extract 60 month-aligned pairs (0051–0055 → 0601–0605) into `data/processed/QU240/`
2. Fit scalers on the 48 training pairs
3. Write persistence RMSE from the tensors
4. Copy a portable tree to `data/aiready/QU240/` (relative index, checksums, dataset card)
5. Include **one** X restart (`rst.0055-01-01`) for prototype writeback
6. Make `data/aiready/OceanAISpinup-QU240-aiready-v1.0.0.tar.gz`

Useful flags:

| Flag | Effect |
|---|---|
| `--jan1-only` | 5 Jan-1 pairs (smoke pack) |
| `--templates none` | tensors only (smallest; no writeback on dest) |
| `--templates holdout` | 12 holdout X restarts (~0.7 GB) |
| `--templates all-x` | all 60 early restarts (~3.5 GB) |
| `--no-tar` | skip gzip archive |
| `--skip-build` | re-export from existing `processed/` |
| `--verify-only` | check `$OCEANAI_PROCESSED` without exporting |

Working extract lives in `data/processed/QU240/` (Frontier paths, extra dirs for checkpoints). The **transfer artifact** is `data/aiready/`.

---

## Layout inside the pack

```
QU240/
  DATASET.md
  manifest.json
  SHA256SUMS
  mesh_graph.npz          # cellsOnCell → edge_index (once)
  deep_mask.npz           # k=46…60, valid columns
  datm_monthly.npz        # (12, nCells, 10) NYF on cells
  physics_theta.json      # constant mpaso_in subset
  pairs/index.json        # pair_id, years, month, split, npz  (no Lustre paths)
  pairs/0051-01.npz       # … 0055-12.npz
  scalers/scalers.json    # train-only z-score
  baselines/persistence.json
  templates/              # optional X restart copy/copies
```

Each pair npz: `t_x,s_x,h_x,t_y,s_y,h_y` as `float32` `(7153, 15)` plus `valid` bool. Invalid deep points are zeroed.

Split (locked): train `0051–0054` → `0601–0604` (48); holdout `0055` → `0605` (12).

---

## On the destination GPU cluster

```bash
tar -xzf OceanAISpinup-QU240-aiready-v1.0.0.tar.gz
# → QU240/

git clone <this-repo> AI4MPSO && cd AI4MPSO
python3 -m venv .venv && source .venv/bin/activate
pip install numpy torch   # netCDF4 only if you will write restarts

export OCEANAI_PROCESSED=/absolute/path/to/QU240
export PYTHONPATH="$PWD"

python -m oceanai.data.pack_aiready --verify-only
```

Do not set `OCEANAI_RAW` there. Loaders read only the pack.

Python:

```python
from oceanai.data.pack_aiready import verify_pack
from oceanai.data.assets import load_training_assets
from oceanai.data.dataset import pair_to_tensors

verify_pack()
assets = load_training_assets()
batch = pair_to_tensors("0055-01", assets["mesh"], assets["mask"])
```

Writeback (needs `netCDF4` + a file under `templates/`):

```python
from oceanai.io.write_restart import write_deep_ts
from oceanai.paths import processed_dirs

t = processed_dirs()["templates"] / "v3.GMPAS-NYF_QU240.mpaso.rst.0055-01-01_00000.nc"
```

---

## Transfer options

```bash
# tarball
scp data/aiready/OceanAISpinup-QU240-aiready-v1.0.0.tar.gz USER@OTHER:/path/

# or rsync the tree
rsync -aP data/aiready/QU240/ USER@OTHER:/path/QU240/
```

On OLCF, Globus is usually more reliable than `scp` for >100 MB. Checksums: `sha256sum -c QU240/SHA256SUMS` (does not hash `manifest.json` / `SHA256SUMS` themselves).

---

## Rebuild vs train

| Task | Needs raw `OCEANAI_RAW` | Needs pack `OCEANAI_PROCESSED` |
|---|---|---|
| Re-extract pairs / DATM / graph | yes | working dir |
| Train residual GNN | no | yes |
| Persistence / scalers / pair tensors | no | yes |
| Write `*.ml.nc` restart | no (needs template nc) | yes |
| MPAS-Analysis / history OHC vs AM | yes (history files) | optional |

History monthly files stay on Frontier. Persistence OHC in the pack is computed from restart T/S/h in the pair npz (`ρ₀=1026`, `cₚ=3996`, T in Kelvin inside `ohc_from_state`).
