# 00 — Concepts in five minutes

Read this once. Then pick a hands-on tutorial from [`README.md`](README.md).

## What we are learning

A **restart operator**, not a weather model.

\[
\hat{x}_{600} = x_{50} + f_\phi(x_{50},\, F_{\mathrm{NYF}},\, \theta,\, G)
\quad\text{on deep levels } k=46\ldots 60
\]

Given an **early** MPAS-Ocean restart (year ~50), predict the **deep** temperature and salinity of a **late** restart (year ~600) on the same QU240 mesh, then **write those fields back** into a copy of the early file so MPAS could ingest it.

We do **not** predict SSH, velocity, or the upper ocean in v1. Thickness and barotropic auxiliaries stay on the template.

## Vocabulary

| Word | Meaning here |
|---|---|
| **X** | Early restart (~year 51–55). Input state. |
| **Y** | Late restart (~year 601–605). Target. Same calendar month as X, 550 years later. |
| **Pair** | One month-aligned map, e.g. `0051-01` → `0601-01`. There are **60** pairs. |
| **Train / holdout** | Train: years 51–54 → 601–604 (**48**). Hold out: 55 → 605 (**12**). |
| **Deep** | Vertical levels with `refBottomDepth > 2000 m`: **k = 46…60** (15 levels, ~2075–5500 m). |
| **Valid cell** | Column actually reaches >2000 m (`bottomDepth` and `maxLevelCell`). ~63 228 deep points. |
| **Persistence** | The baseline: \(\hat Y = X\). Any model must beat this on deep T and OHC. |
| **Writeback** | `shutil.copy` the X restart, overwrite only deep `temperature` and `salinity`. |
| **AI-ready pack** | Numpy tensors + graph + monthly NYF. **Not** the 19 GB raw NetCDF dump. |
| **NYF** | CORE2 Normal Year Forcing. It **cycles**, so atmosphere \(F\) is the same year for every pair. |

## What a pair tensor looks like

Each `pairs/YYYY-MM.npz` holds arrays of shape **`(7153, 15)`**:

- `t_x, s_x, h_x` — deep T (°C), S, layer thickness (m) from X
- `t_y, s_y, h_y` — same from Y
- `valid` — boolean mask (land / shallow / fill → False, values zeroed)

The GNN sees the **whole mesh at once** (one graph, 41 018 directed cell–cell edges). It predicts residual **ΔT, ΔS**, added back onto X.

## Two machines

| Machine | You have | You run |
|---|---|---|
| **Frontier** | Kang’s `Dali/` dump + this repo | `python -m oceanai.run_prototype` and/or `pack_aiready` |
| **Other GPU cluster** | Repo + ~113 MB tarball | Set `OCEANAI_PROCESSED`, train; `netCDF4` only if you write a restart |

Login-node `python3` on Frontier has **no** `netCDF4`. Use `cray-python` + the project `.venv`.

## Do not (v1)

- Train diffusion / GenCast on 60 NYF pairs.
- Interpolate T/S onto a lat–lon grid for a ViT.
- Write history fields (`timeMonthly_avg_activeTracers_*`) into a restart.
- Treat DATM or `mpaso_in` as *causes* of holdout skill — they are constant across this dataset.

## Next

- On Frontier, first time: [01 — Frontier prototype](01-frontier-prototype.md)
- Taking data elsewhere: [02 — AI-ready pack](02-aiready-pack.md)
- Restart file contract: [03 — Writeback](03-restart-writeback.md)
- Numbers Alice cares about: [04 — Metrics and OHC](04-metrics-and-ohc.md)
- After an ML restart exists: [05 — Forward MPAS](05-forward-mpas.md)
