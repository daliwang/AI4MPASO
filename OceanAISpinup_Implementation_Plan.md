# OceanAISpinup — Detailed Implementation Plan

**Date:** 2026-08-27  
**Status:** **Schema locked.** Frontier archive has **60 monthly restarts at years 51–55 and 60 at years 601–605** (month-aligned 550-year pairs). Graph/loader unblocked. Track A can start on this pair set. **Not** diffusion-ready (still two 5-year windows, not a full 20–600 trajectory).  
**Companion:** `OceanAISpinup_Development_Plan.md` (GraphCast / LandSim review; Phase 0 closed against this sample)  
**Data docs:** `data/docs/` (DATM, `mpaso_in`, restart deep-ocean selection)  
**Local sample:** `data/OceanSpin_sample/` (headers, namelists, stream XML)  
**Frontier archive:** `/lustre/orion/cli115/world-shared/hgkang/data4others/Dali/` — see `data/docs/FRONTIER_QU240_ARCHIVE.md`

This note answers three questions:

1. Do we know enough about Kang’s MPAS-Ocean sample to design the system?
2. How should the **model** represent the map from early spinup → late spinup, including atmosphere, physics parameters, and especially the **unstructured mesh**?
3. How should we **prepare training data**, including a conditional **diffusion / flow** option?

---

## 1. Direct answer: is Kang’s data enough?

**Enough to lock names, dimensions, graph construction, DATM encoding, namelist tokens, deep-mask, OHC constants, and a single-mesh prototype loader. Not enough to train a model that uses atmospheric forcing and physics parameters as causal inputs, and not enough pairs to train diffusion.**

| Question | What we have (this repo) | Remaining gap |
|---|---|---|
| Mesh topology | Restart header **and** Frontier `rst.0051-01-01` / `rst.0601-01-01`: `nCells=7153`, `nEdges=22403`, `nVertices=15211`, `nVertLevels=60`; incidence is in the restart. Standalone mesh: `…/601-605/mesh/ocean.QU.240km.151209.nc` | None for QU240 |
| Prognostic names | Locked: `temperature`, `salinity`, `layerThickness`, `normalVelocity` (same on 0051 and 0601) | None for v1 |
| Deep-ocean target | k = 46…60; ρ₀=1026, cₚ=3996; AM + monthly OHC files on Frontier | Script: restart OHC vs `oceanHeatContent2000mToBot` |
| Early vs late pairing | **On Frontier:** 60 monthly rst years **51–55** and 60 monthly rst years **601–605**. Month-aligned **60 pairs with Δ = 550 yr**. Format samples 0661/0681 are extra, not this tree. | Continuous years 56–600 (or 20–50) if Hyun has them |
| Atmosphere | CORE2 NYF; **already remapped to oQU240** (`ncol=7153`) under `remapped_datm/QU240-NYF/remapped/` | NYF still cycles — F does not differ across pairs |
| Physics configs | `mpaso_in` + `mpaso_variables` with numeric values | One case — θ not identifiable |
| Training volume | 60 long-horizon pairs + short-Δ pairs inside each 5-year window | More years for diffusion / generalization |

**Implication for architecture:** on the current sample, atmosphere and namelist are **run-level metadata**, not per-example features. The mesh **is** the spatial operator and must be first-class. Forcing and parameters become informative only when the dataset spans **multiple physics settings, forcings, or meshes**.

The rest of this plan is written so a QU240 MVP can start now against one restart file, and so later multi-run data plugs in without changing the IO contract.

---

## 2. Local sample inventory (`data/OceanSpin_sample/`)

Schema authority is this tree, copied from Hyun’s NERSC sample. Large NetCDF payloads are **not** versioned (`.gitignore`: `data/**/*.nc`). Headers, namelists, stream XML, and selection lists **are** versioned.

### 2.1 Case identity (from restart/history global attributes)

| Item | Value |
|---|---|
| Case | `v3.GMPAS-NYF_QU240` |
| Username / host (sample files) | `hgkang` / `miller` |
| MPAS git | `be7af980a1` |
| Ocean mesh | Quasi-uniform QU240 (~240 km), spherical C-grid (`on_a_sphere=YES`, `sphere_radius=6371229`) |
| Vertical | 60 levels, `config_init_vertical_grid_type = z-star` |
| Atmosphere | DATM `CORE2_NYF` (prescribed, `taxmode=cycle`) |
| Calendar | `noleap` |
| Ocean `config_dt` | `01:00:00` (barotropic `config_btr_dt = 0000_00:03:00`) |
| Integrator | `split_explicit_ab2` |
| Partition prefix (namelist) | `…/ocn/mpas-o/oQU240/partitions/mpas-o.graph.info.230422.part.` |
| NERSC pointer | `/global/cfs/cdirs/m4259/hgkang/data_for_others/Dali_OceanSpinup_sample` |
| Analysis | [MPAS-Analysis GMPAS-NYF_QU240](https://portal.nersc.gov/project/e3sm/hgkang/ImPACTS/AI_spinup/v3.GMPAS-NYF_QU240/www/) |

### 2.2 Files in the local sample tree

**Versioned (in git)**

| Path | Role |
|---|---|
| `restart/mpas_ocean_header.txt` | **Authoritative** restart names, dims, mesh connectivity, fill values |
| `history/history_header.txt` | Monthly history names; OHC / SSH / MLD diagnostics |
| `datm_NYF/ncep_header.txt` | NCEP T62 NYF 6-hourly fields (`time=1460`) |
| `mpaso_in` | Full ocean namelist (physics values) |
| `mpaso_variables` | Selected namelist tokens for AI conditioning |
| `restart_variables` | Selected deep-ocean restart fields |
| `datm_in` | DATM namelist (`CORE2_NYF`, bilinear, cycle) |
| `datm.streams.txt.CORE2_NYF.NCEP` | NCEP stream: `u_10,v_10,t_10,slp_,q_10,dn10` |
| `datm.streams.txt.CORE2_NYF.GXGXS` | Precip stream: `prc` → `prec` |
| `datm.streams.txt.CORE2_NYF.GISS` | Radiation: `lwdn,swdn,swup` |
| `datm.streams.txt.presaero.clim_2000` | Optional aerosol deposition |

**Named in headers / docs, not in git (bring onto the machine to implement WP1)**

| File | Time stamp | Role |
|---|---|---|
| `v3.GMPAS-NYF_QU240.mpaso.rst.0661-01-01_00000.nc` | 0661-01-01 | Format exemplar (late-run restart; **not** year ~50) |
| `v3.GMPAS-NYF_QU240.mpaso.rst.0681-01-01_00000.nc` | 0681-01-01 | Format exemplar, +20 yr |
| `v3.GMPAS-NYF_QU240.mpaso.hist.am.timeSeriesStatsMonthly.0678-11-01` | 0678-11 | One monthly history (OHC QC) |
| `nyf.ncep.T62.050923.nc` | NYF year, 6-hourly | DATM winds / T / SLP / q / density |
| `nyf.gxgxs.T62.051007.nc` | 12 months | DATM precip |
| `nyf.giss.T62.051007.nc` | monthly | DATM radiation |
| `domain.lnd.T62_oQU240.240513.nc` | static | T62 → oQU240 remap domain (`datm_in`) |

Do **not** treat 0661 → 0681 as the scientific 50 yr → 600 yr pair. Those two files prove format and a 20-year residual.

**Frontier payloads (Hyun, 2026-08):** `/lustre/orion/cli115/world-shared/hgkang/data4others/Dali/` — full inventory in `data/docs/FRONTIER_QU240_ARCHIVE.md`.

| Window | Restart dir | Files | Dates |
|---|---|---|---|
| Early (~50 yr) | `QU240_Restart_Hist_051-055/restart/` | 60 × 57 MB | monthly, **0051-01 … 0055-12** |
| Late (~600 yr) | `QU240_Restart_Hist_601-605/restart_files/` | 60 × 57 MB | monthly, **0601-01 … 0605-12** |

Month-aligned map `0051-MM → 0601-MM` (and the four following years) is **60 pairs at Δ = 550 yr**. Schema matches the locked header (`xtime` checked on 0051-01-01 and 0601-01-01). DATM is already on cells: `remapped_datm/QU240-NYF/remapped/`.

### 2.3 Restart fields — **use header names**

From `restart/mpas_ocean_header.txt`. Fill value `9.96920996838687e+36`; T/S/h use `missing_value_mask = cellMask`; velocity uses `edgeMask`. Masks are **not** stored as arrays — derive from `minLevelCell` / `maxLevelCell`.

| Role | NetCDF name | Shape | Notes |
|---|---|---|---|
| Potential temperature | `temperature` | `Time, nCells, nVertLevels` | °C |
| Salinity | `salinity` | `Time, nCells, nVertLevels` | 1e-3 |
| Layer thickness | `layerThickness` | `Time, nCells, nVertLevels` | m |
| Edge-normal velocity | `normalVelocity` | `Time, nEdges, nVertLevels` | m/s |
| Barotropic velocity | `normalBarotropicVelocity` | `Time, nEdges` | split-explicit auxiliary; copy from template in v1 |
| Column depth | `bottomDepth` | `nCells` | m, positive down |
| Active levels | `minLevelCell`, `maxLevelCell` | `nCells` | 1-based indices |
| Reference z | `refBottomDepth` | `nVertLevels` | m |
| Resting thickness | `restingThickness` | `nCells, nVertLevels` | ALE reference |
| Model time | `xtime` | `Time, StrLen` | `YYYY-MM-DD_HH:MM:SS` |

Deep mask (this mesh):

```
refBottomDepth[k] > 2000  and  k <= maxLevelCell[i]  and  bottomDepth[i] > 2000
```

with **k = 46…60** (1-based; 0-based 45…59). That is **15 deep levels**.  
First deep level: `refBottomDepth[46] ≈ 2074.87 m`. Bottom: `refBottomDepth[60] ≈ 5499.99 m`.

**`ssh` is not a restart variable** in this header. History has `timeMonthly_avg_ssh`. Column thickness / SSH consistency for writeback goes through `layerThickness` (and MPAS’s own SSH reconstruction). Keep `normalBarotropicVelocity` and other time-stepper auxiliaries from the template restart.

### 2.4 History diagnostics (validation only — not writeback)

From `history/history_header.txt` (`nOceanRegions=7`, same `nCells` / `nVertLevels`).

| History name | Use |
|---|---|
| `timeMonthly_avg_oceanHeatContent2000mToBot` | Primary deep-OHC target (J per cell) |
| `timeMonthly_avg_oceanHeatContentSfcTo700m` | Shallow band (matches `Ocean_EQ.png`) |
| `timeMonthly_avg_oceanHeatContent700mTo2000m` | Mid band |
| `timeMonthly_avg_oceanHeatContentSfcToBot` | Full-column OHC |
| `timeMonthly_avg_activeTracers_temperature` / `_salinity` | Monthly T/S (names differ from restart) |
| `timeMonthly_avg_layerThickness` | Monthly thickness |
| `timeMonthly_avg_ssh` | SSH (history only) |
| `timeMonthly_avg_tThreshMLD` / `dThreshMLD` | Mixed-layer sanity |
| `timeMonthly_avg_BruntVaisalaFreqTop` | Stratification QC |

OHC from restart (must match the 2000 m–bottom history field after a global sum):

\[
\mathrm{OHC}_{2000}^{\mathrm{bot}}
= \rho_0 c_p \sum_i \sum_{k\in\mathrm{deep}} T_{i,k}\, h_{i,k}\, A_i
\]

with \(\rho_0=1026\) (`config_density0`) and \(c_p=3996\) (`config_specific_heat_sea_water`).

Do **not** train on history `windStress*`, `latentHeatFlux`, `rainFlux`, etc. Those depend on SST/ice.

### 2.5 Atmosphere (DATM), not coupler fluxes

| Stream | File | Grid | Time | Variables |
|---|---|---|---|---|
| NCEP | `nyf.ncep.T62.050923.nc` | T62, 94 × 192 | 6-hourly NYF (`time=1460` = 365×4) | Tier-1: `u_10`, `v_10`, `t_10`, `slp_`; Tier-2: `q_10`, `dn10` |
| GXGXS | `nyf.gxgxs.T62.051007.nc` | T62 | monthly climatology (12) | `prc` |
| GISS | `nyf.giss.T62.051007.nc` | T62 | monthly | `swdn`, `swup`, `lwdn` |

DATM remap: `mapalgo=bilinear`, `vectors=u:v`, domain `domain.lnd.T62_oQU240.240513.nc`.

Because NYF **cycles**, a 50-year and a 600-year restart see the **same annual forcing**. The ocean still changes because of **slow internal adjustment**. Forcing still belongs in the model as a **condition** (the map is “under this repeating climate”), but it will not differentiate samples until we have IAF, different NYF products, or flux perturbations.

### 2.6 Physics parameters (locked values, one case)

From `mpaso_variables` / `mpaso_in`. Encode as a global token vector. With one `mpaso_in`, store once as run metadata.

| Group | Locked values |
|---|---|
| Momentum visc | `mom_del2=4000` (on), `mom_del4=2e14` (on) |
| Redi / GM | both `constant`, κ=`900` |
| Submesoscale | enabled; `ce=0.08`, `tau=172800` |
| CVMix | KPP + convection + shear on; background visc `1e-4` |
| Bulk coupling | wind stress + thickness flux on; precip scale `1.0` |
| Numerics | tracer adv order 3; monotonic flux/remap; flux-form vertical |
| Drag | implicit constant, coeff `1e-3` |
| EOS / PGF | `jm` / `Jacobian_from_TS` |
| S restoring | piston `1.585e-6`, max ΔS `0.5`, off under ice |

### 2.7 Mesh is the major difference

LandSim treats each land cell as IID. GraphCast uses a **separate** icosahedral mesh and keeps loss on lat–lon. MPAS-Ocean **already is** the unstructured C-grid. Connectivity lives **in the same restart file** as the state.

| Entity | Count (QU240) | Carries |
|---|---|---|
| Cells (primal polygons) | 7153 | `temperature`, `salinity`, `layerThickness`, `areaCell`, bathymetry |
| Edges | 22403 | `normalVelocity`, `dcEdge`, `dvEdge`, `fEdge` |
| Vertices (dual triangles) | 15211 | optional vorticity / reconstruction |

Connectivity that **must** become the graph (from the restart):

- `cellsOnCell`, `nEdgesOnCell`, `edgesOnCell`, `cellsOnEdge`
- `areaCell`, `dcEdge`, `dvEdge`, `angleEdge`, `latCell`, `lonCell`, `xCell,yCell,zCell`, `fCell` / `fEdge`
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

This is **not** GraphCast’s 6-hour rollout. Δ can be 20 yr (sample pair), 50 yr, or ~550 yr (intended). The model is a **spinup operator**, closer to LandSim’s early→eq map, but with spatial coupling on \(G\).

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
MPAS restart (same file as state)
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

For NYF, **use Hyun’s remapped files** (`nyf.ncep.oQU240.*`, `ncol=7153`) rather than re-running T62→mesh. They were built with **area-average** (`map_T62_TO_oQU240_aave.151209.nc`), not `datm_in` bilinear. Aggregate 6-hourly NCEP to a 12-month climatology (or annual mean) before the GNN. Do not feed 1460×T62 raw 6-hour fields into the ocean GNN.

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
| G | Restart geometry | Graph cache keyed by mesh ID |
| QC | History optional | Deep OHC time series for the same years |

**Identity join on cell/edge indices** when mesh matches. No lat/lon KD-tree.

### 5.2 How to get enough pairs from limited spinups

Kang’s **intended** pairing is one map: 50 yr → 600 yr. A single pair cannot train a network. On Frontier we now have **two 5-year monthly windows**:

| Recipe | Pair definition | N on this archive | Purpose |
|---|---|---|---|
| **Long-horizon (primary)** | Month-aligned 005y-MM → 060y-MM | **60** at Δ = 550 yr | The scientific spinup operator |
| **Jan-1 subset** | 0051-01 → 0601-01, …, 0055-01 → 0605-01 | 5 | Cleaner annual baseline |
| **Sliding monthly** | Consecutive months inside 51–55 or 601–605 | 59+59 | Short residual / IO tests |
| **Same-month +1 yr** | Inside a window | 48+48 | Seasonal-aligned 1-year Δ |
| **Physics / forcing / mesh ensembles** | Later | 0 here | Makes θ and F identifiable |

**Still not in this dump:** years 56–600 (or 20–50) as a continuous restart series. If only these two windows exist, **do not start diffusion**; train Track A on the 60 long-horizon pairs (and short-Δ pairs as auxiliary), hold out e.g. year 55 / 605 or a basin.

### 5.3 Normalization and QC

- Fit scalers on **train years only**.
- Per-variable min-max or z-score; log-scale for `config_mom_del4`-class coefficients in \(\theta\).
- Drop cells with `bottomDepth ≤ 2000` from the loss (or weight 0).
- Reject samples with fill-value storms / NaNs in deep T/S.
- Verify OHC with the formula in §2.4 vs history `timeMonthly_avg_oceanHeatContent2000mToBot` (global sum).

### 5.4 On-disk layout (suggested)

```
data/processed/QU240/
  mesh_graph.npz          # once, built from any QU240 restart
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

Report area-weighted RMSE/bias for deep T, S, and OHC 2000 m–bottom. Any GNN/diffusion must beat (1) and (2). First number to publish: persistence **0051-01-01 → 0601-01-01** on deep T (then the other 59 aligned months).

---

## 6. Implementation work packages

### WP0 — Schema lock — **done locally**

- [x] Freeze NetCDF names to the restart header (`temperature`, `salinity`, `layerThickness`, `normalVelocity`).
- [x] Selection lists: `data/OceanSpin_sample/restart_variables`, `mpaso_variables`; docs in `data/docs/`.
- [x] Deep mask k=46…60; OHC ρ₀/cₚ from namelist; history OHC field names.
- [x] DATM stream map and NYF cycle semantics; remapped oQU240 files on Frontier.
- [x] Inventory Hyun’s Frontier windows: years **51–55** and **601–605** monthly (`data/docs/FRONTIER_QU240_ARCHIVE.md`).
- [x] Confirm ~50 yr and ~600 yr paths: `rst.0051-*` and `rst.0601-*` (not 0661/0681).
- [ ] Ask Hyun whether more years exist between 55 and 601 (or after 605).

### WP1 — Graph + dataset (1–2 weeks; starts as soon as one restart `.nc` is local)

- [ ] `mpas_mesh_to_typedgraph.py` on `rst.0051-01-01` (unit test: nCells=7153, degree ≤ 6, area sum vs 4πR²).
- [ ] Deep-mask builder from `refBottomDepth` / `maxLevelCell`.
- [ ] Pair index: 60 month-aligned 005y-MM → 060y-MM; optional short-Δ inside each window.
- [ ] DATM: load `remapped_datm/QU240-NYF/remapped/` (already on cells); monthly-mean NCEP.
- [ ] Baseline RMSE: persistence 0051-01-01 → 0601-01-01 on deep T (then all 60 aligned months).

### WP2 — Deterministic GNN MVP (Track A)

- [ ] Cell-only residual GNN: predict deep \(\Delta T,\Delta S\) (thickness frozen or predicted).
- [ ] Area × thickness weighted loss; FiLM stubs for \(F,\theta,\Delta\).
- [ ] Copy-template restart writeback for predicted fields only (keep `normalBarotropicVelocity` and auxiliaries from template).
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
| Mesh | QU240 only (`nCells=7153`) |
| State | Deep k=46–60 `temperature`, `salinity`; optional `layerThickness` |
| Velocity | Deferred (Track A cell-only) |
| Atmosphere | NYF 12-month means remapped to cells (condition, constant for this case) |
| Config | `mpaso_variables` vector (condition, constant for this case) |
| Lead \(\Delta\) | Conditioning token; train on all available checkpoint gaps |
| Processor | 10–12 step interaction GNN, 128–256 latent, residual |
| Loss | Huber, `areaCell` × `restingThickness` weights, deep mask |
| Generative | **Interface ready** (noise/FiLM slot); **not trained** until pair count allows |
| Output | Residual add + mask → restart overwrite of selected 3D fields |

---

## 8. Risks (implementation-specific)

| Risk | Mitigation |
|---|---|
| Two format restarts (0661/0681) mistaken for a dataset | Inventory the full spinup; pair factory along time |
| History vs restart name mismatch (`activeTracers_temperature` vs `temperature`) | Restart header is writeback source of truth; history is QC only |
| Learning \(F\) or \(\theta\) from one NYF case | Encode them, but evaluate only on ocean-state skill until ensembles exist |
| Interpolating ocean to lat–lon “to use ViT/diffusion-on-images” | Disallowed for ocean state; mesh operators only |
| Diffusion on 1–20 samples | Overfit; keep Track A until O(10²)+ pairs |
| Unusable restart (missing auxiliaries) | v1 overwrites only selected 3D fields; keep other restart vars from template |
| Deep-only prediction vs full-column restart | Document: ML owns k>2000 m; copy shallow levels from \(x_t\) or template |
| SSH not in restart | Do not invent an `ssh` variable; thickness writeback only |

---

## 9. What to do next on this machine / NERSC

Schema dump is **done**. Two 5-year monthly windows are **on Frontier**. Remaining:

1. Build the graph from `…/051-055/restart/…rst.0051-01-01_00000.nc` (WP1).
2. Publish persistence RMSE 0051-01-01 → 0601-01-01 on deep T (`areaCell` × thickness).
3. Stand up the 60-pair index (month-aligned 550-year map); hold out year 55/605 or a basin.
4. Load remapped NYF from `remapped_datm/QU240-NYF/remapped/` (do not re-grid T62 for v1).
5. Ask Hyun if years 56–600 (or 20–50) will be exported; Track C waits on that.
6. Only then train Track A — 60 long-horizon pairs is a prototype set, not a diffusion set.

---

## 10. References in this repo

- `OceanAISpinup_Implementation_Slides.pptx` — 13-slide team deck (regenerate with `generate_implementation_slides.py`)
- `OceanAISpinup_Development_Plan.md` — GraphCast vs LandSim transfer; Phase 0 closed
- `data/docs/FRONTIER_QU240_ARCHIVE.md` — Hyun’s Frontier 51–55 / 601–605 inventory
- `data/docs/README.md` — variable-selection index
- `data/docs/DATM_FORCING_VARIABLES.md`
- `data/docs/MPASO_PHYSICS_CONFIG_INPUTS.md`
- `data/docs/RESTART_DEEP_OCEAN_STATE.md`
- `data/OceanSpin_sample/restart/mpas_ocean_header.txt` — **authoritative names and dims**
- `data/OceanSpin_sample/history/history_header.txt` — OHC diagnostics
- `data/OceanSpin_sample/mpaso_in` — namelist values including ρ₀, cₚ
- `Ocean_EQ.png` — deep OHC spinup motivation

*Architecture choice in one line: LandSim pairing + GraphCast typed mesh GNN on MPAS cells/edges, residual early→late map, FiLM for NYF and namelist, diffusion/flow as a drop-in denoiser once the pair factory has enough checkpoints.*
