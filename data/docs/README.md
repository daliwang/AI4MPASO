# AI4MPAS Ocean Spinup — Variable Selection Docs

Documentation of atmospheric forcing, MPAS-Ocean physics configs, and restart
deep-ocean state variables selected for AI training.

| Document | Topic |
|---|---|
| [DATM_FORCING_VARIABLES.md](DATM_FORCING_VARIABLES.md) | DATM CORE2_NYF forcing: Tier-1 `u,v,t,slp` + GXGXS precip `prc` |
| [MPASO_PHYSICS_CONFIG_INPUTS.md](MPASO_PHYSICS_CONFIG_INPUTS.md) | Selected `mpaso_in` physics / numerics namelist inputs |
| [RESTART_DEEP_OCEAN_STATE.md](RESTART_DEEP_OCEAN_STATE.md) | Restart deep ocean (2000 m–bottom): input@~50yr, target@~600yr |

## Selection lists (machine-readable)

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
