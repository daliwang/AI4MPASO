---
marp: true
paginate: true
title: OceanAISpinup handoff
---

# OceanAISpinup — handoff

**Branch:** `handoff/prototype-e2e`  
**Date:** 10 Sep 2026

Early QU240 restart (year ~50) → deep T/S at year ~600 → **legal MPAS restart**.

Not a weather model. Not GenCast.

---

# What this branch is

GitHub: `daliwang/AI4MPAS` · branch **`handoff/prototype-e2e`**

| In git | Not in git |
|---|---|
| `oceanai/` code + tutorials | 19 GB raw Kang dump |
| Headers / namelists | `data/processed/` tensors |
| **X vs ML vs Y snapshot** | 57 MB `*.ml.nc` files |
| This briefing | Checkpoints |

`main` still has old notes and slide binaries. Use **this branch** to take over.

---

# One-sentence contract

Copy the **year-55 restart**. Overwrite **only** deep `temperature` and `salinity` (k=46…60). Keep thickness, velocity, mesh, `xtime`.

\[
\hat{x}_{600} = x_{50} + f_\phi(x_{50}, F_{\mathrm{NYF}}, G)
\quad \text{on deep levels}
\]

60 month-aligned pairs, Δ = 550 yr. Train 48 / hold out 12 (year 55→605).

---

# Workflow

```
Kang Dali/  raw restarts + remapped NYF
    │
    ├─ 1. pair index, deep mask, mesh graph, monthly DATM
    ├─ 2. extract 60 pair npz
    ├─ 3. persistence baseline
    ├─ 4. tiny residual GNN (optional skill)
    ├─ 5. write_restart → *.ml.nc
    └─ 6. snapshot X vs ML vs Y
```

Frontier: `python -m oceanai.run_prototype --stage all`  
Other cluster: copy the **113 MB** AI-ready tar, not the 19 GB dump.

---

# Tutorials (`tutorials/`)

| # | Start here if you… |
|---|---|
| **00** | Need the vocabulary (X, Y, deep, persistence) |
| **01** | Are on Frontier and want a smoke run |
| **02** | Are taking tensors to another GPU cluster |
| **03** | Touch restart writeback |
| **04** | Own OHC / RMSE |
| **05** | Will run N-day MPAS (recipe; not automated) |
| **06** | Want the X / ML / Y snapshot |

Index: `tutorials/README.md`

---

# Snapshot — holdout January

Files compared (not committed as NetCDF):

| Role | Restart | `xtime` |
|---|---|---|
| **X** early | `rst.0055-01-01` | 0055-01-01 |
| **ML** AI | `rst.0055-01-01.ml.nc` | 0055-01-01 (template) |
| **Y** truth | `rst.0605-01-01` | 0605-01-01 |

**Contract:** max \|ML−X\| = 0 on shallow T/S, thickness, `normalVelocity`.

Report in git: `prototype/snapshots/0055-01/compare.md`

---

# Deep T vs ground truth

Area × thickness weighted, k=46…60.

| | Mean T | RMSE vs Y | this − Y |
|---|---|---|---|
| X (persistence) | 1.45 °C | **1.43 °C** | +1.37 °C too warm |
| **ML** | 0.10 °C | **0.39 °C** | +0.03 °C |
| Y (sim) | 0.075 °C | — | — |

OHC 2000 m–bottom rel. err. vs Y: X **0.43%** → ML **0.065%**.

Salinity: little 550-yr signal (RMSE 0.073 → 0.069). Do not over-claim S.

---

# Maps (column-mean deep T)

Same color scale. Late ocean is colder; ML follows Y, not X.

`prototype/snapshots/0055-01/map_T_{X,ML,Y,ML_minus_Y}.svg`

Per-level means: X−Y stays ~1.2–1.6 °C; ML−Y is a few hundredths.

Regenerate: `python -m oceanai.qc.snapshot`

---

# After handoff

| Person | Owns |
|---|---|
| **Olawale** | Pair factory, scalers, training |
| **Alice** | OHC maps, holdout interpretation |
| **Hyun** | N-day forward from `*.ml.nc` |
| **Dali** | Advisor; restart contract |

**Do not:** train GenCast on 60 NYF pairs; interpolate to lat–lon; write history tracers into a restart.

---

# Monday morning

```bash
git checkout handoff/prototype-e2e
# Frontier:
python -m oceanai.run_prototype --stage all --smoke
# Other cluster:
export OCEANAI_PROCESSED=/path/to/QU240
python -m oceanai.data.pack_aiready --verify-only
```

Then read `tutorials/00-concepts.md` and open `prototype/snapshots/0055-01/compare.md`.
