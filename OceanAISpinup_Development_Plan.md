# OceanAISpinup: Codebase Review and Development Plan

**Date:** 2026-07-30 (amended 2026-08-27 with local sample inventory; **2026-09-10** Frontier DATM + restart/history re-inspection)  
**Audience:** AI4MPASO / ImPACTS ocean spinup team (Dali, Alice, Hyun, Olawale)  
**Purpose:** Share findings from reviewing GraphCast and LandSim, and propose a concrete plan for an MPAS-Ocean early→equilibrium AI model that respects unstructured-mesh coupling.

**Related local notes**

- `OceanAISpinup_Prototype_Plan.md` — prototype e2e; Dali builds then advises (**use this to begin coding**)
- `OceanAISpinup_Start_Report.md` — 2026-09-10 Frontier audit and data freeze
- `OceanAISpinup_Diffusion_Evaluation.md` — GraphCast / GenCast / LandSim re-review of the diffusion decision
- `OceanAISpinup_Implementation_Plan.md` — detailed architecture, pair factory, and WP list
- `data/docs/AIREADY_DATASET.md` — portable tensor pack for a second GPU cluster
- Local sample (headers / namelists): `data/OceanSpin_sample/` — see §2.3
- Sample data (NERSC): `/global/cfs/cdirs/m4259/hgkang/data_for_others/Dali_OceanSpinup_sample`
- MPAS-Analysis example: [GMPAS-NYF_QU240](https://portal.nersc.gov/project/e3sm/hgkang/ImPACTS/AI_spinup/v3.GMPAS-NYF_QU240/www/)

**Codebases reviewed**

| Codebase | Path | Role in this plan |
|----------|------|-------------------|
| GraphCast / GenCast | local copy; not tracked (`graphcast/` gitignored) | Typed mesh GNN / sparse transformer operators |
| LandSim | not in this repo | Early→equilibrium pairing, multi-stream fusion, restart writeback |
| MPAS-Ocean guide | E3SM v3 user guide (not vendored on this branch) | Restart/history schema; headers in `data/OceanSpin_sample/` |

---

## 1. Executive summary

**Goal.** Learn a map from **early / partial MPAS-Ocean spinup** (+ forcings, mesh, and configuration context) to a **near-equilibrium / restart-quality** ocean state, then inject predictions into an MPAS restart file—analogous to LandSim for ELM.

**Hard constraint.** Unlike LandSim (and unlike treating atmosphere on a lat–lon grid as independent cells), MPAS-Ocean state lives on an **unstructured C-grid**. Horizontal coupling through circulation, waves, and tracer advection means a **per-cell IID model is insufficient**.

**Recommended strategy.**

1. **Reuse LandSim’s workflow spine:** modular data generation of early (**X**) vs near-eq (**Y**) pairs, config-driven IO lists, per-variable normalization, multi-task weighted loss, and template-restart overwrite.
2. **Reuse GraphCast’s mesh operator stack:** `TypedGraph` + `DeepTypedGraphNet` encode–process–decode, geometric edge features, residual prediction, optional autoregressive / multi-time training.
3. **Replace** GraphCast’s lat–lon ↔ icosahedral bridges and LandSim’s cell-independent Transformer with a **native MPAS cell/edge(/vertex) graph processor** and **`areaCell`-weighted** losses.

**Immediate clarification.** `data/OceanSpin_sample/mpaso_variables` lists **namelist physics/config knobs** (GM, KPP, bottom drag, EOS, remapping, etc.). Those should condition the model as a **simulation regime**, but they are **not** the prognostic restart fields the AI should predict. Prognostic names are now locked against the sample restart header (§2.3): `temperature`, `salinity`, `layerThickness`, `normalVelocity` on deep levels k=46…60.

---

## 2. Problem framing

### 2.1 What we are predicting

| Role | Content | Status |
|------|---------|--------|
| **Regime / config tokens** | Namelist settings in `mpaso_variables` (viscosity, GM/Redi, KPP, drag, EOS, …) | **Locked** (one NYF case; constant per run) |
| **Static mesh features** | `latCell`/`lonCell`, `areaCell`, `bottomDepth`, Coriolis, `cellsOnCell` / edge incidence | **In the restart file** (QU240: 7153 cells, 22403 edges, 60 levels) |
| **Early state (X)** | Restart deep T/S/`layerThickness` (optional `normalVelocity`) | Format sample: `rst.0661-01-01`; intended scientific X is ~50 yr |
| **Context** | DATM CORE2_NYF (NCEP `u,v,t,slp` + GXGXS `prc`; not history coupler fluxes) | **Locked**; NYF cycles — does not differentiate pairs until more cases exist |
| **Target (Y)** | Same restart prognostics at later time, deep mask k=46…60 | Format sample: `rst.0681-01-01`; intended scientific Y is ~600 yr |
| **Diagnostics (validation only)** | History OHC bands, especially `timeMonthly_avg_oceanHeatContent2000mToBot`; MLD; N² | Present in sample monthly history `0678-11` |

`ssh` is **not** in the sample restart; do not treat it as a writeback field. Use `layerThickness` plus the template restart for a usable file.

### 2.2 Success criteria (proposed)

- Global / basin **RMSE and bias** vs reference long spinup on primary prognostics, with **`areaCell` (and vertical) weighting**.
- Stratification / static-stability sanity (no systematic unstable profiles).
- **Short forward test:** restart from ML state, integrate **N days** with the same namelist, compare drift to restart-from-full-spinup.
- Wallclock / human-iteration savings vs completing full ocean spinup for new cases.

### 2.3 Local sample findings (2026-08-27)

Inspected `data/OceanSpin_sample/` (headers, `mpaso_in`, DATM streams). NetCDF payloads are gitignored.

| Item | Finding |
|------|---------|
| Case | `v3.GMPAS-NYF_QU240`, MPAS git `be7af980a1`, `noleap`, `config_dt=01:00:00`, z-star 60 levels |
| Restart dims | `nCells=7153`, `nEdges=22403`, `nVertices=15211`, `maxEdges=6` |
| Prognostic names | `temperature`, `salinity`, `layerThickness`, `normalVelocity` (not history aliases) |
| Deep mask | `refBottomDepth[k]>2000` and `k≤maxLevelCell` → **k=46…60** (~2075–5500 m) |
| Format pair | Original sample 0661/0681 (20 yr, late). **Frontier:** monthly rst **0051–0055** and **0601–0605** (60 + 60 files) |
| History | `timeSeriesStatsMonthly.0678-11-01`; OHC 0–700 / 700–2000 / 2000–bot / sfc–bot |
| OHC constants | ρ₀=`config_density0=1026`, cₚ=`config_specific_heat_sea_water=3996` |
| DATM | CORE2_NYF cycle; NCEP T62 94×192, `time=1460`; bilinear to oQU240 |
| Physics | GM/Redi κ=900; mom_del2=4000; mom_del4=2e14; KPP+convection on |

**Still needed from Hyun’s archive:** whether more years exist between 55 and 601 (or after 605). Two 5-year monthly windows are already on Frontier.

Details, IO contract, and work packages: `OceanAISpinup_Implementation_Plan.md`. Variable notes: `data/docs/`.

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

- **Phase 2 MVP:** cell-centered prognostics (`temperature`, `salinity`, `layerThickness`) only. Sample restart has **no** standalone `ssh`.
- **Phase 3:** add **edge** nodes for `normalVelocity` so stagger structure is preserved.
- Avoid collapsing all fields to cell centers permanently if restart writeback must remain dynamically usable.

---

## 6. Phased roadmap

### Phase 0 — Schema and targets — **done locally** (2026-08-27)

1. ~~`ncdump -h` on sample restart and history~~ — headers in `data/OceanSpin_sample/`; dims and names documented in §2.3 and `data/docs/`.
2. IO lists (machine-readable):
   - `data/OceanSpin_sample/mpaso_variables` — regime tokens
   - `data/OceanSpin_sample/restart_variables` — restart fields to predict (deep mask)
   - History diagnostics: `timeMonthly_avg_oceanHeatContent*` (see implementation plan §2.4)
3. “Near equilibrium” for v1: **calendar ~600 yr** plus deep OHC 2000 m–bottom as the slow-spinup index (`Ocean_EQ.png`). Drift thresholds still to confirm with Alice/Hyun.
4. Mesh ID v1: **QU240** (`nCells=7153`).

Open: full restart year inventory on NERSC; payload `.nc` files on the workdir.

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
| **Dali** | Prototype e2e (`OceanAISpinup_Prototype_Plan.md`); then advisor |
| **Alice** | After handoff: OHC QC, holdout maps, near-eq thresholds |
| **Hyun** | Extra restart years if any; MPAS-Analysis / N-day forward after an ML restart exists |
| **Olawale** | After handoff: LandSim-style dataGEN / scaler / training hardening |

---

## 9. Checklist for the ocean-data machine

Use this list when improving the report with real file schemas:

- [x] List restart variables and dims from one early and one near-eq **format** sample (`0661`, `0681`; same schema)
- [x] List history variables needed for OHC / MLD / validation plots (`history_header.txt`)
- [x] Confirm which fields are required for a usable restart vs optional (overwrite T/S/`layerThickness` only in v1; keep auxiliaries from template; no standalone `ssh`)
- [x] Record mesh name, vertical grid, and key configs (QU240, z-star 60, `mpaso_in`; early vs late share one namelist in this case)
- [x] Estimate number of usable (early, late) pairs: **60 month-aligned 550-year pairs** on Frontier (years 51–55 × 601–605); plus short-Δ inside each window
- [x] Remapped DATM on oQU240 cells (`ncol=7153`, identity join); GISS daily; NCEP 6-hourly; precip monthly (`OceanAISpinup_Start_Report.md`)
- [x] Prognostic IO list: `data/OceanSpin_sample/restart_variables` + restart header
- [x] Masking: `maxLevelCell` / `bottomDepth>2000` / fill value; no `cellMask` array in restart
- [ ] Identify baseline RMSE of persistence on deep T/S (and OHC) with `areaCell` weights — run on **0051-01-01 → 0601-01-01**

---

## 10. References inside this repo

- `README.md` — handoff front door
- `prototype/README.md` — how to run the pilot
- `data/docs/` — DATM, `mpaso_in`, restart deep-ocean selection, AI-ready pack
- `data/OceanSpin_sample/` — GMPAS-NYF_QU240 headers, namelists, stream XML
- `OceanAISpinup_Start_Report.md` — 2026-09-10 Frontier data audit and how to start
- `OceanAISpinup_Implementation_Plan.md` — architecture, pair factory, work packages
- `docs/HANDOFF.md` — what this branch dropped vs `main`

---

*Report generated from GraphCast + LandSim codebase review for AI4MPASO OceanAISpinup planning. §2.3 and §9 updated 2026-08-27 from the local sample headers; 2026-09-10: Frontier remapped DATM + restart/history confirmed (`OceanAISpinup_Start_Report.md`). Remaining blocker for diffusion: denser restart years, not schema.*
