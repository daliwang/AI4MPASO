# OceanAISpinup: Codebase Review and Development Plan

**Date:** 2026-07-30  
**Audience:** AI4MPAS / ImPACTS ocean spinup team (Dali, Alice, Hyun, Olawale)  
**Purpose:** Share findings from reviewing GraphCast and LandSim, and propose a concrete plan for an MPAS-Ocean early→equilibrium AI model that respects unstructured-mesh coupling.

**Related local notes**

- `background.txt` — team task split and sample data pointers (2026-06-22)
- `selected_variables.txt` — current namelist / physics-config list (regime conditioning; see §2.1)
- `MPAS_Ocean_ML_Init_Report.md` — earlier conceptual GraphCast + LandSim framing
- Sample data (NERSC): `/global/cfs/cdirs/m4259/hgkang/data_for_others/Dali_OceanSpinup_sample`
- MPAS-Analysis example: [GMPAS-NYF_QU240](https://portal.nersc.gov/project/e3sm/hgkang/ImPACTS/AI_spinup/v3.GMPAS-NYF_QU240/www/)

**Codebases reviewed**

| Codebase | Path | Role in this plan |
|----------|------|-------------------|
| GraphCast / GenCast | `/Users/7xw/Documents/Work/AI4MPASO/graphcast` (local copy; not tracked in this repo) | Typed mesh GNN / sparse transformer operators |
| LandSim | `/Users/7xw/Documents/Work/LandSim` | Early→equilibrium pairing, multi-stream fusion, restart writeback |
| MPAS-Ocean guide | `MPAS_Ocean_Users_Guide_E3SM_V3.0.0.pdf` | Restart/history schema authority |

---

## 1. Executive summary

**Goal.** Learn a map from **early / partial MPAS-Ocean spinup** (+ forcings, mesh, and configuration context) to a **near-equilibrium / restart-quality** ocean state, then inject predictions into an MPAS restart file—analogous to LandSim for ELM.

**Hard constraint.** Unlike LandSim (and unlike treating atmosphere on a lat–lon grid as independent cells), MPAS-Ocean state lives on an **unstructured C-grid**. Horizontal coupling through circulation, waves, and tracer advection means a **per-cell IID model is insufficient**.

**Recommended strategy.**

1. **Reuse LandSim’s workflow spine:** modular data generation of early (**X**) vs near-eq (**Y**) pairs, config-driven IO lists, per-variable normalization, multi-task weighted loss, and template-restart overwrite.
2. **Reuse GraphCast’s mesh operator stack:** `TypedGraph` + `DeepTypedGraphNet` encode–process–decode, geometric edge features, residual prediction, optional autoregressive / multi-time training.
3. **Replace** GraphCast’s lat–lon ↔ icosahedral bridges and LandSim’s cell-independent Transformer with a **native MPAS cell/edge(/vertex) graph processor** and **`areaCell`-weighted** losses.

**Immediate clarification.** `selected_variables.txt` currently lists **namelist physics/config knobs** (GM, KPP, bottom drag, EOS, remapping, etc.). Those should condition the model as a **simulation regime**, but they are **not** the prognostic restart fields the AI should predict. A separate prognostic IO list must be locked with Alice/Hyun against restart/history headers on the sample data machine.

---

## 2. Problem framing

### 2.1 What we are predicting

| Role | Content | Status |
|------|---------|--------|
| **Regime / config tokens** | Namelist-style settings in `selected_variables.txt` (viscosity, GM/Redi, KPP, drag, EOS, …) | Draft list exists |
| **Static mesh features** | `latCell`/`lonCell`, `areaCell`, bathymetry / bottom depth, Coriolis, land/ice masks, connectivity | From mesh / init files |
| **Early state (X)** | Short-spinup restart and/or history on the **same mesh** | Sample path available on NERSC |
| **Context (optional)** | Atmospheric/bulk forcings, restoring, external analyses | To be specified like LandSim forcing streams |
| **Target (Y)** | Near-equilibrium / long-spinup **restart prognostics** (T, S, thickness, SSH, velocities, …) | **Needs schema lock on data machine** |
| **Diagnostics (validation only)** | OHC and related indices from history (`h0`); MLD proxies; drift metrics | Alice/Hyun notes in `background.txt` |

### 2.2 Success criteria (proposed)

- Global / basin **RMSE and bias** vs reference long spinup on primary prognostics, with **`areaCell` (and vertical) weighting**.
- Stratification / static-stability sanity (no systematic unstable profiles).
- **Short forward test:** restart from ML state, integrate **N days** with the same namelist, compare drift to restart-from-full-spinup.
- Wallclock / human-iteration savings vs completing full ocean spinup for new cases.

---

## 3. LandSim review — what transfers

LandSim (v0.1, formerly AI4BGC) learns a **per-gridcell** map:

> early / AD-spinup land state + multi-source context → final-spinup / restart-quality CNP pools → write into ELM restart NetCDF.

### 3.1 Reuse almost directly

| Pattern | LandSim artifact | Ocean analogue |
|---------|------------------|----------------|
| Early→eq supervised pairs | `A_ds10_restart_x` + `A_r_list_y` in `LandSim_dataGEN` | Partial spinup restart vs long / near-eq restart on **same mesh** |
| Modular extract → assemble | `run_extraction.py` / `run_assembly.py` | Forcing, bathymetry, early IC, tracers as modules |
| Config-driven IO lists | `CNP_IO_*.txt`, `parse_cnp_io_list` | `Ocean_IO_*.txt` with stream groups |
| Per-variable scalers | `IndividualScalerManager` | Same for T/S/SSH/u/v/… |
| Multi-task weighted MSE | `ModelTrainer` | Heads per field family (3D tracers, 2D SSH, edge velocity) |
| Template restart overwrite | `ai_predictions_to_restart.py` | Copy MPAS restart; overwrite by `nCells` / `nEdges` index |
| Temporal forcing patches | `ForcingTemporalEncoder` | Atmospheric / flux / restoring time series |
| Phased regional models | Phase1/2/3 + masks | Basin / shelf / deep experts if needed |

Key paths (LandSim):

- `models/cnp_combined_model.py` — `ForcingTemporalEncoder`, `StaticVariableEncoder`, `CNPCombinedModel`
- `data/data_loader_individual.py`, `data/individual_scaler_manager.py`
- `training/trainer.py`
- `LandSim_dataGEN/` — pairing pipeline
- `scripts/ai_predictions_to_restart.py` — restart injection pattern

### 3.2 Must change for MPAS-Ocean

| LandSim assumption | Why it breaks for ocean | Required change |
|--------------------|-------------------------|-----------------|
| Gridcells are IID in the batch | Circulation / nonlocal equilibration | Neighbor message passing (GNN / mesh attention) |
| Transformer attends only over modality tokens within a cell | No horizontal operators | Mesh processor after (or instead of) mean-pool |
| Lat/lon are features only | Geometry is discrete connectivity | Build graph from `cellsOnCell` / edge incidence |
| PFT + soil column layout | Wrong state layout | `nCells × nVertLevels`, edge-centered velocities |
| Softplus / positivity on C/N/P pools | Different physics | EOS-aware / stratification / tracer constraints |
| Lat/lon KD-tree remap for pairing | Same-mesh training preferred | **Identity index join** when mesh matches |

**Bottom line for LandSim:** keep the **data and restart ops**; do **not** copy the cell-independent model as the ocean backbone.

---

## 4. GraphCast review — what transfers

GraphCast is an **encode–process–decode** model: physical fields live on a **lat–lon grid**, dynamics message-passing runs on an **icosahedral multi-mesh**, and loss/rollouts stay on the grid.

### 4.1 Architecture (implementation names)

| Component | Module | Role |
|-----------|--------|------|
| `TypedGraph` / `NodeSet` / `EdgeSet` | `typed_graph.py` | Heterogeneous node/edge sets |
| `DeepTypedGraphNet` | `deep_typed_graph_net.py` | Encode → multi-step InteractionNet → decode |
| Grid2Mesh GNN | `graphcast.py` | Bipartite: lat–lon → mesh (radius query) |
| Mesh GNN | `graphcast.py` | Homogeneous multi-mesh edges (`merge_meshes`, `faces_to_edges`) |
| Mesh2Grid GNN | `graphcast.py` | Bipartite: mesh triangle → grid points |
| Spatial features | `model_utils.py` | Relative geometry in local frames |
| Residual + norm | `normalization.py` | Predict normalized residual vs last input |
| Weighted MSE | `losses.py` | Latitude × level weights |
| Autoregressive train | `autoregressive.py` | Differentiable multi-step `hk.scan` |
| GenCast sparse attn | `sparse_transformer.py`, `transformer.py` | Optional mesh self-attention (banded / Splash) |

### 4.2 What transfers well to MPAS

1. **`TypedGraph` + typed message passing** — map MPAS primal/dual entities to node sets (`cells`, `edges`, `vertices`) and incidence relations to edge-set types.
2. **`DeepTypedGraphNet`** — encode–process–decode with per-type MLPs and residuals.
3. **Geometric edge features** — extend with `dcEdge`, `dvEdge`, cell area, angle, etc.
4. **Predictor / residual / AR wrappers** — training pattern is mesh-agnostic once tensors are redefined.
5. **Multi-scale idea** — GraphCast merged hierarchy ≈ build **METIS / agglomeration** coarse graphs on MPAS (do not reuse icosahedral `merge_meshes` on MPAS geometry).
6. **GenCast sparse transformer** — only if attention runs on **one** homogeneous graph (e.g. cell dual) after banded reordering.

### 4.3 What does **not** transfer

1. Treating lat–lon points as the carriers of physics (`dataset_to_stacked`, `nlat*nlon` flatten).
2. Separate icosahedral “dynamics mesh” — **MPAS already is the unstructured mesh**.
3. Grid2Mesh / Mesh2Grid as the primary path — keep only if fusing **external lat–lon reanalysis** into native cells.
4. Homogeneous `mesh_nodes` for all prognostics — MPAS is **C-grid staggered** (tracers/SSH on cells; normal velocity on edges).
5. `normalized_latitude_weights` — replace with **`areaCell` / thickness** weights.
6. Atmosphere TaskConfig / solar forcings / land–sea mask as-is.

**Suggested mapping**

| GraphCast concept | MPAS analogue |
|-------------------|---------------|
| `grid_nodes` (physics) | Drop as primary carriers; optional forcing/aux nodes |
| `mesh_nodes` | Prefer **`cells` + `edges` (+ `vertices` if needed)** |
| Multi-mesh edges | Coarse↔fine cell graphs or k-hop dual edges |
| Mesh processor | Typed MP on incidence / dual graph |
| Lat weights | `areaCell` / layer-thickness-weighted loss |
| AR rollout | Same pattern over spinup lead times or multi-time fusion |

**Bottom line for GraphCast:** treat it as a **reference implementation of typed sphere-graph GNNs**, not a model to fine-tune on ERA5. Keep TypedGraph/GNN/residual stack; rebuild I/O and graph construction for MPAS.

---

## 5. Recommended architecture (hybrid)

```
Early restart/history + forcings + config/mesh statics
        │
        ▼
 Stream encoders (LandSim-style tokenization of time/config)
        │
        ▼
 Node embedding on MPAS cells / edges
        │
        ▼
 Mesh processor (GraphCast-style DeepTypedGraphNet
                 ± optional sparse attention on cell dual)
        │
        ▼
 Decode heads → residual Δstate → near-eq fields
        │
        ▼
 Copy template restart → overwrite predicted variables
        │
        ▼
 QC + MPAS-Analysis + N-day forward restart test
```

### 5.1 Three model tracks

| Track | Description | When |
|-------|-------------|------|
| **A. Mesh GNN residual (start here)** | Single early snapshot (+ static mesh/config) → residual to near-eq restart | Fastest path to writeback + forward tests |
| **B. Temporal fuse + GNN (LandSim-like)** | Patch early trajectory / forcing time series, then mesh GNN | Best match to LandSim strategies once multi-time samples exist |
| **C. Multi-scale / sparse attn** | METIS coarse graphs or GenCast-style banded attention | After A/B prove skill; needed for large meshes (e.g. EC30to60…) |

### 5.2 C-grid staging

- **Phase 2 MVP:** cell-centered prognostics (T, S, SSH, layer thickness) only.
- **Phase 3:** add **edge** nodes for `normalVelocity` (and related) so stagger structure is preserved.
- Avoid collapsing all fields to cell centers permanently if restart writeback must remain dynamically usable.

---

## 6. Phased roadmap

### Phase 0 — Schema and targets (do this on the ocean-data machine)

1. `ncdump -h` (or equivalent) on sample **restart** and **history** files from Hyun’s path; document dims (`nCells`, `nEdges`, `nVertLevels`, …) and variable names against the user guide.
2. Split IO lists:
   - `Ocean_IO_config.txt` — regime tokens (starting from `selected_variables.txt`)
   - `Ocean_IO_prognostics.txt` — restart fields to predict
   - `Ocean_IO_diagnostics.txt` — OHC / validation-only fields
3. Operationally define “near equilibrium” (calendar time vs OHC / drift thresholds from Alice/Hyun).
4. Register mesh IDs for v1 (**QU240 first**).

### Phase 1 — DataGEN on the same mesh

1. Port LandSim_dataGEN pattern → `Ocean_dataGEN`: early X, late Y, forcings, static mesh, masks.
2. Prefer **same-mesh identity joins** (no lat/lon KD-tree when mesh matches).
3. Store connectivity once per mesh; ship area-weighted QC.
4. Publish **baselines before any neural net**: persistence (early≈late), climatology, optional analysis interpolate.

### Phase 2 — Mesh GNN MVP (Track A)

1. MPAS mesh → `TypedGraph` builder (unit-test on QU240).
2. `DeepTypedGraphNet` processor; residual heads; `areaCell` × level-weighted MSE.
3. Restart writeback script (LandSim `ai_predictions_to_restart` analogue).
4. N-day forward test vs long-spinup restart under the **same namelist regime**.

### Phase 3 — Temporal fusion + edges (Track B)

1. Multi-time early history / forcing tokens.
2. Optional bipartite link for external lat–lon analysis (only place GraphCast-style grid2mesh returns).
3. Edge-node velocity heads; weak physics penalties (stratification; optional barotropic / SSH projection).

### Phase 4 — Production hardening

1. Multi-mesh / multi-forcing generalization.
2. METIS multi-scale or sparse attention if resolution jumps.
3. MPAS-Analysis scorecards; document Perlmutter/Frontier ingest; quantify wallclock savings.

---

## 7. Risks and mitigations

| Risk | Why it matters | Mitigation |
|------|----------------|------------|
| Config list mistaken for prognostics | Wrong training targets | Separate IO lists; lock against restart headers |
| Copying LandSim cell IID model | Misses nonlocal ocean equilibration | Require mesh GNN from MVP |
| Dynamical inconsistency | ML restart drifts quickly | Residual learning + short forward tests + optional projections |
| Expensive long-spinup labels | Few Y examples | QU240 first; multi-segment short→mid pairs; curated long runs |
| C-grid mismatch | Velocity on edges | Cell tracers first; edges in Phase 3 |
| Distribution shift (new mesh/forcing) | Poor zero-shot | Graph-native model; train on multiple meshes when available |

---

## 8. Proposed team actions

| Person | Next actions |
|--------|--------------|
| **Alice** | Lock prognostic restart + equilibrium diagnostic lists; confirm OHC / other steady-state indices |
| **Hyun** | Confirm sample restart/history paths; QU240 case; MPAS-Analysis hooks; share utilities for time series / maps |
| **Olawale** | Port LandSim dataGEN / training-sample strategies to OceanAISpinup; document pairing rules |
| **Dali** | TypedGraph builder + Track A MVP + restart ingest design; keep this report updated from data-machine findings |

---

## 9. Checklist for the ocean-data machine

Use this list when improving the report with real file schemas:

- [ ] List restart variables and dims from one early and one near-eq sample
- [ ] List history variables needed for OHC / MLD / validation plots
- [ ] Confirm which fields are required for a usable restart vs optional
- [ ] Record mesh name, vertical grid, and namelist hash / key config diffs between early and late runs
- [ ] Estimate number of usable (early, late) pairs and time spacing
- [ ] Draft `Ocean_IO_prognostics.txt` and attach example `ncdump` snippets
- [ ] Note any land/ice/shelf masking rules for loss and writeback
- [ ] Identify baseline RMSE of persistence on T/S/SSH with `areaCell` weights

---

## 10. References inside this repo

- `MPAS_Ocean_ML_Init_Report.md` — prior high-level concept and slide outline
- `MPAS_Ocean_ML_Init_Deck.pptx` — companion slides
- `graphcast_gnn_mesh_schematic.png` / `GraphCast_gridhandling.png` — mesh I/O figures
- `generate_graphcast_schematic.py` — schematic regenerator
- `MPAS_Ocean_Users_Guide_E3SM_V3.0.0.pdf` — authoritative MPAS-Ocean I/O
- `Copy of Running MPAS-Ocean on Perlmutter and Frontier.txt` — HPC workflow notes
- `background.txt`, `selected_variables.txt` — team notes and current config list

---

*Report generated from GraphCast + LandSim codebase review for AI4MPAS OceanAISpinup planning. Please amend §2 and §9 after inspecting the NERSC sample spinup archive.*
