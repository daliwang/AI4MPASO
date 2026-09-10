# Handoff branch

Branch: **`handoff/prototype-e2e`**  
Date: 2026-09-10

This is the tree to clone for team takeover. `main` still has early notes and
slide binaries if someone needs them.

## What to read

1. [`docs/handoff_briefing.html`](handoff_briefing.html) — short live intro (← → keys)
2. [`docs/ARCHITECTURE_AND_DESIGN.md`](ARCHITECTURE_AND_DESIGN.md) — architecture handout for talks (GraphCast/LandSim, data, variables, per-level tables)
3. Repo [`README.md`](../README.md)
4. [`tutorials/README.md`](../tutorials/README.md) — on-ramp
5. [`prototype/snapshots/0055-01/compare.md`](../prototype/snapshots/0055-01/compare.md) — X / ML / Y
6. [`prototype/README.md`](../prototype/README.md) — run + metrics
7. [`data/docs/AIREADY_DATASET.md`](../data/docs/AIREADY_DATASET.md) — off-Frontier pack
8. [`OceanAISpinup_Prototype_Plan.md`](../OceanAISpinup_Prototype_Plan.md) — roles

## What is in git vs not

| In git | Not in git |
|---|---|
| `oceanai/`, docs, sample headers/namelists | `data/processed/QU240/` working extract |
| `prototype/snapshots/0055-01/` (tables + SVG maps) | 57 MB ML/X/Y NetCDF restarts |
| `requirements.txt`, `prototype/README.md` | `data/aiready/` tensor pack (~113 MB tarball) |
| | Kang raw dump (~19 GB on Frontier Lustre) |
| | `.venv/`, checkpoints, `*.ml.nc` |

Frontier pack on this machine (not versioned):

`/lustre/orion/lrn105/proj-shared/wangd/AI4MPAS/data/aiready/OceanAISpinup-QU240-aiready-v1.0.0.tar.gz`

## Removed from this branch (kept on `main`)

Working notes and bulky one-offs that are not the operator contract:

| Path | Why dropped |
|---|---|
| `background.txt` | 2026-06-22 meeting scratch |
| `selected_variables.txt` | Duplicate of `data/OceanSpin_sample/mpaso_variables` |
| `Copy of Running MPAS-Ocean on Perlmutter and Frontier.txt` | Early ops dump |
| `MPAS_Ocean_ML_Init_Report.md` | Pre-prototype GraphCast/LandSim sketch |
| `MPAS_Ocean_ML_Init_Deck.pptx`, `MPASOcean_init_plan.pptx`, `OceanAISpinup_Implementation_Slides.pptx` | Slide decks |
| `MPAS_Ocean_Users_Guide_E3SM_V3.0.0.pdf` | Vendor PDF; use E3SM docs |
| `generate_graphcast_schematic.py`, `generate_implementation_slides.py` | One-off generators |
| `graphcast_gnn_mesh_schematic.png`, `GraphCast_gridhandling.png` | Generator outputs |
| `data/docs/mpaso_variables`, `data/docs/restart_variables` | Duplicates of `data/OceanSpin_sample/` |

Kept: `Ocean_EQ.png` (deep OHC motivation).

## Do not do (unless the data change)

1. Train diffusion / GenCast on 60 NYF pairs.
2. Interpolate T/S to lat–lon for a ViT/UNet.
3. Write history `activeTracers_*` into a restart.
4. Treat DATM or `mpaso_in` as causal until a second case exists.
