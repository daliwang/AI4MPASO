# OceanAISpinup — Detailed Implementation Plan

**Date:** 2026-08-27  
**Status:** Schema-ready for a QU240 prototype; **not** yet training-ready  
**Companion:** `OceanAISpinup_Development_Plan.md` (GraphCast / LandSim review)  
**Data docs:** `data/docs/` (DATM, `mpaso_in`, restart deep-ocean selection)

This note answers three questions:

1. Do we know enough about Kang’s MPAS-Ocean sample to design the system?
2. How should the **model** represent the map from early spinup → late spinup, including atmosphere, physics parameters, and especially the **unstructured mesh**?
3. How should we **prepare training data**, including a conditional **diffusion / flow** option?

---

## 1. Direct answer: is Kang’s data enough?

**Enough to design the architecture, graph builder, IO contract, and a single-mesh prototype loader. Not enough to train a model that actually uses atmospheric forcing and physics parameters as causal inputs.**

| Question | What we have | Gap |
|---|---|---|
| Mesh topology | Full restart header: `nCells=7153`, `nEdges=22403`, `nVertices=15211`, `nVertLevels=60`, `maxEdges=6` | Need the mesh file (or restart) on disk for `cellsOnCell`, `cellsOnEdge`, `areaCell`, … |
| Prognostic names | Restart header locks **actual** NetCDF names (see §2.2) | Selection docs still use some aliases (`layerThickness` vs `layerThickness`) — lock to the header |
| Deep-ocean target | Alice/Hyun: 2000 m–bottom OHC is the slow spinup signal; `k = 46…60` | Need a script that computes deep OHC from restart and matches history `timeMonthly_avg_oceanHeatContent2000mToBot` |
| Early vs late pairing | **Intended:** restart@~50 yr → restart@~600 yr | Sample only has **0661** and **0681** (20 years apart), plus one monthly history (`0678-11`) |
| Atmosphere | CORE2 NYF streams documented; NCEP T62 6-hourly climatology (`time=1460`) | NYF **cycles the same year**. With one case, forcing is identical for every pair |
| Physics configs | `mpaso_in` + `mpaso_variables` | Also **constant** for one case — cannot learn parameter sensitivity yet |
| Training volume | Format samples + headers | Need the long-run restart archive (many years) and/or additional cases (params, meshes) |

**Implication for architecture:** on the current sample, atmosphere and namelist are **run-level metadata**, not per-example features. The mesh **is** the spatial operator and must be first-class. Forcing and parameters become informative only when the dataset spans **multiple physics settings, forcings, or meshes**.

The rest of this plan is written so a QU240 MVP can start now, and so later multi-run data plugs in without changing the IO contract.

---

## 2. What Kang’s sample actually is

### 2.1 Case

| Item | Value |
|---|---|
| Case | `v3.GMPAS-NYF_QU240` |
| Ocean mesh | Quasi-uniform QU240 (~240 km), spherical MPAS C-grid |
| Atmosphere | DATM `CORE2_NYF` (prescribed, cycled normal year) |
| Calendar | `noleap` |
| Ocean `config_dt` | `01:00:00` |
| Vertical | 60 z-star / ALE levels |
| NERSC pointer | `/global/cfs/cdirs/m4259/hgkang/data_for_others/Dali_OceanSpinup_sample` |
| Analysis | [MPAS-Analysis GMPAS-NYF_QU240](https://portal.nersc.gov/project/e3sm/hgkang/ImPACTS/AI_spinup/v3.GMPAS-NYF_QU240/www/) |

### 2.2 Restart fields — **use header names, not aliases**

From `data/OceanSpin_sample/restart/mpas_ocean_header.txt`:

| Role | NetCDF name (lock this) | Shape | Notes |
|---|---|---|---|
| Potential temperature | `temperature` | `Time, nCells, nVertLevels` | °C |
| Salinity | `salinity` | `Time, nCells, nVertLevels` | 1e-3 |
| Layer thickness | `layerThickness` | `Time, nCells, nVertLevels` | m; **not** `layerThickness` |
| Edge-normal velocity | `normalVelocity` | `Time, nEdges, nVertLevels` | m/s; **not** `normalVelocity` |
| Column depth | `bottomDepth` | `nCells` | m |
| Active levels | `minLevelCell`, `maxLevelCell` | `nCells` | 1-based indices |
| Reference z | `refBottomDepth` | `nVertLevels` | m |
| Resting thickness | `restingThickness` | `nCells, nVertLevels` | ALE reference |

Deep mask (this mesh):

```
refBottomDepth[k] > 2000  and  k <= maxLevelCell[i]  and  bottomDepth[i] > 2000
```

with **k = 46…60** (1-based). That is **15 deep levels**.

History validation (not a restart writeback field):

- `timeMonthly_avg_oceanHeatContent2000mToBot` (J per cell)

`ssh` is **not** present as a standalone restart variable in this header; column thickness / SSH consistency must be handled via `layerThickness` (and MPAS’s own SSH reconstruction) if a full restart is written.

### 2.3 Atmosphere (DATM), not coupler fluxes

| Stream | Grid | Time | Variables to use |
|---|---|---|---|
| NCEP | T62, 94 × 192 | 6-hourly NYF (`time=1460`) | `u_10`, `v_10`, `t_10`, `slp_` (Tier-1); `q_10`, `dn10` (Tier-2) |
| GXGXS | T62 | monthly climatology (12) | `prc` |
| GISS | T62 | monthly | `swdn`, `swup`, `lwdn` |

Do **not** train on history `windStress*`, `latentHeatFlux`, `rainFlux`, etc. Those depend on SST/ice.

Because NYF **cycles**, a 50-year and a 600-year restart see the **same annual forcing**. The ocean still changes because of **slow internal adjustment**. Forcing still belongs in the model as a **condition** (the map is “under this repeating climate”), but it will not differentiate samples until we have IAF, different NYF products, or flux perturbations.

### 2.4 Physics parameters

`mpaso_variables` / `selected_variables.txt` are **namelist scalars/flags** (GM/Redi κ, visc, KPP, drag, EOS, …). Encode as a global token vector (float / log-float / boolean / categorical). With one `mpaso_in`, store once as run metadata.

### 2.5 Mesh is the major difference

LandSim treats each land cell as IID. GraphCast uses a **separate** icosahedral mesh and keeps loss on lat–lon. MPAS-Ocean **already is** the unstructured C-grid:

| Entity | Count (QU240) | Carries |
|---|---|---|
| Cells (primal polygons) | 7153 | `temperature`, `salinity`, `layerThickness`, `areaCell`, bathymetry |
| Edges | 22403 | `normalVelocity`, `dcEdge`, `dvEdge`, `fEdge` |
| Vertices (dual triangles) | 15211 | optional vorticity / reconstruction |

Connectivity that **must** become the graph (from the same restart/mesh file):

- `cellsOnCell`, `nEdgesOnCell`, `edgesOnCell`, `cellsOnEdge`
- `areaCell`, `dcEdge`, `dvEdge`, `angleEdge`, `latCell`, `lonCell`, `fCell` / `fEdge`
- land/valid masks via `maxLevelCell` / fill values

QU240 is small enough that a **full-graph GNN** (or even dense attention over 7k cells) is feasible. EC30to60-class meshes will require sparse / multi-scale operators later; do not design the v1 stack around lat–lon patches or ViT on interpolated maps.

---

## 3. Learning problem

We want a **conditional** map, not a next-hour weather step:

\[
x_{t+\Delta} \sim p\big(x_{t+\Delta} \,\big|\, x_t,\, F,\, \theta,\, G\big)
\]

| Symbol | Meaning |
|---|---|
| \(x_t\) | Early restart state on mesh \(G\) (deep T/S/h, optionally `normalVelocity`) |
| \(x_{t+\Delta}\) | Later restart (same variables, same mesh) |
| \(F\) | Atmospheric forcing summary (NYF climatology or time-mean / monthly cycle) |
| \(\theta\) | Physics-config vector from `mpaso_in` |
| \(G\) | Unstructured MPAS graph + static geometry |

**Preferred prediction target:** residual

\[
\Delta x = x_{t+\Delta} - x_t
\]

on the deep mask only. Persistence (\(x_{t+\Delta}=x_t\)) is the first baseline; the network should beat it on deep T and on OHC 2000 m–bottom.

This is **not** GraphCast’s 6-hour rollout. Δ can be 20 yr (sample), 50 yr, or ~550 yr (intended). The model is a **spinup operator**, closer to LandSim’s early→eq map, but with spatial coupling on \(G\).

### 3.1 Why a probabilistic (diffusion) model is plausible

A long ocean spinup is not a unique function of \(x_t\): mesoscale (even at QU240, weakly), convection, and GM closures produce a **distribution** of late states. A Gaussian MSE GNN learns the **conditional mean**. A **conditional diffusion / flow** model learns \(p(x_{t+\Delta}|x_t,F,\theta,G)\), which is useful for:

- sampling an ensemble of restart candidates;
- capturing multi-modal deep-water outcomes if they appear;
- matching GenCast-style training (noise the **target**, condition on context).

**With the current data volume, diffusion will overfit.** Use it as the **target architecture** of the denoiser (mesh GNN/transformer), but **train a deterministic residual GNN first** until there are many \((x_t, x_{t+\Delta})\) pairs (see §5).

---

## 4. Model architecture

### 4.1 Design principles

1. **Native mesh, no lat–lon interpolate of ocean state.** Interpolating T/S to a regular grid for a ViT, then interpolating back, destroys C-grid stagger and cell volume. Use that path only for **DATM**, which already lives on T62.
2. **Typed graph.** Cell nodes and edge nodes are different types (GraphCast `TypedGraph` idea; MPAS incidence instead of icosahedron).
3. **Vertical as channels, not a 3rd graph.** Deep k=46…60 → 15 channels per field on each cell/edge (GraphCast-style stacking). Optional 1D vertical mixing MLP per column after horizontal MP.
4. **Conditioning is global + local.** \(x_t\) and mesh geometry are local node features. \(F\) and \(\theta\) are global (or coarsened) tokens injected by FiLM / scale-shift LayerNorm (GenCast `use_norm_conditioning` pattern) or concatenated context nodes.
5. **Area-weighted loss.** Weight cells by `areaCell` (and `layerThickness` or `restingThickness` for 3D). Do not use GraphCast latitude weights.
6. **Writeback must use restart names and index spaces** (`nCells` / `nEdges`), LandSim-style copy-template overwrite.

### 4.2 Graph construction (once per mesh)

```
MPAS restart or mesh file
  → node_cells:  [nCells,  F_static]
  → node_edges:  [nEdges,  F_static]
  → edges cell→cell   from cellsOnCell (symmetric)
  → edges cell↔edge   from cellsOnEdge / edgesOnCell
```

Static cell features: unit-sphere position (`xCell,yCell,zCell` or lat/lon), `areaCell`, `bottomDepth`, `fCell`, `meshDensity`, deep-column flag.  
Static edge features: `dcEdge`, `dvEdge`, `angleEdge`, `fEdge`, relative sender–receiver vectors (GraphCast `get_graph_spatial_features` analogue).

Store the graph as a **mesh ID cache** (QU240 v1). Do not rebuild every sample.

### 4.3 Conditioning encoders

**A. Early ocean state (local)**  
Per cell: deep `temperature`, `salinity`, `layerThickness` at \(t\).  
Per edge (phase 2): deep `normalVelocity`.  
Normalize with per-variable (optionally per-level) scalers, LandSim `IndividualScalerManager` style.

**B. Atmosphere \(F\)** — two acceptable encodings (pick one for v1):

| Option | How | Use when |
|---|---|---|
| **B1. NYF monthly cycle on T62, then bilinear to cells** | 12 × (u,v,t,slp,prc,…) → per-cell seasonal tokens | Single NYF case; cheap; matches DATM `mapalgo=bilinear` |
| **B2. Keep T62 as a second node set** | GraphCast-style bipartite grid→mesh GNN | Later, if forcing varies in time or product |

For NYF, **B1 with a 12-month climatology** (or even annual mean) is enough. Do not feed 1460×T62 raw 6-hour fields into the ocean GNN.

**C. Physics \(\theta\)**  
Encode `mpaso_variables` to a vector \(e_\theta\). Inject with FiLM on every residual block. If \(\theta\) is constant in the batch, this is a no-op at train time but keeps the interface for multi-physics data.

**D. Mesh \(G\)**  
Already in the operators. Optionally add a learned **mesh-ID embedding** when multiple meshes exist.

### 4.4 Backbone options (same IO, swap processor)

```
                 ┌─ DATM encoder (B1 or B2) ── e_F
x_t, G_static ──┤
                 ├─ Config encoder ───────────── e_θ
                 │
                 └─ Node embed(cells, edges)
                            │
                    Mesh processor  ← FiLM(e_F, e_θ)
                            │
                    Heads: ΔT, ΔS, Δh  (cells)
                           Δu_n         (edges, later)
                            │
                    x̂_{t+Δ} = x_t + Δx   (masked)
```

| Track | Processor | Training objective | When |
|---|---|---|---|
| **A. Deterministic Mesh GNN (MVP)** | `DeepTypedGraphNet`-style MP, 8–16 steps, residual | Area-weighted MSE / Huber on \(\Delta x\) | Now; QU240 |
| **B. Mesh transformer** | GenCast sparse self-attention on cell dual (k-hop mask); RCM reorder if needed | Same as A | If MP receptive field is too local for basin-scale spinup |
| **C. Conditional diffusion / flow** | Same processor as **denoiser** | Denoise \(x_{t+\Delta}\) (or \(\Delta x\)) given \((x_t,F,\theta,G,\sigma)\) | After ≥O(10²) pairs; ensemble restarts |

QU240 has 7k cells: Track B can start as **dense** attention (7k² is acceptable). EC meshes should use sparse k-hop or multi-scale (METIS) graphs, **not** GraphCast’s icosahedral merge.

### 4.5 Diffusion / flow (Track C) — recommended formulation

Treat the **late state residual** as the generated field.

**Forward (training):**  
Let \(y = \Delta x = x_{t+\Delta}-x_t\). Sample \(\sigma\) (or \(t_{\text{diff}}\in[0,1]\)).  
\(y_\sigma = y + \sigma\,\varepsilon\), \(\varepsilon\sim\mathcal{N}(0,I)\) on valid deep cells/edges only.

**Score network / denoiser \(D_\phi\):**  
Same mesh GNN/transformer as Track A. Extra input: noise level (Fourier embedding + FiLM). Conditioning channels: \(x_t\), static \(G\), \(e_F\), \(e_\theta\).

**Loss:** EDM / flow-matching on valid points, weighted by `areaCell` × layer thickness.

**Sampler (inference):** start from noise, reverse to \(\hat y\), set \(\hat x_{t+\Delta}=x_t+\hat y\), apply mask and optional post-process (see §4.6).

**Prefer flow matching over vanilla DDPM** for this problem: fewer steps, more stable on continuous physical fields (as in recent weather diffusion / GenCast-class models). Keep the same denoiser.

**Do not** diffuse DATM or \(\theta\); they are conditions, not generated variables.

**Do not** expect Track C to work on two sample restarts. It needs the pair factory in §5.

### 4.6 Physics-light constraints (post-net, not a full ocean model)

Apply after decode, before writeback:

1. Mask inactive cells/levels (`maxLevelCell`, fill values).
2. Keep `layerThickness` positive (softplus or clamp to a fraction of `restingThickness`).
3. Optional: column-sum thickness / SSH consistency if writing a full restart.
4. Optional: static-stability penalty (N²) in the loss, not a hard layer.
5. Velocity (phase 2): predict `normalVelocity` on edges; do not independently predict reconstructed zonal/meridional at cells.

A full divergence-free / continuity projection is **out of scope for v1**. The N-day forward MPAS run is the real dynamical filter.

### 4.7 Why not a LandSim Transformer or a grid ViT as the backbone?

| Approach | Failure mode here |
|---|---|
| LandSim per-cell Transformer | No neighbor communication; deep spinup is nonlocal (circulation, GM, waves) |
| ViT on interpolated lat–lon | Wrong measure (`areaCell`), smears C-grid, bad coastal/bathymetry |
| GraphCast as-is | Icosahedral mesh ≠ MPAS; loss on ERA5 grid; atmosphere 6-hour task |
| GenCast as-is | Same mesh mismatch; designed for short-range weather diffusion |

Reuse **LandSim** for data pairing, scalers, restart overwrite. Reuse **GraphCast/GenCast** for typed graphs, geometric edge features, residual heads, and (later) the diffusion wrapper. Replace their grids with MPAS incidence.

---

## 5. Training-dataset preparation

This is the critical path. Architecture will idle without pairs.

### 5.1 Pair factory (LandSim analogue)

Build `Ocean_dataGEN` with explicit roles:

| Stream | Source | Per sample |
|---|---|---|
| X | Restart at \(t\) | Deep T, S, `layerThickness`, (optional `normalVelocity`) |
| Y | Restart at \(t+\Delta\) | Same fields |
| F | DATM NYF | Monthly cycle remapped to cells (shared across samples for NYF) |
| θ | `mpaso_in` | Config vector (shared per run) |
| G | Mesh / restart geometry | Graph cache keyed by mesh ID |
| QC | History optional | Deep OHC time series for the same years |

**Identity join on cell/edge indices** when mesh matches. No lat/lon KD-tree.

### 5.2 How to get enough pairs from limited spinups

Kang’s **intended** pairing is one map: 50 yr → 600 yr. That is **one supervised example** per simulation. A network cannot be trained on that.

Use the **long trajectory** as a dataset:

| Recipe | Pair definition | Purpose |
|---|---|---|
| **Multi-horizon** | All \((t, t+\Delta)\) with \(\Delta \in \{20,50,100,\ldots\}\) yr | Learn a family of spinup operators; condition on \(\Delta\) (or \(\log\Delta\)) as a token |
| **Sliding annual** | Consecutive Jan-1 restarts along the run | Dense local residuals; easier than 550-year jump |
| **Curriculum** | Train short \(\Delta\) first, then increase | Stabilizes residual learning |
| **Deep-only tensors** | Store only k=46…60 + mask | Cuts volume ~4× vs full 60 levels |
| **Physics ensemble** (later) | Same mesh, perturbed GM/Redi/visc | Makes \(\theta\) identifiable |
| **Forcing ensemble** (later) | NYF vs IAF vs precip scale | Makes \(F\) identifiable |
| **Mesh transfer** (later) | QU240 train, EC holdout or dual-mesh | Tests graph-native generalization |

**Minimum viable training set (proposed, Hyun/Alice to confirm inventory):**

- All annual (or 5-year) restarts from the QU240 NYF spinup between ~year 20 and ~year 600.
- Labels: next checkpoint and/or the 600-year state (two heads or \(\Delta\)-conditioned).
- Hold out: a late window (e.g. years 500–600) **or** a geographic basin, not random cells.

If only a handful of restarts exist, **do not start diffusion**; compute persistence RMSE and stop until more checkpoints are exported.

### 5.3 Normalization and QC

- Fit scalers on **train years only**.
- Per-variable min-max or z-score; log-scale for `config_mom_del4`-class coefficients in \(\theta\).
- Drop cells with `bottomDepth ≤ 2000` from the loss (or weight 0).
- Reject samples with fill-value storms / NaNs in deep T/S.
- Verify OHC: \(\sum_i \sum_{k\in\text{deep}} \rho_0 c_p\, T_{i,k}\, h_{i,k}\, A_i\) vs history `timeMonthly_avg_oceanHeatContent2000mToBot` (global sum).

### 5.4 On-disk layout (suggested)

```
data/processed/QU240/
  mesh_graph.npz          # once
  scalers/               # IndividualScalerManager analogue
  pairs/index.parquet    # t, t_delta, paths, mesh_id, config_id
  pairs/xxxxx.npz        # tensors: x_t, x_td, mask, (optional F_cell)
```

Keep raw `.nc` gitignored. Version **index + docs + code**, not payloads.

### 5.5 Baselines before any neural net

Compute on the same pairs:

1. **Persistence:** \(\hat x_{t+\Delta}=x_t\)
2. **Linear drift:** fit global/basin deep-T trend vs year, apply uniformly
3. **Climatology of late state:** predict the time-mean of all Y in train

Report area-weighted RMSE/bias for deep T, S, and OHC 2000 m–bottom. Any GNN/diffusion must beat (1) and (2).

---

## 6. Implementation work packages

### WP0 — Name and schema lock (1–2 days)

- [ ] Freeze NetCDF names to the restart header (`layerThickness`, `normalVelocity`, …).
- [ ] Update `restart_variables` / `RESTART_DEEP_OCEAN_STATE.md` aliases.
- [ ] Inventory Kang’s full restart times on NERSC (list of `rst.*.nc` years).
- [ ] Confirm 50 yr and 600 yr file paths vs the 0661/0681 samples.

### WP1 — Graph + dataset (1–2 weeks)

- [ ] `mpas_mesh_to_typedgraph.py` on QU240 (unit test: nCells, degree ≤ 6, area sum).
- [ ] Deep-mask builder from `refBottomDepth` / `maxLevelCell`.
- [ ] Pair index from restart catalog; PyTorch `Dataset` returning cell/edge tensors.
- [ ] DATM monthly climatology remap T62 → cells (reuse E3SM map file if available: `domain.lnd.T62_oQU240.*`).
- [ ] Baseline RMSE script.

### WP2 — Deterministic GNN MVP (Track A)

- [ ] Cell-only residual GNN: predict deep \(\Delta T,\Delta S\) (thickness frozen or predicted).
- [ ] Area × thickness weighted loss; FiLM stubs for \(F,\theta,\Delta\).
- [ ] Copy-template restart writeback for predicted fields only.
- [ ] Compare maps + global deep OHC vs 0681 / 600-yr target.

### WP3 — Dynamics smoke test

- [ ] Short MPAS-Ocean forward from ML restart vs official restart (N days).
- [ ] MPAS-Analysis hooks for T/S/OHC.

### WP4 — Edges, time, diffusion

- [ ] Add `normalVelocity` edge nodes.
- [ ] \(\Delta\)-conditioned multi-horizon training.
- [ ] If pair count is sufficient: flow-matching wrapper around the same backbone; ensemble of 4–8 late states; pick member with best deep-OHC.

### WP5 — Generalization (only with new simulations)

- [ ] Second `mpaso_in` or precip-scale ensemble so \(\theta\) and \(F\) vary.
- [ ] Second mesh (if/when provided); mesh-ID embedding + graph rebuild.

---

## 7. Suggested v1 model card (so implementation is unambiguous)

| Item | v1 choice |
|---|---|
| Mesh | QU240 only |
| State | Deep k=46–60 `temperature`, `salinity`; optional `layerThickness` |
| Velocity | Deferred (Track A cell-only) |
| Atmosphere | NYF 12-month means remapped to cells (condition, may be constant) |
| Config | `mpaso_variables` vector (condition, may be constant) |
| Lead \(\Delta\) | Conditioning token; train on all available checkpoint gaps |
| Processor | 10–12 step interaction GNN, 128–256 latent, residual |
| Loss | Huber, `areaCell` × `restingThickness` weights, deep mask |
| Generative | **Interface ready** (noise/FiLM slot); **not trained** until pair count allows |
| Output | Residual add + mask → restart overwrite |

---

## 8. Risks (implementation-specific)

| Risk | Mitigation |
|---|---|
| Two sample restarts mistaken for a dataset | Inventory the full spinup; pair factory along time |
| Alias mismatch (`layerThickness` vs `layerThickness`) | Header is source of truth |
| Learning \(F\) or \(\theta\) from one NYF case | Encode them, but evaluate only on ocean-state skill until ensembles exist |
| Interpolating ocean to lat–lon “to use ViT/diffusion-on-images” | Disallowed for ocean state; mesh operators only |
| Diffusion on 1–20 samples | Overfit; keep Track A until O(10²)+ pairs |
| Unusable restart (missing auxiliaries) | v1 overwrites only selected 3D fields; keep other restart vars from template |
| Deep-only prediction vs full-column restart | Document: ML owns k>2000 m; copy shallow levels from \(x_t\) or template |

---

## 9. What to do on the ocean-data machine next

1. `ls` the real restart archive; publish a **year list** (this unblocks WP1).
2. Run `ncdump -v refBottomDepth` and confirm k=46…60 vs 2000 m.
3. Compute persistence RMSE 0661→0681 on deep T (area-weighted) as the first number in the project.
4. Implement WP1 graph builder against the 0661 file (no training required).
5. Only then stand up Track A.

---

## 10. References in this repo

- `OceanAISpinup_Development_Plan.md` — GraphCast vs LandSim transfer
- `data/docs/DATM_FORCING_VARIABLES.md`
- `data/docs/MPASO_PHYSICS_CONFIG_INPUTS.md`
- `data/docs/RESTART_DEEP_OCEAN_STATE.md`
- `data/OceanSpin_sample/restart/mpas_ocean_header.txt` — **authoritative names and dims**
- `data/OceanSpin_sample/history/history_header.txt` — OHC diagnostics
- `Ocean_EQ.png` — deep OHC spinup motivation

*Architecture choice in one line: LandSim pairing + GraphCast typed mesh GNN on MPAS cells/edges, residual early→late map, FiLM for NYF and namelist, diffusion/flow as a drop-in denoiser once the pair factory has enough checkpoints.*
