# QU240 pilot: early→equilibrium restart operator

End-to-end demonstration on Kang’s Frontier dump. **Not** a diffusion model.

**Contract:** year ~50 restart (deep T/S) → year ~600 deep T/S → copy-template MPAS restart.

## Run on Frontier

```bash
cd /lustre/orion/lrn105/proj-shared/wangd/AI4MPAS
module load cray-python/3.11.7
source .venv/bin/activate          # created once: python3 -m venv .venv && pip install -r requirements.txt

python -m oceanai.run_prototype --stage all
# faster January-only demo:
python -m oceanai.run_prototype --stage all --smoke
```

Stages: `prepare` → `qc` → `baseline` → `truth-writeback` → `train` → `infer`.

## What it does

1. **60 month-aligned pairs** `005y-MM → 060y-MM` (Δ = 550 yr). Train years 51–54 (48); hold out 55→605 (12).
2. Deep mask **k = 46…60** (`refBottomDepth` > 2000 m): 7153 cells, 63 228 valid deep points.
3. Cell graph from `cellsOnCell` (41 018 directed edges, max degree 6).
4. DATM NYF monthly on the same cells (`q_10` clamped ≥ 0).
5. Persistence baseline, then a **tiny residual GraphSAGE** (6 layers, hidden 64, CPU).
6. Writeback overwrites **only** deep `temperature` and `salinity`. `xtime` stays on the template (early date). Thickness and velocity are unchanged.

## Artifacts (not in git)

```
data/processed/QU240/
  pairs/index.csv|.json     60-row table
  pairs/YYYY-MM.npz
  deep_mask.npz  mesh_graph.npz  datm_monthly.npz
  scalers/scalers.json
  baselines/persistence.json  ohc_qc.json  truthY_writeback.json  model_holdout.json
  checkpoints/track_a_proto.pt
  restarts_ml/rst.0055-01-01.ml.nc      # demo ML restart
  restarts_ml/rst.0051-01-01.truthY.nc  # dry-run: Y deep T/S into X template
```

## Metrics from this run (2026-09-10, 15 epochs, CPU)

Area × layer-thickness weighted RMSE on the deep mask. OHC uses T in Kelvin (`T_C+273.15`) × ρ₀=1026 × cₚ=3996 × `areaCell` × `layerThickness`.

| Check | Result |
|---|---|
| Persistence **0051-01 → 0601-01** deep T RMSE | **1.438 °C** (bias +1.38 °C) |
| Persistence holdout deep T RMSE (12 months) | **1.433 °C** |
| Persistence holdout deep S RMSE | 0.073 |
| Persistence holdout OHC rel. err. | 0.43% |
| **Model holdout deep T RMSE** | **0.388 °C** (beats persistence) |
| Model holdout deep S RMSE | 0.069 (small gain) |
| Model holdout OHC rel. err. | **0.063%** |
| Model **0055-01** deep T RMSE | 0.392 °C vs persist 1.433 °C |
| Truth-Y writeback OHC vs Y | rel. err. **7.5×10⁻⁴** (h from X, T/S from Y) |
| Restart vs history OHC AM | ~10% (discrete k=46–60 vs AM 2000 m interpolation) |

The temperature skill is mostly a **large-scale cooling** that 48 pairs can fit. Salinity change over 550 yr is small; do not over-claim. The prototype **ships the contract** (loader → net → restart). Better GNNs and a forward MPAS test are the team’s next work.

`ncdump -v xtime data/processed/QU240/restarts_ml/rst.0055-01-01.ml.nc` → `0055-01-01_00:00:00` (template time).

## Honest limitations

- One NYF case, one mesh, 48 train graphs — easy to overfit; holdout is the same seasonal cycle one year later.
- History OHC is a monthly mean with a continuous 2000 m cut; restart OHC is instantaneous on 15 discrete levels.
- No edge `normalVelocity`, no diffusion/flow, no N-day MPAS forward (Hyun after handoff).
- Login-node CPU only in this demo.

## Handoff

See `OceanAISpinup_Prototype_Plan.md`. Olawale: dataGEN/training. Alice: OHC maps. Hyun: forward test. Dali advises; do **not** train GenCast on these 60 pairs.

Branch: `handoff/prototype-e2e`. On-ramp: [`tutorials/README.md`](../tutorials/README.md).

## Off-Frontier: AI-ready pack

Do not copy the 19 GB raw dump. On Frontier:

```bash
python -m oceanai.data.pack_aiready --templates jan1-holdout
```

That writes `data/aiready/OceanAISpinup-QU240-aiready-v1.0.0.tar.gz` (~113 MB): 60 pair tensors, mesh graph, monthly NYF, scalers, persistence JSON, and one X restart template for writeback. On the other cluster set `OCEANAI_PROCESSED` to the unpacked `QU240/` directory. Full card: `data/docs/AIREADY_DATASET.md`.

