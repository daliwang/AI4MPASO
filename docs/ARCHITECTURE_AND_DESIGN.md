# OceanAISpinup — Architecture, Design, and Pilot Results

**Audience:** team presentations alongside [`docs/handoff_briefing.html`](docs/handoff_briefing.html)  
**Branch:** `handoff/prototype-e2e`  
**Case:** `v3.GMPAS-NYF_QU240` (E3SM / MPAS-Ocean)  
**Date:** 2026-09-10 (metrics from the published CPU pilot)

This document is the **architecture narrative** for the AI effort: what we learn, why the design looks the way it does, how GraphCast and LandSim relate, how data are prepared, which restart fields are predicted, and what the holdout numbers show (including per-layer temperature).

---

## 1. Problem statement

Ocean spinup to a near-equilibrium restart is expensive. LandSim already showed that an AI model can map **early spinup state → near-equilibrium restart fields** for ELM. For MPAS-Ocean the same *job* exists, but the state lives on an **unstructured C-grid**, so spatial coupling cannot be ignored.

**OceanAISpinup v1 (pilot)** learns a **restart operator** on one coarse mesh:

\[
\hat{x}_{t+\Delta}
=
x_{t}
+
f_\phi\!\left(x_{t},\, F_{\mathrm{NYF}},\, G\right)
\quad\text{on deep levels } k = 46\ldots 60
\]

| Symbol | Meaning in the pilot |
|---|---|
| \(x_t\) | Early restart (**X**), years 51–55 |
| \(x_{t+\Delta}\) | Late restart (**Y**), years 601–605 (Δ = **550 yr**, same calendar month) |
| \(F_{\mathrm{NYF}}\) | CORE2 Normal Year Forcing (monthly, remapped to ocean cells) |
| \(G\) | QU240 cell dual graph from `cellsOnCell` |
| \(f_\phi\) | Residual GraphSAGE (cell-only) |

**Deliverable:** a **legal MPAS-Ocean restart** NetCDF: copy the early file, overwrite only deep `temperature` and `salinity`, keep thickness, velocity, mesh, and `xtime`.

This is **not** a weather forecast, **not** GenCast, and **not** a full-column ocean emulator.

---

## 2. Design principles

1. **Restart contract first.** Any prediction must land in a file MPAS can open. Writeback is copy-template overwrite, proven with a truth-Y dry run before trusting the model.
2. **Native unstructured mesh.** Ocean fields stay on MPAS cells. Do not interpolate T/S to lat–lon for a ViT/UNet and interpolate back.
3. **Deep ocean only in v1.** Alice/Hyun OHC bands show the 2000 m–bottom layer is the slow spinup signal. Levels with `refBottomDepth > 2000 m` → **k = 46…60** (15 levels).
4. **Residual learning.** Predict \(\Delta T, \Delta S\) and add to X. Persistence (\(\hat Y = X\)) is the baseline every model must beat.
5. **Area × thickness weighted loss.** Use `areaCell` and layer thickness so large deep cells dominate RMSE/OHC consistently with ocean integrals.
6. **Deterministic GNN before diffusion.** With 48 train pairs on one NYF case, a GenCast-style generative model is the wrong first objective (see `OceanAISpinup_Diffusion_Evaluation.md`).
7. **Encode atmosphere and namelist, do not over-claim causality.** NYF cycles and `mpaso_in` is fixed for this case — \(F\) and \(\theta\) do not vary across samples.
8. **Ship the workflow.** The pilot’s value is the end-to-end path (pairs → graph → train → restart → X/ML/Y snapshot), not a production GNN.

---

## 3. Relationship to GraphCast and LandSim

OceanAISpinup is a **hybrid of two parents**. It does **not** import either codebase; it reuses their *ideas*.

```
                 ┌─────────────────────┐
                 │      LandSim        │
                 │  early → eq map     │
                 │  multi-source data  │
                 │  restart overwrite  │
                 └──────────┬──────────┘
                            │  workflow spine
                            ▼
                 ┌─────────────────────┐
                 │   OceanAISpinup     │
                 │  MPAS cell GraphSAGE│
                 │  deep T/S residual  │
                 │  copy-template rst  │
                 └──────────▲──────────┘
                            │  mesh operator
                 ┌──────────┴──────────┐
                 │      GraphCast      │
                 │  residual GNN       │
                 │  message passing    │
                 │  geometric graph    │
                 └─────────────────────┘
```

### 3.1 What we take from LandSim

| LandSim pattern | OceanAISpinup analogue |
|---|---|
| Early AD-spinup (**X**) vs final-spinup (**Y**) pairs | Year ~50 vs ~600 month-aligned restart pairs |
| Modular dataGEN / IO lists | `oceanai.data` pair index, extract, DATM encoder, scalers |
| Per-variable normalization | Train-only z-score on T/S and ΔT/ΔS |
| Multi-task weighted loss | Huber on ΔT‖ΔS with area×thickness weights |
| `ai_predictions_to_restart` copy-template overwrite | `oceanai.io.write_restart.write_deep_ts` |

**What we do *not* copy:** LandSim’s **per-gridcell IID Transformer**. Land cells are treated as independent samples; deep ocean equilibration is **nonlocal**. A cell-independent model is the wrong inductive bias for MPAS-Ocean.

### 3.2 What we take from GraphCast

| GraphCast pattern | OceanAISpinup analogue |
|---|---|
| Message passing on a sphere graph | GraphSAGE on MPAS `cellsOnCell` dual |
| Predict **normalized residual** of the next state | \(\hat T = T_X + \mathrm{unzscore}(\widehat{\Delta T})\) (same for S) |
| Vertical levels as **channels** | 15 deep levels stacked in the feature/target vectors |
| Area-aware loss (lat weights on ERA5) | `areaCell` × `layerThickness` on the deep mask |

**What we do *not* copy:**

| GraphCast / GenCast piece | Why it does not transfer as-is |
|---|---|
| Separate icosahedral “dynamics mesh” | MPAS **is** already the unstructured mesh |
| Grid↔mesh bipartite encode/decode | Physics already lives on cells; DATM is remapped offline |
| 6-hour weather rollout | We map a **550-year** spinup jump |
| GenCast diffusion / ensembles | Need many independent pairs and proven multi-modality first |
| Lat–lon as the loss grid | Loss and writeback stay on `nCells` / deep levels |

**One-line lineage:** *LandSim workflow + GraphCast residual mesh GNN, specialized to MPAS deep-ocean restart writeback.*

---

## 4. Architecture (as implemented)

### 4.1 System diagram

```
Kang Dali/  (raw restarts + remapped NYF)
        │
        ▼
 prepare ──► pair index (60) · deep_mask · mesh_graph · datm_monthly · scalers
        │
        ▼
 baseline ─► persistence Ŷ = X
        │
        ▼
 train ────► ResidualGNN (GraphSAGE × 6, hidden 64)
        │         input  x: (7153, 47)
        │         target y: (7153, 30)   # ΔT ‖ ΔS
        │
        ▼
 infer ────► write_deep_ts(template=X) → *.ml.nc
        │
        ▼
 snapshot ─► X vs ML vs Y tables + maps
```

Package: `oceanai/` (`run_prototype.py` stages the pipeline). Dependencies: `numpy`, `torch`, `netCDF4` only — **no** PyG, **no** JAX GraphCast import.

### 4.2 Graph

| Item | Value |
|---|---|
| Nodes | 7153 cells |
| Edges | ~41 018 directed edges from `cellsOnCell` (max degree 6) |
| Node types (v1) | **Homogeneous cells only** (edge `normalVelocity` deferred) |
| Batching | One full mesh graph per pair (not mini-batches of cells) |

### 4.3 Network (`ResidualGNN`)

```
node features (N, 47)
  → Linear → ReLU → LayerNorm          # encoder
  → 6 × GraphSAGELayer                 # mean-aggregate neighbors, concat, Linear, ReLU, LN, + residual
  → Linear → (N, 30)                   # 15 ΔT + 15 ΔS (z-scored)
```

Defaults used for published metrics: **hidden = 64**, **6 layers**, Adam `lr = 1e-3`, ~15–25 epochs on CPU, checkpoint on best holdout deep-T RMSE.

### 4.4 Node features (47 channels)

| Block | Width | Content |
|---|---|---|
| Early deep T | 15 | z-scored `temperature` at k=46…60 |
| Early deep S | 15 | z-scored `salinity` |
| Static / season | 7 | sin/cos(lat), sin/cos(lon), log depth, month sin/cos |
| DATM month | 10 | `u_10,v_10,t_10,slp_,q_10,dn10,prc,lwdn,swdn,swup` for that month |

Physics namelist (`mpaso_variables`) is stored as run metadata; **not** FiLM-conditioned in the shipped net.

### 4.5 Loss

Area × X-`layerThickness` weighted **Huber** on the concatenated normalized (ΔT, ΔS), zeroed where the deep mask is invalid (~63 228 valid deep points).

---

## 5. Data preparation

### 5.1 Source data (Kang / Frontier)

| Stream | Role |
|---|---|
| Restarts years **051–055** | Early state **X** |
| Restarts years **601–605** | Late state **Y** |
| DATM CORE2 NYF (remapped to oQU240) | Monthly atmosphere on cells |
| `mpaso_in` / `mpaso_variables` | Static physics regime (one case) |
| History OHC AM | Validation only (not writeback) |

Raw dump (~19 GB) stays on Lustre. Training off Frontier uses the **~113 MB AI-ready pack** (`oceanai.data.pack_aiready`).

### 5.2 Pair factory

| Rule | Value |
|---|---|
| Alignment | Same calendar month, Δ = 550 yr |
| Count | **60** pairs (`0051-01`→`0601-01`, …, `0055-12`→`0605-12`) |
| Train | Years 51–54 → 601–604 (**48**) |
| Holdout | Year 55 → 605 (**12**) |
| Join | Identity on cell index (same mesh) |

Each `pairs/YYYY-MM.npz` holds `(7153, 15)` arrays: `t_x,s_x,h_x,t_y,s_y,h_y,valid`.

### 5.3 Deep mask

```
refBottomDepth[k] > 2000  and  k ≤ maxLevelCell[i]  and  bottomDepth[i] > 2000
```

→ **k = 46…60** (≈ 2075–5500 m), `N_DEEP = 15`.

### 5.4 Atmosphere encoding

Prefer **DATM state** (Tier-1 winds/T/SLP + precip + radiation), not coupler fluxes from ocean history (those depend on SST/ice). NYF **cycles**, so \(F\) is the same annual cycle every year — useful as context, not as a causal contrast in this dataset.

---

## 6. Predicted variables (v1 restart contract)

### 6.1 Written by the model

| NetCDF name | Dimensions (written) | Levels | Units | How |
|---|---|---|---|---|
| `temperature` | `nCells ×` deep | **k = 46…60** | °C | \(T_X + \widehat{\Delta T}\) |
| `salinity` | `nCells ×` deep | **k = 46…60** | 1e-3 | \(S_X + \widehat{\Delta S}\) |

**Two prognostic fields**, **fifteen levels each** → **30 output channels** per cell. Only valid deep points are overwritten; inactive cells/levels keep the template.

### 6.2 Copied unchanged from the early restart (X)

| Field | Why frozen in v1 |
|---|---|
| `temperature` / `salinity` for **k = 1…45** | Upper ocean not in the deep-spinup target |
| `layerThickness` | Mass/volume from template; OHC uses X thickness |
| `normalVelocity`, `normalBarotropicVelocity` | Edge C-grid; deferred |
| Mesh connectivity, `xtime` | Keep early date on the AI restart |

There is **no standalone `ssh`** in this restart schema; do not invent one.

### 6.3 Conditioning / metadata (not restart prognostics)

| Input class | Examples | Role |
|---|---|---|
| DATM | `u_10,v_10,t_10,slp_,prc,…` | Node features (monthly) |
| Geometry | `areaCell`, lat/lon, `bottomDepth` | Graph + static features |
| Namelist | GM/Redi κ, KPP, viscosity, … | Run metadata (constant here) |

### 6.4 Validation-only (history)

| Field | Use |
|---|---|
| `timeMonthly_avg_oceanHeatContent2000mToBot` | Compare to restart-derived deep OHC |
| Maps / RMSE tables | Holdout interpretation |

---

## 7. Pilot results (holdout January 0055-01 → 0605-01)

Metrics are **area × layer-thickness weighted** on the deep mask. Full snapshot: [`prototype/snapshots/0055-01/compare.md`](prototype/snapshots/0055-01/compare.md).

### 7.1 Headline comparison

| Metric | X (persistence) | **ML** | Y (truth) |
|---|---:|---:|---:|
| Mean deep T (°C) | 1.448 | **0.105** | 0.075 |
| Deep T RMSE vs Y (°C) | 1.433 | **0.392** | — |
| Deep T bias (this − Y) (°C) | +1.373 | **+0.029** | — |
| Mean deep S | 34.736 | 34.726 | 34.714 |
| Deep S RMSE vs Y | 0.073 | 0.069 | — |
| Deep S bias (this − Y) | +0.022 | +0.012 | — |
| OHC 2000 m–bot (J) | 8.180×10²⁶ | 8.140×10²⁶ | 8.145×10²⁶ |
| OHC rel. error vs Y | 0.43% | **0.065%** | — |
| Shallow T/S, thickness, velocity vs X | — | **0 (copy)** | — |

**Reading:** temperature skill is mostly a **large-scale cooling** toward Y. Salinity barely moves over 550 years — do **not** over-claim S skill. The writeback **contract** (unchanged non-deep fields) holds.

### 7.2 Mean deep temperature by level (°C)

| k | z_ref (m) | X | ML | Y | **ML − Y** | **X − Y** |
|---|---:|---:|---:|---:|---:|---:|
| 46 | 2075 | 2.229 | 1.017 | 0.983 | +0.034 | +1.246 |
| 47 | 2298 | 2.041 | 0.811 | 0.792 | +0.019 | +1.249 |
| 48 | 2530 | 1.865 | 0.619 | 0.605 | +0.014 | +1.260 |
| 49 | 2768 | 1.702 | 0.419 | 0.412 | +0.007 | +1.290 |
| 50 | 3011 | 1.559 | 0.245 | 0.218 | +0.027 | +1.341 |
| 51 | 3256 | 1.434 | 0.081 | 0.035 | +0.046 | +1.399 |
| 52 | 3503 | 1.318 | −0.077 | −0.131 | +0.054 | +1.449 |
| 53 | 3752 | 1.200 | −0.219 | −0.281 | +0.062 | +1.481 |
| 54 | 4001 | 1.071 | −0.371 | −0.412 | +0.041 | +1.483 |
| 55 | 4251 | 0.930 | −0.498 | −0.526 | +0.028 | +1.456 |
| 56 | 4500 | 0.818 | −0.602 | −0.620 | +0.017 | +1.437 |
| 57 | 4750 | 0.754 | −0.677 | −0.694 | +0.017 | +1.448 |
| 58 | 5000 | 0.727 | −0.726 | −0.739 | +0.012 | +1.466 |
| 59 | 5250 | 0.740 | −0.760 | −0.758 | −0.001 | +1.498 |
| 60 | 5500 | 0.800 | −0.758 | −0.764 | +0.006 | +1.564 |

At every deep level, persistence (X−Y) stays ~1.2–1.6 °C too warm; ML−Y is typically a few hundredths of a degree.

### 7.3 Spatial maps (slides)

| Field | Files |
|---|---|
| Column-mean deep **T** | `prototype/snapshots/0055-01/map_T_{X,Y,ML,ML_minus_Y}.svg` |
| Column-mean deep **S** | `prototype/snapshots/0055-01/map_S_{X,Y,ML,ML_minus_Y}.svg` (regenerate with `python -m oceanai.qc.snapshot` if missing) |

---

## 8. Honest limitations (say these in the talk)

1. **One mesh, one NYF case, 48 train graphs** — easy to overfit; holdout is the next year of the same seasonal cycle.
2. **Salinity signal is weak** — RMSE improvement is small.
3. **No edge velocity, no upper ocean, no SSH** in v1.
4. **No N-day MPAS forward** in the pilot packet (Hyun after handoff).
5. **Do not** train GenCast/diffusion on these 60 pairs; **do not** lat–lon interpolate ocean state for a vision backbone.

---

## 9. How to use this with the slides

| Slide deck | This document |
|---|---|
| [`docs/handoff_briefing.html`](docs/handoff_briefing.html) | Live short talk (workflow, model card, tables, maps) |
| **This file** | Handout / speaker notes: lineage, IO contract, per-level table, caveats |
| [`tutorials/00-concepts.md`](tutorials/00-concepts.md) | Vocabulary for implementers |
| [`OceanAISpinup_Diffusion_Evaluation.md`](OceanAISpinup_Diffusion_Evaluation.md) | Why not GenCast-first |
| [`OceanAISpinup_Development_Plan.md`](OceanAISpinup_Development_Plan.md) | Deeper GraphCast/LandSim code review |

**Suggested talk arc:** problem → LandSim/GraphCast lineage → design principles → data pairs & deep mask → predicted vs copied variables → architecture box → comparison table → per-level T → maps → limitations / next owners.

---

## 10. References in-repo

- Code: `oceanai/models/residual_gnn.py`, `oceanai/io/write_restart.py`, `oceanai/run_prototype.py`
- Snapshot numbers: `prototype/snapshots/0055-01/compare.md`
- Variable selection: `data/docs/RESTART_DEEP_OCEAN_STATE.md`, `DATM_FORCING_VARIABLES.md`, `MPASO_PHYSICS_CONFIG_INPUTS.md`
- Run card: `prototype/README.md`
