# DATM Atmospheric Forcing Variables

**Case:** `v3.GMPAS-NYF_QU240`  
**Mode:** CORE2 Normal Year Forcing (`datamode = CORE2_NYF`)  
**Sample path:** `data/OceanSpin_sample/` (also mirrored under `data/hgkang/data_for_others/Dali_OceanSpinup_sample/`)

**Related:** MPAS-Ocean physics namelist inputs for AI training —  
[`MPASO_PHYSICS_CONFIG_INPUTS.md`](MPASO_PHYSICS_CONFIG_INPUTS.md)  
(from `data/OceanSpin_sample/mpaso_variables`).

**Related:** Restart deep-ocean state (2000 m–bottom) as input@~50yr /
target@~600yr — [`RESTART_DEEP_OCEAN_STATE.md`](RESTART_DEEP_OCEAN_STATE.md)  
(from `data/OceanSpin_sample/restart_variables`).

## Recommendation

Use **DATM CORE2_NYF atmospheric state** as the forcing source of truth.
Do **not** use coupler-derived fluxes from the MPAS-Ocean monthly history file
as atmospheric forcing inputs (those are diagnostics that depend on SST and sea ice).

Combine with selected **`mpaso_in` physics configs** as static conditioning /
metadata inputs (see related doc above).

**Priority for modeling:**

1. **Tier-1 (NCEP):** `u_10`, `v_10`, `t_10`, `slp_`
2. **Tier-1b (GXGXS):** `prc` (precipitation)
3. **Tier-2 (NCEP):** `q_10`, `dn10`
4. **Tier-3 (GISS):** `swdn`, `swup`, `lwdn`
5. **Physics config:** selected `mpaso_in` parameters (`mpaso_variables`)
6. **Optional:** presaero aerosol deposition species

---

## Why DATM instead of ocean history

| Aspect | DATM NCEP / streams | Ocean history |
|---|---|---|
| Role | Input atmospheric state | Diagnosed surface fluxes |
| Time resolution | 6-hourly (NCEP); monthly (GXGXS precip) | Monthly averages |
| Grid | T62 (94 × 192) | MPAS ocean mesh (`nCells`) |
| Independence from ocean | Yes (prescribed NYF) | No (depends on SST / ice) |
| Use for AI forcing | Primary | Optional target / diagnostic only |

---

## Tier-1 — NCEP atmospheric state

**File:** `datm_NYF/nyf.ncep.T62.050923.nc`  
**Stream:** `datm.streams.txt.CORE2_NYF.NCEP`  
**Header:** `datm_NYF/ncep_header.txt`  
**Title:** NCEP Normal Year Forcing, 6-hour data (1958–2000 ensemble / FFT NYF)  
**Vectors in `datm_in`:** `u:v`

| File variable | DATM name | Long name | Units | Level |
|---|---|---|---|---|
| `u_10` | `u` | U Wind | m/s | 10 m |
| `v_10` | `v` | V Wind | m/s | 10 m |
| `t_10` | `tbot` | Air Temperature | K | 10 m |
| `slp_` | `pslv` | Sea Level Pressure | Pa | surface |

**Rationale:** Winds dominate momentum forcing; air temperature anchors heat
exchange; SLP provides inverse-barometer and large-scale weather structure.

### Coordinate / domain variables (same file)

| Variable | Long name | Units |
|---|---|---|
| `lat` | latitude | degrees_north |
| `lon` | longitude | degrees_east |
| `area` | area of grid cell | radian² |
| `mask` | domain mask | — |
| `frac` | fraction of grid cell that is active | — |
| `time` | observation time | days since 0001-01-01 (noleap) |

---

## Tier-1b — GXGXS precipitation (required companion)

**File:** `datm_NYF/nyf.gxgxs.T62.051007.nc`  
**Stream:** `datm.streams.txt.CORE2_NYF.GXGXS`  
**Title:** 1979–2000 GXGXS Precip Climatology  
**Grid:** T62 (lat=94, lon=192), same as NCEP  
**Time:** monthly climatology (`time = 12`), noleap, coords on the 15th of each month

| File variable | DATM name | Long name | Units | Time |
|---|---|---|---|---|
| `prc` | `prec` | Precipitation | mm/day | Monthly (12) |

**Blend (by latitude):** GPCP (G) / Xie–Arkin (X) / Serreze (S)  
`G to 60S; X to 35S; G to 35N; X to 68N; S to 90N`

**Why include it:** Primary freshwater atmospheric forcing for surface salinity
and layer thickness. Prefer DATM `prc` over history `rainFlux` / `snowFlux`
(those are coupler-partitioned products).

**Temporal note:** Monthly climatology vs 6-hourly NCEP — aggregate or
interpolate consistently when combining features.

---

## Tier-2 — NCEP moisture / density companions

Same file as Tier-1 (`nyf.ncep.T62.050923.nc`).

| File variable | DATM name | Long name | Units | Level |
|---|---|---|---|---|
| `q_10` | `shum` | Specific Humidity | kg/kg | 10 m |
| `dn10` | `dens` | Air Density | kg/m³ | 10 m |

---

## Tier-3 — GISS radiation

**File:** `datm_NYF/nyf.giss.T62.051007.nc`  
**Remapped (Frontier):** `remapped_datm/QU240-NYF/remapped/nyf.giss.oQU240.051007.nc`  
**Stream:** `datm.streams.txt.CORE2_NYF.GISS`  
**Time:** **365 daily** means (noleap, noon each day). Variable attributes still say `av-1mo`; the title and `time=365` are authoritative.

| File variable | DATM name | Role |
|---|---|---|
| `lwdn` | `lwdn` | Downward longwave |
| `swdn` | `swdn` | Downward shortwave |
| `swup` | `swup` | Upward shortwave |

---

## Optional — aerosol deposition (presaero)

**Stream:** `datm.streams.txt.presaero.clim_2000`  
**File:** `datm_NYF/aerosoldep_monthly_2000_mean_1.9x2.5_c090421.nc`

Species include BC/OC/dust wet and dry deposition (`BCDEPWET`, `BCPHODRY`,
`BCPHIDRY`, `OCDEPWET`, `OCPHIDRY`, `OCPHODRY`, `DSTX01WD`–`DSTX04DD`, etc.).
Usually not first-order for large-scale ocean spinup ML.

---

## Full DATM stream map (`datm_in`)

| Stream | File | Variables | Role |
|---|---|---|---|
| NCEP | `nyf.ncep.T62.050923.nc` | `u_10`, `v_10`, `t_10`, `slp_`, `q_10`, `dn10` | Tier-1 + humidity/density |
| GXGXS | `nyf.gxgxs.T62.051007.nc` | `prc` → `prec` | Precipitation (required companion) |
| GISS | `nyf.giss.T62.051007.nc` | `lwdn`, `swdn`, `swup` | Radiative fluxes |
| presaero | `aerosoldep_monthly_2000_mean_…` | BC/OC/dust wet+dry | Aerosol deposition |

**Namelist notes (`datm_in`):**

- `datamode = "CORE2_NYF"`
- `taxmode = "cycle"` (Normal Year cycled)
- `tintalgo = "linear"`
- `mapalgo = "bilinear"`
- `vectors = "u:v"`
- Domain: `domain.lnd.T62_oQU240.240513.nc`
- Correction factors: `COREv2.correction_factors.T62.121007.nc`

---

## Do not treat as atmospheric forcing inputs

Present in `history/history_header.txt` as coupler diagnostics — useful as
targets or validation, **not** as DATM substitutes.

| History field | Why it is not DATM forcing |
|---|---|
| `timeMonthly_avg_windStressZonal` / `…Meridional` | Bulk-formula stress from wind + ocean surface state |
| `timeMonthly_avg_latentHeatFlux` / `…sensibleHeatFlux` | Coupler turbulent fluxes; depend on SST and ice |
| `timeMonthly_avg_shortWaveHeatFlux` / `longWaveHeatFlux*` | Net surface radiation after coupling |
| `timeMonthly_avg_rainFlux` / `…snowFlux` / `…evaporationFlux` | Coupler-partitioned freshwater — use DATM `prc` instead |
| `timeMonthly_avg_atmosphericPressure` | Passed pressure at ocean cells — prefer DATM `slp_` upstream |
| `timeMonthly_avg_seaIce*` / `…river*` / `…iceRunoff*` | Cryosphere / land fluxes, not atmosphere |

---

## Practical notes

- DATM remaps T62 → ocean mesh with bilinear mapping; `u:v` are treated as a vector pair.
- NYF is a climatological normal year (year=1, noleap), cycled — suitable for spinup, not interannual weather.
- Temporal mix: NCEP is 6-hourly; GXGXS precip is monthly; GISS radiation is **daily**; ocean history is monthly — align aggregation when combining features. On Frontier, use Hyun’s remapped oQU240 files (`ncol=7153`); identity-join to restart cells.
- Stream XML originally points at E3SM inputdata (`atm/datm7/NYF`); local copies live under `datm_NYF/`.

## Sources

- `datm_NYF/ncep_header.txt`
- `datm_NYF/nyf.ncep.T62.050923.nc`
- `datm_NYF/nyf.gxgxs.T62.051007.nc`
- `datm_NYF/nyf.giss.T62.051007.nc`
- `datm_in`
- `datm.streams.txt.CORE2_NYF.NCEP`
- `datm.streams.txt.CORE2_NYF.GXGXS`
- `datm.streams.txt.CORE2_NYF.GISS`
- `datm.streams.txt.presaero.clim_2000`
- `history/history_header.txt`
