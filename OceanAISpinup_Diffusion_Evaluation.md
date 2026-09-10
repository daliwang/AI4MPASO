# Evaluation: Does a diffusion model make sense for OceanAISpinup?

**Date:** 2026-09-10  
**Audience:** Dali / AI4MPAS review  
**Question:** Given GraphCast, GenCast, LandSim, and Kang’s QU240 dump, is the current diffusion decision sound?  
**Decision under review** (as documented in `OceanAISpinup_Implementation_Plan.md` and `OceanAISpinup_Start_Report.md`):

1. **Do not train a diffusion / flow model on the current Frontier pairs.**
2. **Start with a deterministic residual mesh GNN (Track A), LandSim-style pairing and restart writeback.**
3. **Keep a GenCast-style generative wrapper as a later option** (same backbone as denoiser; prefer flow matching over vanilla DDPM), only after many more independent \((x_t, x_{t+\Delta})\) pairs.

**Verdict:** **Yes — that decision is the right one.** GraphCast (deterministic GNN) and LandSim (early→equilibrium, restart contract) are the correct parents of v1. GenCast’s diffusion objective is the wrong first model for this task and this data. Keeping a generative *interface* is optional insurance, not a scientific requirement of deep-ocean spinup.

**Sources for this review**

- In-repo GraphCast/LandSim code review: `OceanAISpinup_Development_Plan.md` §§3–5 (from `TypedGraph`, `DeepTypedGraphNet`, LandSim `dataGEN` / `ai_predictions_to_restart.py`). The vendor trees are **not** on Frontier (`graphcast/` gitignored; LandSim lived on a laptop path).
- GraphCast: Lam et al., *Science* 2023 — deterministic GNN, 6-hour residual, ERA5 1979–2017.
- GenCast: Price et al., *Nature* 2024 / arXiv:2312.15796 — conditional diffusion, 12-hour steps, 15-day ensembles, ~40 years of ERA5.
- LandSim / AI4BGC: E3SM land spinup (Wang et al.); GitHub `daliwang/LandSim` — Transformer, multi-task MSE, restart overwrite, **not** diffusion.
- Frontier data: `OceanAISpinup_Start_Report.md` (60 month-aligned 550-year pairs, NYF cycles).

---

## 1. What each codebase actually is

| | **GraphCast** | **GenCast** | **LandSim** | **OceanAISpinup (this project)** |
|---|---|---|---|---|
| Scientific job | Next 6 h of **weather** | **Distribution** of next 12 h of weather; 15-day ensemble | Early land spinup → **near-eq CNP pools** | Early ocean restart (~50 yr) → late restart (~600 yr) |
| Time scale | Hours–days | Hours–days | Decades–millennia of BGC | Centuries of deep T/S |
| Target uniqueness | Chaotic; MSE learns the **mean** | Intentionally **multi-modal / spread** | Near-unique attractor per cell + climate | Slow, nearly monotonic deep adjustment (OHC 2000 m–bot) |
| Objective | Weighted MSE residual | EDM / denoising score | Multi-task MSE / Huber | **v1: same as GraphCast+LandSim (MSE residual)** |
| Backbone | Typed GNN on **icosahedral** mesh; loss on lat–lon | Same encoder/decoder; **graph transformer** processor | Per-cell Transformer over **modality tokens** | **MPAS native cells/edges** (not icosahedron, not IID cells) |
| Data volume | ~40 yr ERA5, 6-hourly | Same order; millions of steps | Many land cells × spinup campaigns | **48 train / 12 holdout** long-horizon pairs |
| Deliverable | Forecast fields | Ensemble forecast | ELM restart NetCDF | MPAS-Ocean restart NetCDF |

Two different Google models are easy to conflate because they share a repo and a mesh. **GraphCast is not a diffusion model.** GenCast added diffusion *because weather ensembles need spread*. LandSim never needed that: land BGC spinup is a constrained map onto a restart contract.

Ocean spinup sits with **LandSim on the workflow** and with **GraphCast on the spatial operator**. It does not sit with GenCast on the **training objective**, unless you later show that \(p(x_{t+\Delta}|x_t)\) is actually broad.

---

## 2. Re-read GraphCast — what to steal, what not to

GraphCast’s physics GNN does **not** run on the ERA5 lat–lon grid. It:

1. Encodes stacked grid fields → icosahedral mesh (`grid2mesh_gnn`).
2. Does multi-scale message passing on merged triangular meshes (`mesh_gnn` / `DeepTypedGraphNet`).
3. Decodes back to the grid (`mesh2grid_gnn`).
4. Predicts a **normalized residual** of the next 6-hour state; trains with latitude- and level-weighted MSE; can unroll with `hk.scan`.

**Transfers to MPAS (keep):**

- `TypedGraph` + typed InteractionNet (cells vs edges vs vertices).
- Geometric edge features (local frames; for us: `dcEdge`, `dvEdge`, `angleEdge`, `areaCell`).
- Residual prediction \(\hat x_{t+\Delta} = x_t + \Delta x\).
- Encode–process–decode wrapping.
- Vertical stacked as **channels** (our k=46…60 → 15 levels), not a 3rd graph.

**Does not transfer:**

- Icosahedral `merge_meshes` / `faces_to_edges` as the dynamics mesh — **MPAS already is the unstructured C-grid**.
- Grid2Mesh / Mesh2Grid as the primary path (optional later only for T62 DATM, and Kang already remapped DATM to cells).
- Homogeneous `mesh_nodes` for all prognostics — tracers live on cells, `normalVelocity` on edges.
- `normalized_latitude_weights` — use `areaCell` × thickness.
- 6-hour autoregressive weather rollout. Our Δ is **550 years**, one shot.

GraphCast’s success is evidence that **a deterministic mesh GNN + residual MSE** can learn a geophysical operator when the graph matches the physics. That is Track A. It is **not** evidence that the next model must be generative.

---

## 3. Re-read GenCast — why they used diffusion, and why that reason is weak here

GenCast (Price et al. 2024) kept GraphCast’s encoder/decoder and replaced the processor with a **k-hop graph transformer**. The training change that matters is the **objective**:

- Corrupt the **target** weather state with noise (EDM / Karras).
- Denoise, **conditioned on** \((x_t, x_{t-1})\).
- Sample different noise seeds → a **50-member ensemble**.
- Trained on ~40 years of ERA5 at 12-hour steps (~10⁴–10⁵ independent weather states).

They did this because **medium-range weather is chaotic**. A deterministic MSE model (GraphCast) is over-dispersed in the mean and **under-dispersed as an ensemble** unless you add ad hoc IC perturbations. Diffusion is how they represent \(p(x_{t+\Delta}|x_t)\) when that conditional is wide and the user needs **risk / extremes**.

Map that argument onto QU240 NYF spinup:

| GenCast assumption | OceanAISpinup fact |
|---|---|
| Next-state distribution is broad (chaos, storms) | Deep T/S over 550 yr under **cycled NYF** is a slow, nearly unique adjustment (`Ocean_EQ.png`: 2000 m–bottom cools persistently) |
| Millions of loosely related samples | **60** month-aligned pairs; 5 consecutive years of the **same** seasonal cycle — highly correlated |
| Forcing and ICs vary across the climatology | \(F\) is one NYF year; \(\theta\) is one `mpaso_in`; \(G\) is one mesh |
| Product is an ensemble forecast | Product is **one** restart that MPAS must integrate without blowing up |
| QU240 mesoscale | Weakly resolved; not a storm-resolving ensemble problem |

A diffusion model on 48 training pairs will not learn a physically meaningful score. It will memorize the train years’ residuals and look stochastic. That is the opposite of GenCast, which had a dense sampling of the attractor.

**If** Hyun later delivers a long restart trajectory or physics/forcing ensembles, **and** a diagnostic shows large spread in late deep T given the same month and similar \(x_t\), **then** wrapping Track A as a flow-matching denoiser is the GenCast move. Until that diagnostic is positive, GenCast is a **category error** (weather ensemble ≠ spinup operator).

---

## 4. Re-read LandSim — this is the actual product analogue

LandSim (AI4BGC) learns:

> short / AD-spinup land state + forcings + static descriptors → restart-quality CNP pools → overwrite ELM restart → continue the process model.

It is **deterministic**, per-gridcell, Transformer-over-modalities, multi-task weighted loss, `IndividualScalerManager`, `LandSim_dataGEN` pairing, `ai_predictions_to_restart.py`. Success is **simulator-in-the-loop**: the written restart must run, conserve, and approach NEE≈0.

That is the same **contract** as OceanAISpinup: one-shot early→late, typed restart tensor, N-day (or N-year) MPAS continuation, OHC as the slow index.

What **must not** be copied: LandSim’s IID cell Transformer. Ocean equilibration is nonlocal (circulation, GM, waves). That is why the backbone is GraphCast-typed MPAS GNN, not LandSim’s per-cell attention.

LandSim did **not** use diffusion. Land spinup is an attractor problem. Deep-ocean spinup is closer to that than to 15-day weather. Using GenCast’s objective because “SOTA weather is generative” would drop the LandSim lesson that actually matches the deliverable.

---

## 5. Decision evaluation (point by point)

### 5.1 “Do not train diffusion on Kang’s dump” — **correct**

Independent reasons; either would suffice:

1. **Task.** Conditional \(p(x_{600}|x_{50}, F_{\mathrm{NYF}}, \theta, G)\) is likely **narrow**. MSE on \(\Delta T,\Delta S\) is the right estimator of the spinup operator. Diffusion spends capacity on sampling noise you have not shown exists.
2. **N.** GenCast-scale generative models see \(\mathcal{O}(10^4+)\) states. You have **48** long-horizon train pairs (hold out 12). Adjacent months are not independent. Short-Δ pairs inside 51–55 are a **different** map (1 month ≠ 550 yr) and must not pad the diffusion dataset.
3. **Constant \(F,\theta\).** With NYF cycling, atmosphere cannot identify a conditional. A denoiser conditioned on \(F\) will ignore \(F\). That is fine for Track A (FiLM stub); it makes generative “ensemble given climate” vacuous.
4. **Restart product.** MPAS needs **one** dynamically usable file. Sampling 8 late states and picking by OHC is extra machinery before you can beat persistence.

### 5.2 “Start Track A: residual mesh GNN + LandSim IO” — **correct**

This is the intersection of the two codebases that actually transfer:

```
LandSim pair factory / scalers / copy-template writeback
        +
GraphCast TypedGraph residual GNN on MPAS incidence
        +
areaCell × thickness Huber on deep k=46…60
```

That is GraphCast’s **objective** and LandSim’s **workflow**, with GraphCast’s **mesh idea** rebuilt on `cellsOnCell` rather than an icosahedron.

Success gate (unchanged): beat persistence **0051-01-01 → 0601-01-01** on area-weighted deep T and on OHC 2000 m–bottom, then the year-55 holdout.

### 5.3 “Keep diffusion/flow as a later drop-in denoiser” — **acceptable, not mandatory**

This is the only part I would **soften**, not reverse.

**Keep the interface** (noise-level FiLM slot, residual as the generated field) if it is cheap: one extra embedding in the GNN. That is what GenCast did to GraphCast’s encoder/decoder.

**Do not** treat Track C as the research goal of the first year. A later go/no-go should be **empirical**:

- Compute, on the 60 pairs, the **spread of Y given calendar month** (deep T RMSE of each 605-MM vs the 601–605 monthly climatology, and vs X).
- If month-conditioned late-state variance is small compared with the 50→600 residual, the map is effectively unique → **stop at Track A/B**. Diffusion would only add sampling noise around a mean you already have.
- If variance is large (multi-modal basins, eddy-rich future meshes, IAF, perturbed \(\theta\)), **then** flow matching around the same GNN is justified — and only after \(N \gtrsim 10^2\) **independent** pairs (different years, not 12 months of the same year counted as 12 climates).

Prefer **flow matching / EDM** over vanilla DDPM if you ever train Track C (fewer steps, better for continuous fields). Do not diffuse \(F\) or \(\theta\). Do not interpolate ocean state to lat–lon to “use an image diffusion UNet.”

### 5.4 Decisions that would **not** make sense

| Choice | Why it fails |
|---|---|
| Fine-tune GenCast weights on QU240 | Wrong mesh, wrong variables, wrong Δt, wrong grid |
| ViT / image DDPM on remapped T/S | Destroys `areaCell` and C-grid; LandSim/GraphCast both warn against this |
| LandSim Transformer as ocean backbone | No horizontal coupling |
| GraphCast as-is (grid2mesh on T62, loss on lat–lon) | Ocean state is native unstructured; DATM is already on cells |
| Train diffusion “to get ensembles” from 5 NYF years | Ensembles of the same seasonal cycle, not of spinup uncertainty |
| Mix 1-month history T/S into the 550-yr generative target | Different operators; history ≠ restart |

---

## 6. Recommended architecture in one diagram

```
                    LandSim spine                         GraphCast operator
                    ─────────────                         ─────────────────
  rst.0051  ──►  pair factory, scalers, mask   ──►  cell/edge TypedGraph
  rst.0601       (identity join on nCells)            residual GNN (Track A)
  remapped NYF   monthly F tokens (condition)         FiLM(F, θ) stubs
  mpaso_in       θ vector (condition, constant)
                         │
                         ▼
              ΔT, ΔS on k=46…60  →  copy-template restart
                         │
                         ▼
              persistence / OHC / N-day MPAS test

  later, only if Y|month variance is large and N grows:
              same GNN  +  noise embedding  =  flow-matching denoiser (GenCast wrapper)
```

This is **not** “GraphCast vs LandSim vs diffusion.” It is **LandSim contract + GraphCast GNN**, with GenCast’s generative head **gated**.

---

## 7. What to measure before anyone revisits Track C

Add these to Sprint 1 baselines (`OceanAISpinup_Start_Report.md`); they decide whether diffusion is even interesting:

1. Persistence RMSE (already planned).
2. **Seasonal climatology of Y:** mean of train late states by month → RMSE to holdout 605. If this is already close to persistence-to-600, the late ocean is a slow attractor + season, i.e. LandSim-like.
3. **Intra-window spread:** std of deep T across years 601–605 for a fixed month, area-weighted. Small std ⇒ little to sample.
4. Residual \(\Delta T = Y-X\) maps: if they are large-scale (basin) not eddy-like, a GNN mean is enough.

Only if (3) is a non-trivial fraction of (1) is a generative model worth the extra sampler.

---

## 8. Bottom line for your review

| Decision | Evaluation |
|---|---|
| Diffusion is the **first** model to train on Kang’s data | **Reject.** Wrong objective for a near-unique spinup map; 48 pairs cannot support a score model. GenCast is not a template for N. |
| Deterministic residual **mesh GNN** first (Track A) | **Accept.** This is GraphCast’s proven operator, on MPAS incidence, with LandSim’s pairing and restart writeback. |
| LandSim cell Transformer as the ocean net | **Reject.** Horizontal coupling is the whole point of using GraphCast. |
| Keep a **later** flow-matching wrapper | **Accept as optional.** Cheap to leave a noise FiLM slot; do not schedule GPU time until spread diagnostics and pair count justify it. |
| “We are building a diffusion model for MPAS-Ocean” as the project headline | **Reframe.** The project is an **early→equilibrium restart operator**. Diffusion is one possible head, not the identity of the work. |

**One sentence:** Your diffusion decision makes sense **if** it means “GraphCast GNN now, GenCast-style sampler only if the late-state distribution is actually wide and we get more independent spinup checkpoints.” It does **not** make sense if it means “start by training DDPM/GenCast on 60 NYF pairs.”

*Code trees for GraphCast/LandSim were not re-cloned on Frontier; module-level mapping follows the existing development-plan review plus the published GraphCast/GenCast/LandSim descriptions. Data constraints follow the 2026-09-10 Frontier audit.*
