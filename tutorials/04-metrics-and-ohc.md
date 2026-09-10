# 04 — Metrics and deep OHC

**Time:** 20 minutes.  
**You need:** pair tensors (`OCEANAI_PROCESSED` or Frontier `processed/`). Raw history is optional.  
**Success:** you can recompute persistence deep-T RMSE on `0051-01` (~1.438 °C) and explain the ~10% restart-vs-history OHC gap.

Published table: [`prototype/README.md`](../prototype/README.md).

## What we score

On the **deep mask only**, weights = `areaCell × layerThickness` (X thickness):

- RMSE and bias of **temperature** (°C) and **salinity**
- Global **OHC 2000 m–bottom** (J)

Persistence means \(\hat T = T_X\), \(\hat S = S_X\). The GNN must beat that on holdout T and OHC. Salinity drift over 550 years is small; do not over-claim S skill.

Split: **train 48** (51–54 → 601–604), **holdout 12** (55 → 605). Never mix 1-month pairs into this loss.

## OHC formula

Restarts store 3D T, not a pre-integrated OHC band. Code: `oceanai/qc/ohc.py`.

\[
\mathrm{OHC}_{2000}^{\mathrm{bot}}
= \rho_0 c_p \sum_i \sum_{k \in \mathrm{deep}} T^{\mathrm{K}}_{i,k}\, h_{i,k}\, A_i
\]

- \(\rho_0 = 1026\), \(c_p = 3996\) (from `mpaso_in` / `oceanai.paths`)
- \(T^{\mathrm{K}} = T_{^\circ\mathrm{C}} + 273.15\) — MPAS AM `oceanHeatContent*` uses Kelvin
- Training residuals stay in **°C**; only the OHC diagnostic converts

## Persistence from tensors (no history files)

```python
from oceanai.data.extract import load_pair
from oceanai.data.pair_index import load_pair_index
from oceanai.mesh.deep_mask import load_deep_mask
from oceanai.baselines.persistence import persistence_on_pair, evaluate_persistence

mask = load_deep_mask()
p = load_pair("0051-01")
m = persistence_on_pair(p, mask["areaCell"])
print("0051-01 RMSE T", round(m["rmse_t"], 3), "C  bias", round(m["bias_t"], 3))
print("OHC rel_err", f"{m['ohc_rel_err']:.4f}")

# all 60 (or whatever is in the index)
rows = load_pair_index()
bl = evaluate_persistence(rows, mask["areaCell"])
print("holdout RMSE T", bl["summary"]["holdout_rmse_t"])
```

Expect (2026-09-10 extract):

| | deep T RMSE | notes |
|---|---|---|
| Persistence `0051-01` | **1.438 °C** | bias ≈ +1.38 °C (late ocean cooler) |
| Persistence holdout (12 mo) | **1.433 °C** | |
| Prototype GNN holdout | **0.388 °C** | mostly large-scale cooling; easy to fit with 48 graphs |

JSON on disk: `baselines/persistence.json` (pairs + `summary.holdout_rmse_t`). Model: `baselines/model_holdout.json`.

## Restart OHC vs history AM

`run_prototype --stage qc` compares restart-integrated OHC to:

- monthly stats: `timeMonthly_avg_oceanHeatContent2000mToBot`
- AM: `oceanHeatContent2000mToBot`

A **~10%** relative gap is expected: history uses a continuous 2000 m cut and monthly-mean T; we sum **instantaneous** restart T on **15 discrete** k=46…60 levels. Do not “fix” the mask to chase AM. Truth-Y writeback (restart vs restart) is the IO test; AM is a sanity check.

```python
from oceanai.qc.ohc import compare_restart_to_history
from oceanai.mesh.deep_mask import load_deep_mask
from oceanai.paths import early_rst

mask = load_deep_mask()
print(compare_restart_to_history(early_rst(51, 1), 51, 1, mask))
```

Needs `OCEANAI_RAW` (history files). Skip this on a dest cluster that only has the tensor pack.

## Maps (Alice)

Holdout deep **ΔT** (Y − X) is the signal: basin-scale cooling. Plot per cell:

```python
import numpy as np
from oceanai.data.extract import load_pair
from oceanai.mesh.deep_mask import load_deep_mask

mask = load_deep_mask()
p = load_pair("0055-01")
# column-mean ΔT on valid deep points (°C)
dt = np.where(p["valid"], p["t_y"] - p["t_x"], np.nan)
col = np.nanmean(dt, axis=1)
lat, lon = np.degrees(mask["latCell"]), np.degrees(mask["lonCell"])
# scatter(lon, lat, c=col) with your usual cartopy / matplotlib
```

Compare three maps: truth (Y−X), persistence (0 by construction), model (\(T_{\hat Y}-T_X\)). Basin RMSE is a later refinement; global area×h RMSE is the prototype number.

## Honest reading of skill

- 48 training graphs on one NYF case **will** overfit a large net. The prototype net is small on purpose.
- Holdout is the same seasonal cycle **one year later**, not an independent spinup.
- Temperature skill is mostly a **mean cooling**; salinity change is tiny.
- Beating persistence on T + writing a legal restart **is** the prototype bar. “Near equilibrium” vs year 605 is Alice’s call.

## Next

[05](05-forward-mpas.md) — whether that restart integrates.  
[03](03-restart-writeback.md) — if OHC of `*.ml.nc` looks insane, the writer is first suspect.
