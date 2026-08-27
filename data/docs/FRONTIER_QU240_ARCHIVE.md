# Frontier QU240 restart / history archive

**Host path:** `/lustre/orion/cli115/world-shared/hgkang/data4others/Dali/`  
**Case:** `v3.GMPAS-NYF_QU240` (same git `be7af980a1`, same dims as `data/OceanSpin_sample/`)  
**Inspected:** 2026-08-27

This is Hyun’s staged **early (~50 yr) and late (~600 yr)** windows on Frontier.
Schema matches the locked restart header. Payloads stay on world-shared (not git).

## Layout

```
Dali/
  QU240_Restart_Hist_051-055/     early window
    restart/                      60 monthly rst  (0051-01 … 0055-12)
    hist/                         60 monthly stats (0051–0055)
                                  + 1250 OHC AM files (0001-02 … 0105-03)
    ocean_heat_content/           72 OHC files (0051-01 … 0056-12)
  QU240_Restart_Hist_601-605/     late window
    restart_files/                60 monthly rst  (0601-01 … 0605-12)
    history/                      60 monthly stats (0601–605)
    ocean_heat_content/           60 OHC files (0601-01 … 0605-12)
    mesh/ocean.QU.240km.151209.nc standalone QU240 mesh (80 MB)
  remapped_datm/QU240-NYF/
    src_grid/                     T62 NYF (NCEP, GXGXS, GISS)
    remapped/                     already on oQU240 cells (ncol=7153)
    map_file/map_T62_TO_oQU240_aave.151209.nc
```

## Restarts

| Window | Directory | Count | Dates | Size |
|---|---|---|---|---|
| Early | `…/051-055/restart/` | 60 | 1st of each month, years **51–55** | 57 MB each (~3.5 GB) |
| Late  | `…/601-605/restart_files/` | 60 | 1st of each month, years **601–605** | 57 MB each (~3.5 GB) |

Checked files:

- `rst.0051-01-01` `xtime = 0051-01-01_00:00:00`
- `rst.0601-01-01` `xtime = 0601-01-01_00:00:00`

Dims (both): `nCells=7153`, `nEdges=22403`, `nVertices=15211`, `nVertLevels=60`.  
Prognostic names match the lock: `temperature`, `salinity`, `layerThickness`, `normalVelocity`. Mesh connectivity is in the restart; a standalone mesh also exists under `601-605/mesh/`.

The original format samples `0661` / `0681` are **not** in this tree (later than 605).

## Pairing this archive actually supports

| Recipe | N | Δ |
|---|---|---|
| Month-aligned early→late | **60** | **550 years** (0051-MM → 0601-MM, …, 0055-12 → 0605-12) |
| Jan-1 only early→late | 5 | 550 years |
| Consecutive months inside a window | 59 + 59 | 1 month |
| Same month, next year, inside a window | 48 + 48 | 1 year |

This is the scientific 50 yr → 600 yr map, with 5 years × 12 months of examples.
It is **not** a continuous annual archive from year 20 to 600. Track A can start; diffusion still wants more years if Hyun has them.

## History / OHC

- Monthly stats (`timeSeriesStatsMonthly`) cover the same 60 months as each restart window.
  OHC there is `timeMonthly_avg_oceanHeatContent2000mToBot`.
- Dedicated AM files use **unprefixed** names: `oceanHeatContent2000mToBot` (and 0–700, 700–2000, sfc–bot).
- Extra: `051-055/hist` also holds a long OHC AM series **0001-02 → 0105-03** (1250 files) — useful for the spinup curve, not for restart writeback.

## DATM already on the ocean mesh

`remapped_datm/QU240-NYF/remapped/`:

| File | Grid | Time | Fields |
|---|---|---|---|
| `nyf.ncep.oQU240.050923.nc` | `ncol=7153` | 1460 (6-hourly NYF) | `u_10,v_10,t_10,slp_,q_10,dn10` |
| `nyf.gxgxs.oQU240.051007.nc` | `ncol=7153` | 12 | `prc` |
| `nyf.giss.oQU240.051007.nc` | `ncol=7153` | 365 | `lwdn,swdn,swup` |

Map is **area-average** (`map_T62_TO_oQU240_aave.151209.nc`), not the namelist `mapalgo=bilinear`. For v1 B1 conditioning, use these remapped files; do not re-interpolate T62 unless comparing map methods.

## Implication for WP0 / WP1

- Year list for these two windows: **done**.
- Graph builder: any `rst.0051-01-01` (or the mesh file).
- Persistence / long-horizon baseline: 0051-01-01 → 0601-01-01 (and the other 59 aligned months).
- Still open: whether Hyun will export more years between 55 and 601 (or after 605).
