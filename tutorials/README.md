# Tutorials (handoff)

Add walkthroughs on this branch so a new developer can run the operator without
reading every plan document.

Nothing here yet except this index. Suggested pages (create as you go):

| Tutorial | Audience | Should cover |
|---|---|---|
| `01-frontier-prototype.md` | Anyone on OLCF | `module load`, venv, `python -m oceanai.run_prototype --stage all --smoke`, where artifacts land |
| `02-aiready-pack.md` | Off-Frontier GPU cluster | Build/copy the tar, `OCEANAI_PROCESSED`, `pack_aiready --verify-only`, load one pair |
| `03-restart-writeback.md` | Olawale / Hyun | Template copy, deep T/S only, `ncdump`, truth-Y test |
| `04-metrics-and-ohc.md` | Alice | Persistence vs model table, OHC formula, holdout maps |
| `05-forward-mpas.md` | Hyun | N-day ocean-only forward from `rst.0055-01-01.ml.nc` |

Code already has:

```bash
python -m oceanai.run_prototype --stage all
python -m oceanai.data.pack_aiready --templates jan1-holdout
python -m oceanai.data.pack_aiready --verify-only
```

Dataset card: [`data/docs/AIREADY_DATASET.md`](../data/docs/AIREADY_DATASET.md)  
Pilot README: [`prototype/README.md`](../prototype/README.md)
