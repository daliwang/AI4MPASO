# OceanAISpinup — Frontier Data Audit and How to Start

**Date:** 2026-09-10  
**Audience:** AI4MPAS / ImPACTS (Dali, Alice, Hyun, Olawale)  
**Status:** Kang’s QU240 package on Frontier is **complete for a prototype restart operator**. It is **not** complete for Track C (conditional diffusion / flow).  
**What Dali builds:** `OceanAISpinup_Prototype_Plan.md` (e2e prototype, then advise)  
**Companion:** `OceanAISpinup_Implementation_Plan.md` (architecture, IO contract, work packages)  
**Archive inventory:** `data/docs/FRONTIER_QU240_ARCHIVE.md`

This report records a re-inspection of Hyun Kang’s staged data on Frontier and turns it into a first-sprint plan. Payloads stay on world-shared Lustre. This repo versions headers, namelists, and docs only.

---

## 1. Verdict

**Start now on Track A.** Do **not** start diffusion training.

Kang staged three streams in one tree:

| Stream | Role in the model | Ready? |
|---|---|---|
| Restarts years **51–55** and **601–605** | Early state \(x_t\) and late state \(x_{t+\Delta}\) | **Yes** — 60 month-aligned pairs, Δ = 550 yr |
| Remapped CORE2 NYF DATM on oQU240 cells | Atmosphere condition \(F\) | **Yes** — full NCEP + precip + radiation; cell index matches restart |
| Monthly history + OHC AM | Validation / spinup curve, **not** writeback | **Yes** for QC; **no** as extra Y |

What this enables immediately: mesh graph, pair factory, DATM encoder, persistence baselines, and a cell-only residual GNN on deep T/S.

What it does **not** enable: a generative denoiser. NYF cycles, so \(F\) is the same year for every pair. Physics \(\theta\) is one namelist. There is no continuous restart series from year 56 to 600. History monthly-mean T/S is not a restart.

---

## 2. Where the data live

**Host path:** `/lustre/orion/cli115/world-shared/hgkang/data4others/Dali/`  
**Case:** `v3.GMPAS-NYF_QU240`  
**MPAS git:** `be7af980a1`  
**Total on disk:** ~19 GB

```
Dali/
  remapped_datm/QU240-NYF/
    remapped/          DATM already on ncol=7153  (built 2026-08-05, ncremap 5.3.9)
    src_grid/          original T62 NYF
    map_file/          map_T62_TO_oQU240_aave.151209.nc
  QU240_Restart_Hist_051-055/
    restart/           60 monthly rst, years 51–55          (~3.5 GB)
    hist/              60 monthly stats + 1250 OHC AM files (~5.5 GB)
    ocean_heat_content/ 72 OHC files, 0051-01 … 0056-12
  QU240_Restart_Hist_601-605/
    restart_files/     60 monthly rst, years 601–605        (~3.5 GB)
    history/           60 monthly stats                     (~5.1 GB)
    ocean_heat_content/ 60 OHC files, 0601-01 … 0605-12
    mesh/ocean.QU.240km.151209.nc
  250926_init_data/    empty dirs + broken IAF/EC30 symlinks — ignore
```

Local schema authority (no NetCDF payloads in git): `data/OceanSpin_sample/`.

Do **not** use the old format exemplars `rst.0661` / `rst.0681` as the scientific pair. They are not in this Frontier tree. Training pairs are **0051–0055 → 0601–0605**.

---

## 3. Re-inspection findings (2026-09-10)

### 3.1 Restarts — X and Y

| Window | Directory | Count | Dates | Size | `xtime` check |
|---|---|---|---|---|---|
| Early | `…/051-055/restart/` | 60 | 1st of each month, **0051-01 … 0055-12** | 57 MB each | `0051-01-01_00:00:00` |
| Late | `…/601-605/restart_files/` | 60 | 1st of each month, **0601-01 … 0605-12** | 57 MB each | `0601-01-01_00:00:00` |

Dims (both windows): `nCells=7153`, `nEdges=22403`, `nVertices=15211`, `nVertLevels=60`.

Writeback names (restart header, **not** history aliases):

| Field | Shape | v1 role |
|---|---|---|
| `temperature` | Time, nCells, nVertLevels | Predict deep ΔT |
| `salinity` | Time, nCells, nVertLevels | Predict deep ΔS |
| `layerThickness` | Time, nCells, nVertLevels | Copy from \(x_t\) in v1; optional later |
| `normalVelocity` | Time, nEdges, nVertLevels | Deferred (Track A cell-only) |
| `bottomDepth`, `maxLevelCell`, `minLevelCell`, `refBottomDepth`, `restingThickness` | geometry | Deep mask + loss weights |
| `cellsOnCell`, `nEdgesOnCell`, `edgesOnCell`, `cellsOnEdge`, `areaCell`, … | mesh | Graph, once |

Deep mask (locked):

```
refBottomDepth[k] > 2000  and  k <= maxLevelCell[i]  and  bottomDepth[i] > 2000
```

**k = 46…60** (1-based; 0-based 45…59) → 15 levels, ~2075–5500 m.

`ssh` is **not** in the restart. Do not invent it. Keep `normalBarotropicVelocity` and other time-stepper auxiliaries from the template file.

### 3.2 Remapped DATM — F

Files under `remapped_datm/QU240-NYF/remapped/`:

| File | Time | Fields | Size |
|---|---|---|---|
| `nyf.ncep.oQU240.050923.nc` | 1460 × 6-hourly (`0.00 … 364.75`, noleap) | `u_10`, `v_10`, `t_10`, `slp_`, `q_10`, `dn10` | 240 MB |
| `nyf.gxgxs.oQU240.051007.nc` | 12 (mid-month days) | `prc` (mm/day) | 1.3 MB |
| `nyf.giss.oQU240.051007.nc` | 365 daily (`0.5 … 364.5`) | `lwdn`, `swdn`, `swup` (W/m²) | 31 MB |

Verified:

- `ncol=7153`, `mask=1` on every cell, no NaNs in the remapped fields.
- Cell order matches restart: first five `lat`/`lon` agree with `latCell`/`lonCell` to ~1e-12 degrees. **Identity join.** Do not KD-tree.
- Ocean cell area sum ≈ 0.70 × 4π steradian (land omitted) — expected for an ocean mesh.
- Physical ranges: winds ±25 m/s, `t_10` 202–323 K, SLP ~971–1031 hPa, precip 0.03–15 mm/day.
- `q_10` is slightly negative on ~0.32% of points (min ≈ −0.0018 kg/kg). Inherited from the original NCEP FFT NYF product; clamp to ≥0 in the encoder.
- Map is **first-order conservative** (`map_T62_TO_oQU240_aave.151209.nc`), not the DATM namelist bilinear `u:v`. Accept for v1 conditioning; do not re-grid T62 unless comparing map methods.
- GISS title is “daily mean climatology”; variable attributes still say `av-1mo`. Use the 365 daily samples.
- No `presaero` file. Optional; skip for v1.

**v1 encoding (B1):** monthly-mean NCEP (12 × 6 fields) + monthly `prc` + monthly-mean GISS, all on cells. Shared across every training pair because NYF cycles. Do **not** feed 1460 × 7153 raw 6-hour fields into the GNN.

### 3.3 History and OHC — QC only

| Product | Count | Coverage | Use |
|---|---|---|---|
| `timeSeriesStatsMonthly` early | 60 × 87 MB | 0051-01 … 0055-12 | Monthly T/S/h, SSH, MLD, N², OHC bands |
| `timeSeriesStatsMonthly` late | 60 × ~87 MB | 0601-01 … 0605-12 | Same, aligned with late restarts |
| OHC AM in `051-055/hist/` | 1250 × 209 KB | **0001-02 → 0105-03** | Spinup curve (2D J/cell) |
| Dedicated OHC dirs | 72 + 60 | 0051–0056 and 0601–0605 | Window OHC |

History 3D tracers are named `timeMonthly_avg_activeTracers_temperature` / `_salinity`. These are **monthly averages**, not instantaneous restart state. Do not mix them into Y. Do not overwrite a restart with history fields.

OHC 2000 m–bottom from a restart must match history after a global sum:

\[
\mathrm{OHC}_{2000}^{\mathrm{bot}}
= \rho_0 c_p \sum_i \sum_{k\in\mathrm{deep}} T_{i,k}\, h_{i,k}\, A_i
\]

with \(\rho_0=1026\), \(c_p=3996\). AM files use unprefixed names (`oceanHeatContent2000mToBot`); monthly stats use the `timeMonthly_avg_` prefix.

Coupler fluxes in history (`windStress*`, `latentHeatFlux`, `rainFlux`, …) are **not** DATM substitutes.

### 3.4 Pair recipes this archive supports

| Recipe | N | Δ | Use |
|---|---|---|---|
| **Long-horizon (primary)** | **60** | **550 yr** | Scientific spinup operator |
| Jan-1 only | 5 | 550 yr | Clean annual baseline / sanity |
| Consecutive months inside a window | 59+59 | 1 month | Loader / graph tests only |
| Same month, next year, inside a window | 48+48 | 1 yr | Seasonal-aligned short residual |
| Physics / forcing / mesh ensembles | 0 | — | Needed before \(F\) or \(\theta\) are identifiable |

**Hold-out (v1):** train on years 51–54 mapped to 601–604 (48 pairs). Hold out **0055-MM → 0605-MM** (12 pairs). Do not mix 1-month pairs into the same loss as the 550-year map.

**Still missing for Track C:** years 56–600 (or 20–50) as restarts, or additional `mpaso_in` / IAF cases. Ask Hyun before any diffusion run.

---

## 4. What to build (and what not to)

The learning problem is a **spinup operator**, not a 6-hour weather step:

\[
x_{t+\Delta} \approx x_t + f_\phi(x_t, F, \theta, G), \qquad \Delta = 550~\mathrm{yr}
\]

on the deep mask only. Persistence (\(f_\phi=0\)) is the first number to beat.

| Start | Do not start |
|---|---|
| Pair factory + mesh graph + DATM monthly encoder | Diffusion / flow matching |
| Persistence, linear-drift, late-climatology baselines | ViT on interpolated lat–lon ocean state |
| Cell-only residual GNN (deep ΔT, ΔS) | Predicting coupler fluxes as if they were DATM |
| Copy-template restart overwrite of deep T/S | Treating 0661/0681 or monthly history as Y |
| OHC QC vs history | Feeding raw 6-hourly NCEP (1460 steps) into the GNN |

Architecture (unchanged from the implementation plan): LandSim pairing + GraphCast typed mesh GNN on MPAS incidence, residual early→late map, FiLM stubs for NYF and namelist. Diffusion remains a **drop-in denoiser interface**, untrained until pair count grows.

---

## 5. How to start — first three sprints

Work on Frontier against Kang’s paths. Keep processed tensors under this project’s Lustre space, not inside git.

Suggested processed root (working extract). For a **portable AI-ready pack** to copy to another GPU cluster, see `data/docs/AIREADY_DATASET.md` and `python -m oceanai.data.pack_aiready`.

```
/lustre/orion/lrn105/proj-shared/wangd/AI4MPAS/data/processed/QU240/
  mesh_graph.npz
  deep_mask.npz
  datm_monthly.npz          # 12 × nCells × n_fields, shared
  scalers/
  pairs/index.json
  pairs/*.npz
  baselines/persistence.json
```

Python: `cray-python/3.11.7` plus a user env with `netCDF4`/`xarray` and PyTorch (or JAX if matching GraphCast). Login-node `python3` has neither netCDF4 nor a current scientific stack; `ncdump` is at `/opt/cray/pe/netcdf/4.9.0.7/bin/ncdump`.

### Sprint 0 — paths, index, QC (days, not weeks)

**Goal:** a machine-readable pair table and a proof that OHC from restart matches history.

1. Write `oceanai/paths.py` with the Dali prefixes above (single source of truth).
2. Write `oceanai/data/pair_index.py`:
   - glob `rst.0051-01` … `rst.0055-12` and `rst.0601-01` … `rst.0605-12`
   - emit 60 rows: `t`, `t_delta`, `path_x`, `path_y`, `split` (`train` if year in 51–54, `holdout` if 55)
   - optional secondary tables for 1-month pairs, **not** mixed into the primary loader
3. Write `oceanai/data/deep_mask.py` from `refBottomDepth` / `maxLevelCell` / `bottomDepth`. Unit test: 15 levels, k=46…60.
4. Write `oceanai/qc/ohc.py`:
   - compute deep OHC from `rst.0051-01-01` and `rst.0601-01-01`
   - compare global sum to `timeMonthly_avg_oceanHeatContent2000mToBot` in the matching monthly history (and/or AM `oceanHeatContent2000mToBot`)
   - plot the year-1–105 AM series (diagnostic figure, not a training target)
5. Confirm DATM `lat[0:5]` vs restart `latCell[0:5]` (already true; keep as a loader assertion).

**Done when:** `pairs/index.parquet` has 60 primary rows; OHC relative error is documented; deep-mask unit test passes.

### Sprint 1 — graph, DATM encoder, baselines (WP1)

**Goal:** tensors the GNN can load, plus the numbers any net must beat.

1. `oceanai/mesh/mpas_mesh_to_typedgraph.py` on `rst.0051-01-01` (or `mesh/ocean.QU.240km.151209.nc`):
   - cell nodes: `xCell,yCell,zCell` (or lat/lon), `areaCell`, `bottomDepth`, `fCell`, deep-column flag
   - cell→cell edges from `cellsOnCell` (symmetric, skip 0-index holes)
   - cache `mesh_graph.npz`; do not rebuild per sample
   - unit tests: `nCells=7153`, max degree ≤ 6, `sum(areaCell)` vs ocean surface area
2. `oceanai/data/datm_encoder.py`:
   - load remapped NCEP / GXGXS / GISS
   - monthly-mean NCEP; keep 12 `prc`; monthly-mean GISS
   - clamp `q_10 ≥ 0`
   - write `datm_monthly.npz` once (shared \(e_F\) source)
3. `oceanai/data/extract_pair.py`: for each index row, read deep T/S/(h) from X and Y, apply mask, write `pairs/xxxxx.npz`.
4. `oceanai/data/scalers.py`: fit per-variable (optionally per-level) z-score or min-max on **train years only**.
5. `oceanai/baselines/persistence.py`:
   - \(\hat x_{t+\Delta}=x_t\)
   - linear global/basin deep-T drift
   - late-state climatology (mean of train Y)
   - metrics: `areaCell` × `restingThickness` (or `layerThickness`) RMSE and bias for deep T, S, and OHC 2000 m–bottom
   - **first published number:** persistence **0051-01-01 → 0601-01-01** on deep T, then all 48 train + 12 holdout pairs

**Done when:** one can `Dataset[i] → (x_t, x_td, mask, F_month, G)` without opening NetCDF in the training loop; baseline JSON exists for holdout.

### Sprint 2 — Track A residual GNN (WP2, cell-only)

**Goal:** beat persistence on holdout deep T and on deep OHC.

1. Cell-only processor: 10–12 message-passing steps, latent 128–256, residual \(\Delta T,\Delta S\) (15 channels each). Thickness frozen (copy \(x_t\)).
2. FiLM / scale-shift slots for \(e_F\) and \(e_\theta\) even though both are constant in this case — keeps the IO contract.
3. Loss: Huber, weights `areaCell` × thickness, deep mask only. Shallow levels are not in the loss; at writeback they stay from the template / \(x_t\).
4. Train on 48 pairs. Tiny set: heavy augmentation is **not** a substitute for more years. Use dropout / weight decay; early-stop on holdout OHC RMSE.
5. `oceanai/io/write_restart.py`: copy `rst.0055-01-01` (or the matching X file) as template; overwrite only deep `temperature` and `salinity`; leave auxiliaries untouched.
6. Maps: holdout deep ΔT (truth vs pred vs persistence). Global OHC 2000 m–bottom vs year-605 history.

**Done when:** holdout area-weighted deep-T RMSE < persistence, and a written restart opens in `ncdump` with valid `xtime` and no fill-value storms in the overwritten levels.

### After Track A (not this start)

| Next | Trigger |
|---|---|
| WP3: N-day MPAS forward from ML restart vs official 605 restart | Track A beats persistence |
| Edge `normalVelocity` heads | Cell T/S is stable |
| Track B dense attention on 7k cells | Message passing is too local (basin-scale error remains) |
| Track C flow matching | Hyun delivers \(\gtrsim 10^2\) more independent long-horizon pairs, or multi-physics/IAF cases |
| \(\theta\) / \(F\) as causal inputs | Second namelist or non-NYF forcing |

---

## 6. Suggested code layout

Nothing in this repo implements the loader yet. Add a small package rather than notebooks-only:

```
oceanai/
  paths.py
  mesh/
    mpas_mesh_to_typedgraph.py
    deep_mask.py
  data/
    pair_index.py
    extract_pair.py
    datm_encoder.py
    scalers.py
    dataset.py
  baselines/
    persistence.py
  models/
    residual_gnn.py          # Track A
    film.py                  # stubs for F, θ
  io/
    write_restart.py
  qc/
    ohc.py
  train_track_a.py
```

IO lists stay where they are: `data/OceanSpin_sample/restart_variables`, `mpaso_variables`. Do not train on namelist knobs as if they were prognostics.

---

## 7. Concrete file pointers (copy-paste)

```text
DALI=/lustre/orion/cli115/world-shared/hgkang/data4others/Dali

# Graph + mask
$DALI/QU240_Restart_Hist_051-055/restart/v3.GMPAS-NYF_QU240.mpaso.rst.0051-01-01_00000.nc
$DALI/QU240_Restart_Hist_601-605/mesh/ocean.QU.240km.151209.nc

# Primary pair example
X=$DALI/QU240_Restart_Hist_051-055/restart/v3.GMPAS-NYF_QU240.mpaso.rst.0051-01-01_00000.nc
Y=$DALI/QU240_Restart_Hist_601-605/restart_files/v3.GMPAS-NYF_QU240.mpaso.rst.0601-01-01_00000.nc

# DATM on cells
$DALI/remapped_datm/QU240-NYF/remapped/nyf.ncep.oQU240.050923.nc
$DALI/remapped_datm/QU240-NYF/remapped/nyf.gxgxs.oQU240.051007.nc
$DALI/remapped_datm/QU240-NYF/remapped/nyf.giss.oQU240.051007.nc

# OHC QC (same month as X)
$DALI/QU240_Restart_Hist_051-055/hist/v3.GMPAS-NYF_QU240.mpaso.hist.am.timeSeriesStatsMonthly.0051-01-01.nc
$DALI/QU240_Restart_Hist_051-055/ocean_heat_content/v3.GMPAS-NYF_QU240.mpaso.hist.am.oceanHeatContent.0051-01-01.nc

# Spinup curve (not a training target)
$DALI/QU240_Restart_Hist_051-055/hist/v3.GMPAS-NYF_QU240.mpaso.hist.am.oceanHeatContent.0001-02-01.nc
# … through 0105-03-01.nc
```

Schema names: `data/OceanSpin_sample/restart/mpas_ocean_header.txt`.

---

## 8. Risks for the first sprint

| Risk | Mitigation |
|---|---|
| 60 pairs overfit a GNN | Hold out year 55/605; stop on holdout OHC; keep the net small |
| Mixing monthly history into Y | Restart header is writeback truth; history is QC |
| Mixing 1-month Δ into the 550-yr loss | Separate tables; short-Δ is loader-only until a multi-horizon head exists |
| Conservative DATM remap ≠ coupled bilinear winds | Document; v1 uses Kang’s oQU240 files as-is |
| Negative `q_10` | Clamp in encoder |
| `250926_init_data` looks like another case | Empty / broken; ignore |
| Diffusion “because GenCast” | Same backbone later; not this data volume |
| Unusable ML restart | Overwrite only deep T/S; copy everything else from template |

---

## 9. Asks of the team

| Person | Ask |
|---|---|
| **Dali** | Implement Sprints 0–2 in `oceanai/`; keep this report and the implementation plan in sync |
| **Olawale** | LandSim `dataGEN` patterns → `pair_index` / scalers / writeback |
| **Alice** | Confirm OHC / drift thresholds for “near eq”; review the holdout metric list |
| **Hyun** | Confirm whether years **56–600** (or 20–50) will be exported; that is the Track C gate |

---

## 10. One-line summary

Kang’s Frontier dump is a **complete QU240 Track A dataset**: 60 month-aligned 50→600 yr restart pairs, DATM already on the same cells, and matching history/OHC for QC. Start the pair factory, mesh GNN, and persistence baseline this week. Leave diffusion until there are many more independent ocean checkpoints.

*Re-inspected 2026-09-10. Architecture details remain in `OceanAISpinup_Implementation_Plan.md`.*
