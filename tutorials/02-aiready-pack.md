# 02 — AI-ready pack (train off Frontier)

**Time:** ~10 minutes if the pack already exists; ~15+ minutes to rebuild from raw.  
**You need:** this git repo everywhere; the tarball **or** Frontier + Kang dump to build it.  
**Success:** `python -m oceanai.data.pack_aiready --verify-only` prints `verify ok: 60 pairs` **without** `OCEANAI_RAW`.

Raw dump ≈ **19 GB**. Pack ≈ **113 MB** (`OceanAISpinup-QU240-aiready-v1.0.0.tar.gz`). Copy the pack.

Full card: [`data/docs/AIREADY_DATASET.md`](../data/docs/AIREADY_DATASET.md).

## What is inside (and what is not)

**In the pack:** 60 pair `npz` files, mesh graph, deep mask, monthly NYF on 7153 cells, train scalers, persistence JSON, optional X restart template(s). Index has **no Lustre paths**.

**Not in the pack:** 6-hourly DATM, monthly history, OHC AM series, late (Y) restart files, MPAS executable.

Training uses **numpy + torch** only. `netCDF4` is required only to *write* a restart from `templates/`.

## A. Build on Frontier (once)

```bash
cd /lustre/orion/lrn105/proj-shared/wangd/AI4MPAS
source .venv/bin/activate
export PYTHONPATH="$PWD"

python -m oceanai.data.pack_aiready --templates jan1-holdout
```

Writes:

- working extract: `data/processed/QU240/` (still used by `run_prototype`)
- portable tree: `data/aiready/QU240/`
- tarball: `data/aiready/OceanAISpinup-QU240-aiready-v1.0.0.tar.gz`

| Flag | When to use |
|---|---|
| `--templates none` | Smallest; training only, no writeback on dest |
| `--templates jan1-holdout` | Default: one X file `rst.0055-01-01` (~57 MB extra) |
| `--templates holdout` | All 12 holdout X restarts |
| `--skip-build` | Re-export from existing `processed/` |
| `--jan1-only` | 5 pairs (debug pack, not the scientific split) |

Already built on this project Lustre (not in git):

`/lustre/orion/lrn105/proj-shared/wangd/AI4MPAS/data/aiready/OceanAISpinup-QU240-aiready-v1.0.0.tar.gz`

Transfer (Globus preferred on OLCF):

```bash
scp data/aiready/OceanAISpinup-QU240-aiready-v1.0.0.tar.gz USER@OTHER:/path/
# or
rsync -aP data/aiready/QU240/ USER@OTHER:/path/QU240/
```

## B. Unpack on the other cluster

```bash
tar -xzf OceanAISpinup-QU240-aiready-v1.0.0.tar.gz
# creates ./QU240/

git clone git@github.com:daliwang/AI4MPAS.git   # or copy the tree
cd AI4MPAS
git checkout handoff/prototype-e2e
python3 -m venv .venv && source .venv/bin/activate
pip install numpy torch          # add netCDF4 if you will write restarts
export PYTHONPATH="$PWD"
export OCEANAI_PROCESSED=/absolute/path/to/QU240   # unpacked pack
# do NOT set OCEANAI_RAW
```

`OCEANAI_PROCESSED` must be set **before** you start Python (`oceanai.paths` reads it at import).

Verify (touches only the pack):

```bash
python -m oceanai.data.pack_aiready --verify-only
# verify ok: 60 pairs, t_x (7153, 15), edges 41018
```

Optional checksums (does not hash `manifest.json` / `SHA256SUMS` themselves):

```bash
cd /absolute/path/to/QU240 && sha256sum -c SHA256SUMS
```

## C. Load one sample (the “am I wired?” test)

```bash
python - <<'PY'
from oceanai.data.pack_aiready import verify_pack
from oceanai.data.pair_index import load_pair_index
from oceanai.data.extract import load_pair
from oceanai.data.assets import load_training_assets
from oceanai.data.dataset import pair_to_tensors

verify_pack()
idx = load_pair_index()
print("n", len(idx), "fields", list(idx[0]))   # no path_x / path_y
p = load_pair("0055-01")
print("t_x", p["t_x"].shape, "n_valid", int(p["valid"].sum()))
a = load_training_assets()
b = pair_to_tensors("0055-01", a["mesh"], a["mask"])
print("node x", tuple(b["x"].shape), "target y", tuple(b["y"].shape))
# x: (7153, 47) = 15 T + 15 S + 7 static + 10 DATM
# y: (7153, 30) = 15 ΔT + 15 ΔS  (z-scored)
PY
```

If that runs, you can train `ResidualGNN` on this machine. The Frontier driver `run_prototype --stage all` still wants raw restarts for QC / truth-Y / official Y OHC; on the dest cluster use tensors + (optional) `templates/` for writeback — [03](03-restart-writeback.md).

## Common failures

| Symptom | Fix |
|---|---|
| `No pair index at ...` | `OCEANAI_PROCESSED` not pointed at unpacked `QU240/` |
| Loader still looks under `/lustre/orion/...` | Env not set in **this** shell; restart Python |
| `netCDF4` import error during **verify/train** | Should not happen; you imported writeback/extract-from-nc by mistake |
| Index contains `/lustre/...` | Old working `processed/` index; use `data/aiready/QU240/pairs/index.json` |

## Next

- [03](03-restart-writeback.md) if you brought a template and want `*.ml.nc`  
- [04](04-metrics-and-ohc.md) to reproduce persistence from tensors alone  
