# OceanAISpinup — Prototype Implementation Plan

**Date:** 2026-09-10  
**Headline:** Learn an **early→equilibrium MPAS-Ocean restart operator** — not a weather diffusion model.  
**Owner (prototype):** Dali — build a working end-to-end workflow and a small model, then **hand the plan and code to the team and advise**.  
**Data freeze:** Kang’s Frontier QU240 dump, re-inspected 2026-09-10 (`OceanAISpinup_Start_Report.md`).  
**Code (pilot, 2026-09-10):** `oceanai/` + `python -m oceanai.run_prototype --stage all` — see `prototype/README.md`.

This note is the **operational** plan. Architecture background stays in `OceanAISpinup_Implementation_Plan.md`. Diffusion go/no-go stays in `OceanAISpinup_Diffusion_Evaluation.md`. After the prototype ships, those docs plus this one are the handoff packet.

---

## 1. Project in one sentence

Map a **year ~50 QU240 restart** (deep T/S) plus cyclic NYF forcing and mesh geometry to a **year ~600 restart**, write it back into MPAS-Ocean, and show that it beats persistence on deep temperature and OHC 2000 m–bottom.

\[
\hat x_{600} = x_{50} + f_\phi(x_{50},\, F_{\mathrm{NYF}},\, \theta,\, G)
\quad\text{on } k=46\ldots 60
\]

The prototype proves the **contract** (data → model → restart → QC). It does not need to be the best GNN, support edges, or sample ensembles.

---

## 2. Roles after the prototype

| Person | During prototype (now) | After handoff (Dali advises) |
|---|---|---|
| **Dali** | Design + implement the e2e spine and a tiny residual GNN | Advisor: review PRs, metrics, restart contract, what *not* to build |
| **Olawale** | Consult on LandSim `dataGEN` / scaler / writeback patterns | Own pair factory, scalers, training loop hardening |
| **Alice** | Confirm OHC as near-eq index (already in docs) | Own scientific QC: OHC thresholds, maps, holdout interpretation |
| **Hyun** | Data already staged; answer “more years?” | Own MPAS-Analysis, forward smoke test, extra restarts if exported |

Dali does **not** keep implementing Track B/C, multi-mesh, or production training after handoff unless the advisor role requires a design call.

---

## 3. Dataset the prototype is allowed to use

All paths under `/lustre/orion/cli115/world-shared/hgkang/data4others/Dali/`.

| Stream | Use in prototype |
|---|---|
| `QU240_Restart_Hist_051-055/restart/` (60 rst) | **X** — early state |
| `QU240_Restart_Hist_601-605/restart_files/` (60 rst) | **Y** — late state |
| `remapped_datm/QU240-NYF/remapped/` | **F** — monthly NYF on the same 7153 cells |
| Matching `timeSeriesStatsMonthly` + OHC AM | **QC only** — not Y, not writeback |
| `601-605/mesh/ocean.QU.240km.151209.nc` | Optional graph source (restart also has connectivity) |

**Pairs:** month-aligned `005y-MM → 060y-MM`, Δ = 550 yr, **60** total.  
**Split:** train **51–54 → 601–604** (48); hold out **55 → 605** (12).  
**Jan-1 subset** (5 pairs) is the smoke path: implement e2e on `0051-01 → 0601-01` first, then scale to 48.

Ignore: `250926_init_data/`, `rst.0661`/`0681`, coupler fluxes, `presaero`, 1-month sliding pairs as training data.

NYF **cycles** and `mpaso_in` is **one** case: encode \(F\) and \(\theta\) but do not expect them to explain holdout skill.

---

## 4. Prototype definition of done (Dali)

A reviewer can run **one documented command sequence** on Frontier and get:

1. A pair table (`pairs/index.parquet`) with train/holdout flags.
2. Persistence RMSE for **0051-01-01 → 0601-01-01** on deep T (area × thickness weighted) and global OHC 2000 m–bottom.
3. A trained cell-only residual GNN checkpoint (small: ~8 MP steps, latent 64–128 is enough).
4. A **written restart** `*.ml.nc` that:
   - is a copy of the template X restart;
   - overwrites only deep `temperature` and `salinity` (k=46…60, valid columns);
   - keeps `layerThickness`, `normalVelocity`, barotropic auxiliaries, mesh, `xtime` from the template (or sets `xtime` to the Y timestamp if you prefer a 600-yr stamp — **document which**);
   - opens with `ncdump -h` and has no fill-value storms in overwritten levels.
5. A one-page `prototype/README.md`: commands, metrics table (persistence vs model on holdout), known limitations.

If holdout does **not** beat persistence, the prototype still **ships** if the workflow is complete and the metric is honest. Skill is the next team’s job; the contract is yours.

**Out of prototype scope:** edge velocity, diffusion/flow, dense transformer, multi-horizon Δ, N-day MPAS forward (Hyun after handoff), second mesh, IAF.

---

## 5. End-to-end workflow (what you implement)

```
Kang Dali/ tree
    │
    ├─► 1. pair_index     60 rows, split flag (portable JSON; no Lustre paths)
    ├─► 2. deep_mask      k=46…60 from rst.0051-01-01
    ├─► 3. mesh_graph     cellsOnCell → edge_index (once)
    ├─► 4. datm_monthly   12 × cells × fields (once; clamp q_10)
    ├─► 5. extract_pairs  npz: x_t, y, mask  (Jan-1 first, then 48)
    ├─► 5b. pack_aiready  portable tensor pack + tar for a second GPU cluster
    ├─► 6. scalers        fit on train only
    ├─► 7. baseline       persistence (+ optional late-month climatology)
    ├─► 8. train          residual GNN, Huber, area×h weights
    ├─► 9. infer          holdout 0055-01 (and optionally all 12)
    └─► 10. write_restart copy template, overwrite deep T/S
              │
              ▼
         qc: ncdump + OHC from ML restart vs Y vs persistence
```

Step **5b** (`python -m oceanai.data.pack_aiready`) is the extra export: tensors + graph + monthly NYF + scalers + persistence, not the 19 GB raw dump. Destination cluster sets `OCEANAI_PROCESSED` to the unpacked pack. Details: `data/docs/AIREADY_DATASET.md`.

Processed artifacts (not git):

```
/lustre/orion/lrn105/proj-shared/wangd/AI4MPAS/data/processed/QU240/   # Frontier working extract
  mesh_graph.npz
  deep_mask.npz
  datm_monthly.npz
  scalers/
  pairs/index.json
  pairs/*.npz
  baselines/persistence.json
  checkpoints/track_a_proto.pt
  restarts_ml/rst.0055-01-01.ml.nc

data/aiready/QU240/   # transfer tree (same tensors; checksums; optional X template)
data/aiready/OceanAISpinup-QU240-aiready-v1.0.0.tar.gz
```

Code in this repo (git):

```
oceanai/
  paths.py                 # Dali prefixes; single source of truth
  mesh/{deep_mask,graph}.py
  data/{pair_index,extract,datm_encoder,scalers,dataset,build_processed,pack_aiready}.py
  baselines/persistence.py
  models/residual_gnn.py   # cell-only; unused FiLM slots OK
  io/write_restart.py
  qc/ohc.py
  run_prototype.py         # one entry: index → train → writeback → metrics
prototype/README.md        # how to run; metrics; handoff notes
```

Login-node `python3` has no netCDF4. Use `cray-python` plus a user env with `netCDF4`/`xarray` and PyTorch (or JAX). `ncdump` is at `/opt/cray/pe/netcdf/4.9.0.7/bin/ncdump`.

---

## 6. Model card (prototype only)

| Item | Choice |
|---|---|
| Mesh | QU240, 7153 cells, graph from `cellsOnCell` |
| Predict | Deep ΔT, ΔS (15 levels); add to \(x_t\) |
| Freeze | `layerThickness`, shallow T/S, all velocities |
| Condition | Monthly NYF on cells + constant \(\theta\) (FiLM stubs; may be no-ops) |
| Loss | Huber, `areaCell` × `restingThickness`, deep mask |
| Train | 48 pairs; early-stop on holdout OHC or deep-T RMSE |
| Writeback | Template = X restart of that pair; overwrite deep T/S only |

Keep the net **small**. 48 pairs overfit a 256-wide 16-layer GNN. Prototype skill is secondary to a restart that MPAS could ingest.

---

## 7. Dali schedule (build, then stop coding)

Aim for a **short, closed prototype**, then freeze.

| Slice | You build | Exit |
|---|---|---|
| **P0 — 2–4 days** | `paths`, pair index, deep mask, OHC from one X and one Y vs history | `index.parquet` + OHC numbers in `baselines/` |
| **P1 — ~1 week** | Graph, DATM monthly, extract Jan-1 then 48 pairs, scalers, persistence JSON | Persistence 0051-01→0601-01 published |
| **P2 — ~1 week** | Tiny GNN + `run_prototype.py` + writeback + holdout table | `rst.0055-01-01.ml.nc` + `prototype/README.md` |
| **Handoff** | Tag / branch `handoff/prototype-e2e`; walkthrough with Olawale, Alice, Hyun | You switch to advisor |

Do not start P2 until Jan-1 persistence and writeback-of-**truth-Y** (copy Y deep T/S into X template) works. That dry-run proves the restart contract **without** the net.

**Truth-Y writeback test:** overwrite X’s deep T/S with Y’s. OHC of the new file must match Y. If this fails, the GNN is irrelevant.

---

## 8. Handoff packets (what others pick up)

Give people **work, not a research wishlist**. Each packet: goal, inputs, done-when, advisor checkpoints.

### Olawale — data and training hardening

- Production-ize `Ocean_dataGEN`: more QC, scaler versioning, reproducible splits.
- Optional: 1-year same-month pairs as a **separate** loader (not mixed into 550-yr loss).
- Training: logging, seeds, checkpoint policy, config YAML.
- LandSim patterns: `IndividualScalerManager`, multi-task weights if thickness is added later.

**Done when:** a second person can retrain Track A from `prototype/README.md` without asking Dali about paths.

**Advisor reviews:** split leakage, history fields sneaking into Y, mixing Δ=1 month into Δ=550 yr.

### Alice — scientific QC

- Sign off OHC 2000 m–bottom as the spinup index (formula already in docs: ρ₀=1026, cₚ=3996).
- Maps: holdout deep ΔT (truth, persistence, model); basin RMSE.
- Thresholds: what “near eq” means vs year 605 (not vs 0681).
- Intra-window spread of Y given month (feeds the later diffusion go/no-go).

**Done when:** a short QC note attached to the prototype metrics.

**Advisor reviews:** whether we claim success too early; deep-only vs full-column story.

### Hyun — data and simulator loop

- Confirm whether years 56–600 (or 20–50) will be exported — **Track C gate**, not prototype.
- MPAS-Analysis on ML vs official 605.
- **After** prototype restart exists: N-day forward from `rst.0055-01-01.ml.nc` vs official `rst.0605-01-01` under the same namelist.

**Done when:** either a forward-test recipe or a documented blocker (need ice/coupler files, etc.).

**Advisor reviews:** do not block the prototype on a full G-case; a short ocean-only forward is enough.

---

## 9. What you advise *against* (unless data changes)

Say this explicitly at handoff so the team does not “upgrade” the prototype into a dead end:

1. **Do not train diffusion / GenCast** on 60 NYF pairs.
2. **Do not** interpolate ocean T/S to lat–lon for a ViT/UNet.
3. **Do not** use LandSim’s per-cell Transformer as the ocean backbone.
4. **Do not** write history `activeTracers_*` into a restart.
5. **Do not** treat DATM or namelist as causal until a second case exists.
6. GraphCast **operator** yes; GraphCast/GenCast **as-is** (icosahedron, 6-hour weather) no.

If they want a generative head later: same GNN + noise FiLM, flow matching, **only if** late-state spread given month is large **and** Hyun delivers many more independent restarts.

---

## 10. Advisor cadence (after handoff)

- Weekly 30 min: metrics table (persistence / climatology / model on holdout T, S, OHC).
- Review any change to `write_restart.py` or the deep mask (restart contract).
- Review any proposal that adds a new training objective or a new grid.
- You do not own GPU debugging or plot polish.

---

## 11. Pointers

| Doc | Use |
|---|---|
| This file | What Dali builds; how the team takes over |
| `OceanAISpinup_Start_Report.md` | Paths, QC numbers, pair recipes |
| `data/docs/FRONTIER_QU240_ARCHIVE.md` | Archive layout |
| `OceanAISpinup_Implementation_Plan.md` | Full architecture / later WPs |
| `OceanAISpinup_Diffusion_Evaluation.md` | Why not GenCast-first |
| `data/OceanSpin_sample/restart/mpas_ocean_header.txt` | Names and dims |

---

*Prototype first. Honest metrics. One restart file. Then advise.*
