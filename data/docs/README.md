# AI4MPAS Ocean Spinup — Variable Selection Docs

Documentation of atmospheric forcing, MPAS-Ocean physics configs, and restart
deep-ocean state variables selected for AI training.

**Plans:** `OceanAISpinup_Development_Plan.md` (review),
`OceanAISpinup_Implementation_Plan.md` (architecture + work packages),
and `OceanAISpinup_Prototype_Plan.md` (prototype e2e + handoff).
Diffusion decision vs GraphCast/GenCast/LandSim: `../../OceanAISpinup_Diffusion_Evaluation.md`.

| Document | Topic |
|---|---|
| [DATM_FORCING_VARIABLES.md](DATM_FORCING_VARIABLES.md) | DATM CORE2_NYF forcing: Tier-1 `u,v,t,slp` + GXGXS precip `prc` |
| [MPASO_PHYSICS_CONFIG_INPUTS.md](MPASO_PHYSICS_CONFIG_INPUTS.md) | Selected `mpaso_in` physics / numerics namelist inputs |
| [RESTART_DEEP_OCEAN_STATE.md](RESTART_DEEP_OCEAN_STATE.md) | Restart deep ocean (2000 m–bottom): input@~50yr, target@~600yr |
| [FRONTIER_QU240_ARCHIVE.md](FRONTIER_QU240_ARCHIVE.md) | Hyun’s Frontier windows: monthly rst years 51–55 and 601–605; remapped DATM |
| [AIREADY_DATASET.md](AIREADY_DATASET.md) | Portable tensor pack: extract, tar, and train on a second GPU cluster |

## Local sample (`../OceanSpin_sample/`)

Case **`v3.GMPAS-NYF_QU240`**: QU240 mesh (`nCells=7153`, `nEdges=22403`,
`nVertLevels=60`), DATM CORE2_NYF, `noleap`, `config_dt=01:00:00`.

| Path | Role |
|---|---|
| `restart/mpas_ocean_header.txt` | Authoritative restart names, dims, mesh connectivity |
| `history/history_header.txt` | Monthly history; OHC / SSH / MLD diagnostics |
| `datm_NYF/ncep_header.txt` | NCEP T62 NYF (`time=1460`) |
| `mpaso_in` | Full ocean namelist |
| `datm_in` + `datm.streams.txt.CORE2_NYF.*` | DATM streams (NCEP, GXGXS, GISS, presaero) |

Format-exemplar payloads (gitignored; named in headers):

- `v3.GMPAS-NYF_QU240.mpaso.rst.0661-01-01_00000.nc`
- `v3.GMPAS-NYF_QU240.mpaso.rst.0681-01-01_00000.nc`
- `v3.GMPAS-NYF_QU240.mpaso.hist.am.timeSeriesStatsMonthly.0678-11-01`

0661/0681 are a **20-year late-run pair**, not the intended ~50 yr → ~600 yr
training pair.

NERSC source (headers): `/global/cfs/cdirs/m4259/hgkang/data_for_others/Dali_OceanSpinup_sample`  
Frontier payloads: `/lustre/orion/cli115/world-shared/hgkang/data4others/Dali/` — see [FRONTIER_QU240_ARCHIVE.md](FRONTIER_QU240_ARCHIVE.md).

## Selection lists (machine-readable)

Canonical copies (do not duplicate):

| File | Contents |
|---|---|
| `../OceanSpin_sample/mpaso_variables` | Selected `mpaso_in` parameters |
| `../OceanSpin_sample/restart_variables` | Selected restart deep-ocean fields |

## Supporting metadata in sample tree

Headers, namelists, and DATM stream XML under `../OceanSpin_sample/` describe
the GMPAS-NYF_QU240 sample. Large NetCDF payloads are not versioned (see
repository `.gitignore`).

## Motivation figure

`../../Ocean_EQ.png` — global OHC anomaly by depth band; deep ocean
(2000 m–bottom) shows persistent spinup drift.
