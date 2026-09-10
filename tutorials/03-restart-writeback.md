# 03 — Restart writeback

**Time:** 15 minutes.  
**You need:** `netCDF4`, one X restart template, deep T/S arrays, `deep_mask.npz`.  
**Success:** a new `*.nc` that opens, keeps mesh/velocity/thickness, and changes **only** deep `temperature` and `salinity` on valid columns.

This is the **contract**. If writeback is wrong, the GNN does not matter.

## Rule

1. **Copy** the early (X) restart of that pair — that file is the template.
2. Overwrite `temperature` and `salinity` on **k = 46…60** where the deep mask is True.
3. Leave everything else: `layerThickness`, `normalVelocity`, barotropic auxiliaries, mesh, fill values on inactive cells.
4. **Keep `xtime` from the template** in the prototype (early date). Do not invent `ssh` (it is not in the restart).

History tracers (`timeMonthly_avg_activeTracers_*`) are monthly means. **Never** write them into a restart.

## Dry run: truth-Y (no neural net)

Overwrite X’s deep T/S with **Y’s** deep T/S. OHC of the new file must match Y (small error from using X thickness).

On Frontier this is `python -m oceanai.run_prototype --stage truth-writeback`.

By hand:

```python
from oceanai.data.extract import load_pair
from oceanai.io.write_restart import write_deep_ts
from oceanai.mesh.deep_mask import load_deep_mask
from oceanai.paths import early_rst, late_rst, processed_dirs
from oceanai.qc.ohc import ohc_from_restart

mask = load_deep_mask()
p = load_pair("0051-01")
out = processed_dirs()["restarts_ml"] / "rst.0051-01-01.truthY.nc"
write_deep_ts(early_rst(51, 1), out, p["t_y"], p["s_y"], mask)

ohc_w = ohc_from_restart(out, mask)
ohc_y = ohc_from_restart(late_rst(601, 1), mask)
rel = abs(ohc_w["global"] - ohc_y["global"]) / abs(ohc_y["global"])
print("rel_err", f"{rel:.3e}")   # published: ~7.5e-4
```

If `rel_err` is not ≪ 1%, stop. The GNN cannot fix a broken writer.

## ML restart (holdout January)

`run_prototype --stage infer` writes `data/processed/QU240/restarts_ml/rst.0055-01-01.ml.nc` from the trained checkpoint, using the **0055-01 X file** as template.

Off Frontier, with the AI-ready pack (`--templates jan1-holdout`):

```python
from pathlib import Path
from oceanai.data.extract import load_pair
from oceanai.io.write_restart import write_deep_ts
from oceanai.mesh.deep_mask import load_deep_mask
from oceanai.paths import processed_dirs, rst_name

mask = load_deep_mask()
# t_hat, s_hat: (7153, 15) from your model; demo = copy X (persistence)
p = load_pair("0055-01")
t_hat, s_hat = p["t_x"], p["s_x"]

tmpl = processed_dirs()["templates"] / rst_name(55, 1)
out = Path("rst.0055-01-01.ml.nc")
write_deep_ts(tmpl, out, t_hat, s_hat, mask)
print("wrote", out, "from", tmpl)
```

## What to inspect

```bash
ncdump=/opt/cray/pe/netcdf/4.9.0.7/bin/ncdump   # Frontier
$ncdump -h rst.0055-01-01.ml.nc | head
$ncdump -v xtime rst.0055-01-01.ml.nc | tail
```

| Check | Expect |
|---|---|
| Dims | `nCells=7153`, `nVertLevels=60`, `Time=1` |
| `xtime` | Same as template (`0055-01-01_00:00:00` for the demo) |
| Shallow T/S (k < 46) | Identical to template |
| Deep T/S on valid columns | Your prediction (or Y, for truth-Y) |
| `layerThickness`, `normalVelocity` | Identical to template |
| Fill / NaN storms on land | None in overwritten levels |

Code: `oceanai/io/write_restart.py` (`write_deep_ts`). Invalid mask points keep template values.

## Frozen vs predicted

| Field | v1 |
|---|---|
| Deep `temperature`, `salinity` | **Predict** (residual added to X) |
| `layerThickness` | Copy X |
| `normalVelocity` and barotropic | Copy X |
| Mesh / `areaCell` / `refBottomDepth` | Copy X |
| `xtime` | Copy X (document if you stamp year 600) |

## Next

Hyun: [05 — short forward from the ML restart](05-forward-mpas.md).  
Review the three-way snapshot: [06](06-restart-snapshot.md).  
Alice: [04 — OHC of that file vs Y vs persistence](04-metrics-and-ohc.md).
