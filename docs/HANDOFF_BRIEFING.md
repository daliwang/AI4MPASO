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

GitHub: `daliwang/AI4MPASO` · branch **`handoff/prototype-e2e`**

| In git | Not in git |
|---|---|
| `oceanai/` code + tutorials | 19 GB raw Kang dump |
| Headers / namelists | `data/processed/` tensors |
| **X vs ML vs Y snapshot** | 57 MB `*.ml.nc` files |
| This briefing | Checkpoints |

`main` still has old notes and slide binaries. Use **this branch** to take over.

---

# Pilot workflow

Case `v3.GMPAS-NYF_QU240` on Kang’s Frontier dump. One command:

`python -m oceanai.run_prototype --stage all`

| Stage | What happens |
|---|---|
| **prepare** | 60 pairs, deep mask k=46…60, cell graph, monthly NYF, scalers |
| **qc** | Restart OHC vs history AM (sanity, ~10% cut mismatch OK) |
| **baseline** | Persistence: predict Y = X |
| **truth-writeback** | Put Y deep T/S into X template — proves the writer |
| **train** | Residual GraphSAGE, 48 train graphs, early-stop on holdout T |
| **infer** | Write `rst.0055-01-01.ml.nc` |
| **snapshot** | `python -m oceanai.qc.snapshot` → X vs ML vs Y |

Off Frontier: copy the **113 MB** AI-ready tar, not the 19 GB dump.

---

# Model setup (prototype)

| Item | Choice |
|---|---|
| Mesh | QU240, 7153 cells, graph from `cellsOnCell` (41 018 directed edges) |
| Deep mask | `refBottomDepth` > 2000 m → **k = 46…60** (15 levels) |
| Net | Cell-only residual GraphSAGE, **6 layers**, hidden **64** |
| Node input | 15 T + 15 S + 7 static (lat/lon/depth/month) + 10 monthly NYF = **47** |
| Target | Residual **ΔT, ΔS** on 15 deep levels (z-scored; add back to X) |
| Loss | Huber, weights `areaCell × layerThickness`, train-only scalers |
| Train / holdout | 48 pairs (51–54→601–604) / 12 pairs (55→605) |
| Hardware | Login-node **CPU** for the published demo |

NYF cycles and `mpaso_in` is one case: \(F\) and \(\theta\) are encoded but not identifiable.

---

# Predicted vs copied variables

Restart names (not history aliases).

| Field | Shape | v1 |
|---|---|---|
| `temperature` k=46…60 | nCells × 15 | **Predict** ΔT, add to X |
| `salinity` k=46…60 | nCells × 15 | **Predict** ΔS, add to X |
| `temperature` / `salinity` k=1…45 | shallow | Copy X |
| `layerThickness` | nCells × 60 | Copy X |
| `normalVelocity` | nEdges × 60 | Copy X |
| Barotropic auxiliaries, mesh, `xtime` | — | Copy X |

No `ssh` in the restart — do not invent it. Do not write history `activeTracers_*`.

---

# Comparison table (holdout January)

**0055-01** (X) vs **ML restart** vs **0605-01** (Y). Deep, area×thickness weighted.

| Metric | X (persist) | **ML** | Y (truth) |
|---|---|---|---|
| Mean deep T (°C) | 1.45 | **0.10** | 0.075 |
| Deep T RMSE vs Y (°C) | 1.43 | **0.39** | — |
| Deep T bias this−Y (°C) | +1.37 | **+0.03** | — |
| Mean deep S | 34.736 | 34.726 | 34.714 |
| Deep S RMSE vs Y | 0.073 | 0.069 | — |
| OHC 2000 m–bot rel. err. vs Y | 0.43% | **0.065%** | — |
| Shallow T/S, h, velocity vs X | — | **0 (copy)** | — |

Temperature skill is large-scale cooling. Salinity 550-yr change is small — do not over-claim S.

---

# Maps — column-mean deep T

Same color scale. Late ocean is colder; ML follows Y, not X.

`prototype/snapshots/0055-01/map_T_{X,ML,Y,ML_minus_Y}.svg`

Per-level means: X−Y stays ~1.2–1.6 °C; ML−Y is a few hundredths.

---

# Maps — column-mean deep S

Same layout as T. Signal is weak (global mean X 34.74 → Y 34.71).

`prototype/snapshots/0055-01/map_S_{X,ML,Y,ML_minus_Y}.svg`

RMSE vs Y: persistence 0.073 → ML 0.069. Residual maps are small compared with T.

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
python -m oceanai.qc.snapshot
# Other cluster:
export OCEANAI_PROCESSED=/path/to/QU240
python -m oceanai.data.pack_aiready --verify-only
```

Then `tutorials/00-concepts.md` and `prototype/snapshots/0055-01/compare.md`.
