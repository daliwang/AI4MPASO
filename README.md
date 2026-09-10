# AI4MPAS — OceanAISpinup

Learn an **early → equilibrium MPAS-Ocean restart operator** on the QU240 mesh:
map a year-~50 deep T/S restart to year ~600, write it back into MPAS-Ocean, and
beat persistence on deep temperature and OHC 2000 m–bottom.

This branch is the **handoff packet** (code + docs). Tensors and NetCDF payloads
are not in git.

## Start here

| Order | Doc | Why |
|---|---|---|
| 1 | [`prototype/README.md`](prototype/README.md) | How to run the e2e pilot; metrics from 2026-09-10 |
| 2 | [`data/docs/AIREADY_DATASET.md`](data/docs/AIREADY_DATASET.md) | Portable pack for a second GPU cluster (~113 MB, not the 19 GB dump) |
| 3 | [`OceanAISpinup_Prototype_Plan.md`](OceanAISpinup_Prototype_Plan.md) | What shipped, roles after handoff |
| 4 | [`tutorials/README.md`](tutorials/README.md) | Tutorials (to be added on this branch) |

Architecture and data freeze (read when you need the *why*):

- [`OceanAISpinup_Start_Report.md`](OceanAISpinup_Start_Report.md) — Frontier audit, pair recipe
- [`OceanAISpinup_Implementation_Plan.md`](OceanAISpinup_Implementation_Plan.md) — IO contract, tracks
- [`OceanAISpinup_Diffusion_Evaluation.md`](OceanAISpinup_Diffusion_Evaluation.md) — do **not** train GenCast on 60 NYF pairs
- [`OceanAISpinup_Development_Plan.md`](OceanAISpinup_Development_Plan.md) — GraphCast / LandSim review
- [`data/docs/README.md`](data/docs/README.md) — DATM, namelist, deep-ocean variables, archive layout

## Run the prototype (Frontier)

```bash
module load cray-python/3.11.7
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH="$PWD"
python -m oceanai.run_prototype --stage all
```

January-only smoke: `python -m oceanai.run_prototype --stage all --smoke`

## Train somewhere other than Frontier

Do **not** copy Kang’s ~19 GB `Dali/` tree. Build or copy the AI-ready pack:

```bash
python -m oceanai.data.pack_aiready --templates jan1-holdout
# → data/aiready/OceanAISpinup-QU240-aiready-v1.0.0.tar.gz  (~113 MB)
```

On the destination cluster:

```bash
tar -xzf OceanAISpinup-QU240-aiready-v1.0.0.tar.gz
export OCEANAI_PROCESSED=/absolute/path/to/QU240
export PYTHONPATH=/path/to/AI4MPAS
python -m oceanai.data.pack_aiready --verify-only
```

Details: [`data/docs/AIREADY_DATASET.md`](data/docs/AIREADY_DATASET.md).

## Layout

```
oceanai/                 # pair factory, GNN, writeback, packager
prototype/README.md      # commands + holdout table
data/docs/               # variable selection + AI-ready card
data/OceanSpin_sample/   # headers, namelists (no NetCDF)
tutorials/               # handoff tutorials (add here)
```

Gitignored: `.venv/`, `data/processed/`, `data/aiready/` (the tensor pack), `*.nc`.

## Who owns what after handoff

| Person | Owns |
|---|---|
| **Olawale** | Pair factory, scalers, training loop |
| **Alice** | OHC QC, maps, holdout interpretation |
| **Hyun** | MPAS-Analysis, N-day forward from `*.ml.nc` |
| **Dali** | Advisor: restart contract, what *not* to build |

## Handoff branch cleanup

Dropped from this branch (still on `main` if you need them): meeting scratch,
duplicate variable lists, early GraphCast init slides/PDF, and one-off slide
generators. See [`docs/HANDOFF.md`](docs/HANDOFF.md).
