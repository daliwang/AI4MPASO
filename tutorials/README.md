# Tutorials

Start with **[00 — Concepts](00-concepts.md)** (five minutes). Then pick **one** path:

| If you are… | Do this |
|---|---|
| New to the project | [00](00-concepts.md) → [01](01-frontier-prototype.md) smoke run **or** [02](02-aiready-pack.md) if you have the tarball |
| On Frontier with Kang’s dump | [01 — Frontier prototype](01-frontier-prototype.md) |
| Moving to another GPU cluster | [02 — AI-ready pack](02-aiready-pack.md) |
| Touching restart files | [03 — Writeback](03-restart-writeback.md) |
| Checking skill / OHC | [04 — Metrics and OHC](04-metrics-and-ohc.md) |
| Running MPAS on `*.ml.nc` | [05 — Forward](05-forward-mpas.md) |
| Checking an ML restart vs year 55 and 605 | [06 — Snapshot](06-restart-snapshot.md) |

| # | Tutorial | Time | Needs raw NetCDF? |
|---|---|---|---|
| 00 | [Concepts](00-concepts.md) | 5 min | no |
| 01 | [Frontier prototype](01-frontier-prototype.md) | ~20 min smoke | yes (Frontier) |
| 02 | [AI-ready pack](02-aiready-pack.md) | ~10 min | no (to *use* the pack) |
| 03 | [Restart writeback](03-restart-writeback.md) | ~15 min | template `.nc` only |
| 04 | [Metrics and OHC](04-metrics-and-ohc.md) | ~20 min | no for persistence |
| 05 | [Forward MPAS](05-forward-mpas.md) | recipe | MPAS case files |
| 06 | [Restart snapshot X vs ML vs Y](06-restart-snapshot.md) | ~5 min | ML + X + Y restarts |

Reference (not tutorials): [`prototype/README.md`](../prototype/README.md) (metrics table), [`data/docs/AIREADY_DATASET.md`](../data/docs/AIREADY_DATASET.md) (pack layout).
