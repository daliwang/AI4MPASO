# Restart snapshots (X vs ML vs Y)

Generated comparison of the **AI writeback restart** against the **early** template
and the **late** simulation restart. Not the 57 MB NetCDF files themselves.

| Pair | Report | Maps |
|---|---|---|
| Holdout Jan `0055-01` → `0605-01` | [compare.md](0055-01/compare.md) | `map_T_*.svg` in that folder |

Regenerate (Frontier, after `run_prototype --stage infer`):

```bash
python -m oceanai.qc.snapshot
# → prototype/snapshots/0055-01/
```

Tutorial: [`tutorials/06-restart-snapshot.md`](../../tutorials/06-restart-snapshot.md).
