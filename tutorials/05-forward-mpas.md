# 05 — Short MPAS forward from an ML restart

**Status:** recipe and blockers — **not** automated in `oceanai`. Hyun owns the first smoke test after a `*.ml.nc` exists.  
**Goal:** show the written restart is **ingestible**, not that the GNN replaced a 550-year spinup.

Do not block the prototype on a full G-case.

## What to integrate

| File | Role |
|---|---|
| `data/processed/QU240/restarts_ml/rst.0055-01-01.ml.nc` | ML (or persistence) deep T/S in an **X template** |
| Official `rst.0605-01-01` | Late-state control (same namelist, same forcing) |
| `rst.0055-01-01` (raw X) | Early-state control: how fast does *unmodified* year-55 drift? |
| `data/OceanSpin_sample/mpaso_in` | Physics; this pack is **one** case |

`xtime` on the ML file is still **0055-01-01** (template). Streams / coupler may care. If the case manager requires a 0605 stamp, change `xtime` **explicitly** and document it — do not do that silently in `write_deep_ts`.

## Suggested smoke (ocean-only)

1. Same QU240 mesh, same CORE2 NYF, same `mpaso_in`.
2. Integrate **N days** (start with **1–5 days**, not years) from:
   - `rst.0055-01-01.ml.nc`
   - official `rst.0605-01-01` (if the coupler accepts a year-605 stamp)
3. Compare: crash vs no crash, CFL, silly T/S, global OHC 2000 m–bottom, SSH if the run writes it (restart itself has no `ssh`).
4. MPAS-Analysis on the short hist vs the official 605 monthly stats — after the run survives.

A short ocean-only forward is enough to **fail** a bad writeback (fill-value storms, unstable columns). It is **not** enough to claim equilibrium.

## Likely blockers (document, don’t guess)

- **Sea ice / coupler / datm streams** for GMPAS-NYF may be required even for “ocean” smoke. If so, write the missing files in the QC note rather than expanding v1 writeback.
- Template is year **55**; Y is year **605**. Time-dependent streams and restart extras (`normalBarotropicVelocity`, …) are from year 55 by design.
- `layerThickness` is **X**, T/S deep are **predicted**. Hydrostatic consistency is not projected in v1; the N-day run is the filter.
- History monthly-mean T is not a restart. Do not initialize from `timeSeriesStatsMonthly`.

## Minimal pass / fail

| Result | Meaning |
|---|---|
| MPAS refuses to open / fill-value abort | Writeback bug → [03](03-restart-writeback.md) |
| Runs N days; T/S blow up | Dynamically illegal deep state; model or mask |
| Runs N days; OHC close to 605 control | Encouraging, **not** “spun up” |
| No ice/coupler files | Record the exact missing streams; Alice/Hyun |

## Pointers

- Case name: `v3.GMPAS-NYF_QU240`
- Sample namelist and streams: `data/OceanSpin_sample/`
- Analysis example: [GMPAS-NYF_QU240 MPAS-Analysis](https://portal.nersc.gov/project/e3sm/hgkang/ImPACTS/AI_spinup/v3.GMPAS-NYF_QU240/www/)
- Prototype plan § Hyun: `OceanAISpinup_Prototype_Plan.md`

When this recipe is executed, add the commands and a one-line outcome here (or a short note under `prototype/`).
