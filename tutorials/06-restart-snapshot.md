# 06 — Snapshot the AI restart vs X and Y

**Time:** ~5 minutes after an ML restart exists.  
**You need:** Frontier (or templates + Y restart), `rst.0055-01-01.ml.nc`.  
**Success:** `prototype/snapshots/0055-01/compare.md` with contract checks ~0 and deep-T RMSE ML ≪ persistence.

This is the review artifact for “did writeback do the right thing, and is deep T closer to year 605 than year 55?”

## Three files

| Role | What | This demo |
|---|---|---|
| **X** | Early / initial restart (template) | `rst.0055-01-01` |
| **ML** | Copy of X with deep T/S overwritten by the model | `data/processed/QU240/restarts_ml/rst.0055-01-01.ml.nc` |
| **Y** | Late simulation (ground truth) | `rst.0605-01-01` |

Create ML first if needed: [01](01-frontier-prototype.md) or [03](03-restart-writeback.md).

## Generate

```bash
export PYTHONPATH="$PWD"
python -m oceanai.qc.snapshot
```

Writes `prototype/snapshots/0055-01/`:

- `compare.md` — tables (contract, deep T/S, OHC, per-level means, 3 example columns)
- `compare.json` — same numbers, machine-readable
- `map_T_X.svg` / `map_T_ML.svg` / `map_T_Y.svg` / `map_T_ML_minus_Y.svg` — column-mean deep T

Open `compare.md` in the editor. Open the SVGs for a global picture (blue = colder).

Custom ML path:

```bash
python -m oceanai.qc.snapshot --ml /path/to/rst.0055-01-01.ml.nc --out prototype/snapshots/0055-01
```

## How to read it

1. **Contract table** — max \|ML−X\| on shallow T/S, `layerThickness`, `normalVelocity` must be ~0. If not, writeback leaked.
2. **Deep T means** — Y is much colder than X (~1.4 °C). ML should sit near Y, not X.
3. **RMSE vs Y** — persistence ~1.43 °C; prototype ML ~0.39 °C on this holdout January.
4. **OHC** — relative error vs Y should drop (here 0.43% → 0.065%).
5. **Per-level T** — ML−Y should be tens of hundredths of a degree, not ~1.4 °C like X−Y.
6. **Example columns** — deepest / equator / Southern Ocean: ML follows Y’s cooling with the X profile as the starting point.

Published snapshot from 2026-09-10: [`prototype/snapshots/0055-01/compare.md`](../prototype/snapshots/0055-01/compare.md).
