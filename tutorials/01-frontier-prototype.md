# 01 — Run the prototype on Frontier

**Time:** ~20 minutes for `--smoke`, longer for all 60 pairs + training.  
**You need:** Frontier account, access to Kang’s `Dali/` tree, this repo.  
**Success:** `data/processed/QU240/restarts_ml/rst.0055-01-01.ml.nc` exists and `ncdump` shows `xtime = 0055-01-01_00:00:00`.

If you only want tensors on another cluster, skip to [02](02-aiready-pack.md).

## 0. Mental model

`run_prototype` is a staged pipeline:

`prepare` → `qc` → `baseline` → `truth-writeback` → `train` → `infer`

`--smoke` uses the five January pairs only (`0051-01` … `0055-01`). Use that the first time.

## 1. Environment (once)

Login-node `/usr/bin/python3` cannot import `netCDF4`. Always:

```bash
cd /lustre/orion/lrn105/proj-shared/wangd/AI4MPAS   # or your clone
git checkout handoff/prototype-e2e
module load cray-python/3.11.7
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH="$PWD"
```

Later sessions: `module load cray-python/3.11.7 && source .venv/bin/activate && export PYTHONPATH="$PWD"`.

Optional path overrides (defaults already point at Kang + this project):

```bash
# export OCEANAI_RAW=/lustre/orion/cli115/world-shared/hgkang/data4others/Dali
# export OCEANAI_PROCESSED=/lustre/orion/lrn105/proj-shared/wangd/AI4MPAS/data/processed/QU240
```

Sanity check that raw restarts are visible:

```bash
ls "$OCEANAI_RAW/QU240_Restart_Hist_051-055/restart" | head
# expect v3.GMPAS-NYF_QU240.mpaso.rst.0051-01-01_00000.nc
```

If `OCEANAI_RAW` is unset, the default Dali path is used (`oceanai/paths.py`).

## 2. Smoke run

```bash
python -m oceanai.run_prototype --stage all --smoke
```

What should print (names, not exact numbers):

- pair index 60 rows, then “smoke: 5 January pairs”
- deep mask ~7153 cells × 15 levels, ~63228 valid
- graph ~41018 directed edges
- persistence RMSE T on `0051-01` ≈ **1.44 °C**
- truth-Y writeback relative OHC error ≪ 1
- a few training epochs, then an ML restart path

Re-runs skip existing `pairs/*.npz`, mask, graph, DATM, and scalers.

## 3. Full 48 / 12 split (when smoke looks right)

```bash
python -m oceanai.run_prototype --stage all
```

Stages you can run alone: `prepare`, `qc`, `baseline`, `truth-writeback`, `train`, `infer`.  
`prepare` always runs first (it is cheap if artifacts exist).

## 4. Where files land

All under `data/processed/QU240/` (gitignored):

```
pairs/index.json              60 rows: pair_id, years, month, split
pairs/0051-01.npz             deep T/S/h for X and Y
deep_mask.npz  mesh_graph.npz datm_monthly.npz
scalers/scalers.json          fit on train only
baselines/persistence.json
baselines/ohc_qc.json
baselines/truthY_writeback.json
baselines/model_holdout.json
checkpoints/track_a_proto.pt
restarts_ml/rst.0051-01-01.truthY.nc
restarts_ml/rst.0055-01-01.ml.nc
```

Peek at the index:

```bash
python - <<'PY'
from oceanai.data.pair_index import load_pair_index
rows = load_pair_index()
print(len(rows), "pairs")
print(rows[0])
print("holdout", [r["pair_id"] for r in rows if r["split"]=="holdout"][:3], "...")
PY
```

## 5. Confirm the ML restart

```bash
ncdump=/opt/cray/pe/netcdf/4.9.0.7/bin/ncdump
$ncdump -v xtime data/processed/QU240/restarts_ml/rst.0055-01-01.ml.nc | tail
# xtime = "0055-01-01_00:00:00"   ← template (X) time, by design
```

Published smoke/full metrics: [`prototype/README.md`](../prototype/README.md).

## Common failures

| Symptom | Likely cause |
|---|---|
| `ModuleNotFoundError: netCDF4` | Forgot `cray-python` venv; used `/usr/bin/python3` |
| `FileNotFoundError` on `rst.0051-01` | No access to Kang’s `Dali/` or `OCEANAI_RAW` wrong |
| `expected 15 deep levels` | Wrong mesh / not QU240 |
| Training looks done but no `*.ml.nc` | `infer` did not run; use `--stage all` or `--stage infer` |
| Holdout RMSE T ≈ 1.43 °C after train | Model did not beat persistence — still a valid workflow; check `model_holdout.json` |

## Next

- [03 — Restart writeback](03-restart-writeback.md) — what that `*.ml.nc` is allowed to change  
- [02 — AI-ready pack](02-aiready-pack.md) — copy tensors off Frontier  
- [04 — Metrics](04-metrics-and-ohc.md) — how 1.43 °C and OHC were computed  
