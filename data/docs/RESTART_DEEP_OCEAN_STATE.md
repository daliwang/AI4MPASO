# Restart Deep-Ocean State Variables for AI Training

**Selection file:** `data/OceanSpin_sample/restart_variables`  
**Header:** `data/OceanSpin_sample/restart/mpas_ocean_header.txt`  
**Motivation figure:** `Ocean_EQ.png` (global OHC anomaly by depth band)

## Activity note

Selected variables from the MPAS-Ocean **restart** file represent the
**deep-ocean state (2000 m to bottom)**. The **same variable names** are used
as:

| Role | Restart time | Purpose |
|---|---|---|
| **Input** | ~50-year restart | Early spinup ocean state |
| **Target** | ~600-year restart | Later spinup ocean state to predict / match |

Sample files present locally (model years on filename):

- `restart/v3.GMPAS-NYF_QU240.mpaso.rst.0661-01-01_00000.nc`
- `restart/v3.GMPAS-NYF_QU240.mpaso.rst.0681-01-01_00000.nc`

Use the project’s designated 50-year and 600-year restarts for training pairs;
the sample pair illustrates the file format.

---

## Why deep ocean (2000 m–bottom)

`Ocean_EQ.png` shows global ΔOHC for four bands during a long spinup:

| Band | Behavior (qualitative) |
|---|---|
| 0 m – bottom | Total OHC rises then plateaus |
| 0 – 700 m | Early gain, then long decline |
| 700 – 2000 m | Slow evolution |
| **2000 m – bottom** | **Persistent, nearly monotonic cooling** — slowest equilibration |

Deep OHC is therefore a primary spinup signal. Restart files do **not** store
pre-integrated OHC bands; they store 3D state from which deep OHC (and deep
T/S/velocity) are obtained by masking layers below 2000 m.

History diagnostic (for validation / global metrics, not restart I/O):

- `timeMonthly_avg_oceanHeatContent2000mToBot` — “Integrated heat content from the 2000m to bottom”

---

## Selected restart variables

### Core 3D prognostic fields (apply deep-layer mask)

| Variable | Dimensions | Units | Role for deep ocean |
|---|---|---|---|
| `temperature` | Time, nCells, nVertLevels | °C | Potential temperature (primary heat-content carrier) |
| `salinity` | Time, nCells, nVertLevels | 1e-3 | Deep water-mass / stratification state |
| `layerThickness` | Time, nCells, nVertLevels | m | Layer mass/volume for OHC & column integrals |
| `normalVelocity` | Time, nEdges, nVertLevels | m/s | Deep circulation (edge-normal) |

### Geometry / indexing (define deep mask & valid columns)

| Variable | Dimensions | Units | Role |
|---|---|---|---|
| `refBottomDepth` | nVertLevels | m | Reference bottom depth of each vertical level |
| `bottomDepth` | nCells | m | Column bottom depth (which cells reach >2000 m) |
| `maxLevelCell` | nCells | — | Last active level in column |
| `minLevelCell` | nCells | — | First active level in column |
| `restingThickness` | nCells, nVertLevels | m | Resting layer thickness (z-star / ALE reference) |

---

## Deep vertical levels on this mesh

From `refBottomDepth` in the sample restart (`nVertLevels = 60`):

| Criterion | Levels (1-based) | Depth range |
|---|---|---|
| `refBottomDepth` ≤ 2000 m | k = 1 … 45 | surface → ~1863 m |
| **`refBottomDepth` > 2000 m** | **k = 46 … 60** | **~2075 m → ~5500 m** |

First deep level: `refBottomDepth[46] ≈ 2074.87 m`  
Bottom: `refBottomDepth[60] ≈ 5499.99 m`

**Deep mask (per cell, level k):**  
`refBottomDepth[k] > 2000` **and** `k ≤ maxLevelCell[i]` **and** `bottomDepth[i] > 2000`.

---

## Derived deep-ocean targets (optional)

From the selected restart fields one can compute:

- Column / global **OHC 2000 m–bottom** (analogous to history `oceanHeatContent2000mToBot`)
- Deep mean temperature / salinity
- Deep kinetic energy from `normalVelocity`

These derived scalars align with the OHC bands in `Ocean_EQ.png` and are useful
as global training metrics alongside 3D fields.

---

## Not selected from restart (out of deep-ocean scope)

Surface / mixed-layer / coupler bookkeeping fields, e.g.:

- `temperatureSurfaceValue`, `salinitySurfaceValue`
- `surfaceVelocityZonal` / `Meridional`
- `boundaryLayerDepth`, `indMLD`, `vertNonLocalFluxTemp`
- `atmosphericPressure`, `seaIcePressure`, frazil accumulators
- Time-stepper auxiliaries (`normalVelocityTendOld`, `CoriolisTermOld`, …)

Mesh connectivity (`latCell`, `edgesOnCell`, …) is assumed available from the
mesh/restart geometry separately if needed for operators.

---

## Relation to other AI input docs

| Doc | Content |
|---|---|
| [`DATM_FORCING_VARIABLES.md`](DATM_FORCING_VARIABLES.md) | Atmospheric forcing (u, v, t, slp, prc, …) |
| [`MPASO_PHYSICS_CONFIG_INPUTS.md`](MPASO_PHYSICS_CONFIG_INPUTS.md) | Static `mpaso_in` physics configs |
| **This doc** | Restart deep-ocean state: early = input, late = target |

**Suggested training pairing:**  
`{DATM forcing, mpaso_in configs, restart@~50yr deep state}` → `{restart@~600yr deep state}`  
(with optional OHC 2000m–bottom metrics for monitoring).
