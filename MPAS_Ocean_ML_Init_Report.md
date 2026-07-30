# MPAS-Ocean initialization via GraphCast-style GNN and LandSim-style workflow

**Companion slides:** `MPAS_Ocean_ML_Init_Deck.pptx` — three slides (MPAS initiative overview, GraphCast GNN / mesh I/O, roadmap).

**Analysis and report** — combining the unstructured-mesh GNN approach from GraphCast with the multi-source, early-to-equilibrium workflow pattern from LandSim, applied to **MPAS-Ocean** spinup and restart generation (E3SM v3 context).

**References in this workspace**

- `graphcast/` — GraphCast / GenCast: `TypedGraph`, `deep_typed_graph_net.py`, sparse mesh transformer, icosahedral / grid–mesh connectivity.
- `MPAS_Ocean_Users_Guide_E3SM_V3.0.0.pdf` — mesh, streams, restart and history output definitions (authoritative for variable names and file layout).
- `Copy of Running MPAS-Ocean on Perlmutter and Frontier.txt` — build (`ocean_model`), QU240 test case, `output.nc`, `namelist.ocean`, METIS `graph.info` / `gpmetis`, Slurm, G-case scripts.

LandSim is described here as in the project intent: **multiple data sources**, **early or partial spinup states**, and a **transformer** that targets a **steady or long-equilibrated** land model state; the ocean analogue is **long ocean spinup** or an accepted **restart-quality** 3D state.

---

## GraphCast: how the GNN uses the mesh and simulation I/O

This summary follows the implementation in `graphcast/graphcast.py` and the module docstring there.

**Role of the mesh.** GraphCast does **not** run the physics GNN directly on the lat–lon analysis grid. It uses a **hierarchy of spherical triangular meshes** (`icosahedral_mesh.get_hierarchy_of_triangular_meshes_for_sphere`), merges them for multi-scale edges, and places **mesh nodes at triangle vertices**. Static **node and edge features** include positions on the sphere and relative geometry (`model_utils.get_graph_spatial_features`).

**Three-stage GNN (all are `DeepTypedGraphNet` on `TypedGraph`s).**

1. **Grid → mesh (`grid2mesh_gnn`).** Builds a **bipartite** graph: regular **grid nodes** (lat–lon) connect to **mesh nodes** via `grid_mesh_connectivity.radius_query_indices` (neighbors within a radius tied to mesh resolution). The GNN **aggregates gridded inputs** onto the mesh and produces a **latent state on mesh nodes** (and updated grid latents).

2. **Mesh processor (`mesh_gnn`).** Message passing **only on the mesh**: edges come from the **merged multi-level** triangulation (`icosahedral_mesh.merge_meshes`, `faces_to_edges`). This is where **unstructured horizontal communication** happens across scales.

3. **Mesh → grid (`mesh2grid_gnn`).** Another **bipartite** graph: each **grid point** links to the **three mesh vertices** of the spherical triangle that contains it (`grid_mesh_connectivity.in_mesh_triangle_indices`). The GNN **decodes** mesh latents back to **per grid-node** outputs.

**Simulation data layout.** Atmospheric state and forcings are treated as **stacked fields on the grid nodes** (surface + pressure levels, time in the batch). The model learns to **interpolate between grid and mesh**; **training loss and rollouts are evaluated on the regular grid** (ERA5 / operational lat–lon), not on an unstructured output mesh.

**MPAS analogy.** MPAS-Ocean already lives on an **unstructured horizontal mesh**; a GraphCast-style design could **skip grid2mesh/mesh2grid** for native-cell prediction, or retain a **bipartite** link if you fuse reanalysis on a regular grid with MPAS cell fields.

---

## 1. Objective and success criteria

**Goal:** Produce **MPAS-Ocean restart-quality** 3D state (and required 2D auxiliary fields) from **short early spinup** and **external ocean analyses**, reducing wallclock and human iteration for initialization while remaining **dynamically consistent enough** for standalone or coupled (G-case) production runs.

**Success criteria (examples)**

- Global or regional **RMSE** (and bias) vs a reference long spinup on **T, S, u, v**, and **SSH** on native cells.
- **Stratification / stability sanity** vs reference (no systematic static instability).
- **Short forward test:** restart from the ML-generated state, integrate **N days**, compare drift to restart-from-full-spinup using the same forcings and workflow as in the Perlmutter/Frontier notes.

---

## 2. Inputs and labels (LandSim-like workflow)

| Role | Sources |
|------|--------|
| **Early / partial dynamics** | Short MPAS-Ocean runs (e.g. days to months); multiple trajectory lengths improve robustness. |
| **External context** | Reanalysis or analysis **T, S, SSH** (optional: wind / flux summaries) for matching dates—not required on the MPAS mesh at raw resolution. |
| **Graph geometry** | Fixed **MPAS mesh**: cell connectivity, edges, cell area, bottom depth, Coriolis, etc. (static features). |
| **Target (supervision)** | **Long spinup** or accepted equilibrium: restart file and/or history (`output.nc`-style) on the **same mesh**, per the user guide. |

**Analogy:** LandSim maps **multi-stream inputs + truncated spin** → **ELM steady state**; here we map **multi-stream inputs + short ocean integration** → **long spinup / restart fields**.

---

## 3. Graph and GNN (GraphCast-inspired)

1. **Build a `TypedGraph`** consistent with MPAS topology (e.g. **cells as primary graph nodes**, edges from shared faces / neighbor relations—final choice should match where prognostic variables live in MPAS-Ocean’s C-grid layout per the user guide).
2. **Node features:** bathymetry, geographic position, **early-spinup** layer **T, S, u, v** (thickness-weighted where needed), optional **analysis** interpolated to cell centers.
3. **Edge features:** edge length, **differences** of T/S across cells, optional rotation-aware features for Coriolis-dominated messaging.
4. **Backbone:** **Deep typed GNN** with **sparse attention on the mesh** (same *idea* as GraphCast’s mesh processor: unstructured operators that transfer across resolutions when only the graph changes).

**Optional multi-scale hierarchy:** GraphCast uses refined icosahedral meshes; for MPAS, consider **coarsened graphs** (e.g. METIS aggregates) for multi-scale message passing.

---

## 4. Temporal and fusion head (transformer)

- **Tokens:** Per-cell latents from the GNN at one or several early times \(t_1,\ldots,t_k\), plus **global / context** tokens (basin indices, season, mixed-layer depth proxies from analysis, etc.).
- **Transformer:** Compact **temporal transformer** or **Perceiver-style** pooling over time, with optional **cross-attention** to tokens built from reanalysis (LandSim-style fusion of multiple streams).
- **Output head:** Predict **full target** 3D fields and **SSH**, or a **residual correction** to the early state; optionally add **weak constraints** (smoothness, stratification penalty, mass-balance projection for SSH if required by your experiment design).

---

## 5. Training strategy

- **Dataset:** Examples of (mesh, external fields, **short run**, **long spinup**) with varied forcings, segment lengths, and ideally multiple meshes.
- **Loss:** L2 (or Huber) on prognostic fields with **cell-area weighting** (GraphCast uses latitude weighting on a sphere; MPAS uses native areas).
- **Validation:** Hold out basins, years, or meshes; test **zero-shot** on new mesh versions if the graph builder is generic.

---

## 6. Integration with HPC workflow (Perlmutter / Frontier)

From the local procedure notes:

- Clone E3SM, build `component/mpas-ocean` → **`ocean_model`**.
- Configure **`namelist.ocean`** (e.g. `config_run_duration`), streams, and Slurm jobs.
- History output example: **`output.nc`**; partitioning via **`graph.info`** and **`gpmetis`**.
- Coupled workflow: G-case scripts (e.g. `run_e3sm.v3.GMPAS-IAF_EC30to60E2r2.sh`), run directory layout, timing logs.

The ML pipeline must emit **NetCDF** in the **restart / initial condition** schema expected by MPAS-Ocean (dimensions such as `nCells`, `nVertLevels`, exact variable names from the user guide).

---

## 7. Phased roadmap

1. **Schema lock:** From the user guide, list all restart variables and stream templates required for a cold start vs restart.
2. **Graph builder:** MPAS mesh files → `TypedGraph`; unit tests on **QU240** (or your standard test mesh).
3. **Baselines:** Persistence and analysis-only interpolation vs long spinup.
4. **GNN-only:** Single-time early snapshot → target state.
5. **+ Transformer:** Multi-time early trajectory + reanalysis fusion.
6. **Production hardening:** Restart tests on Perlmutter/Frontier; compare short forward runs and document computational savings.

---

## 8. Risks and mitigations

| Risk | Mitigation |
|------|------------|
| **Distribution shift** (new mesh / forcing) | Train on multiple meshes; graph-native architecture; domain randomization. |
| **Conservation / dynamical inconsistency** | Post-process barotropic / SSH if needed; conservation-aware losses or projection steps. |
| **Cost of long-spinup labels** | Fewer, curated long runs; semi-supervised use of short trajectories. |

---

## 9. Slide deck summary (see `MPAS_Ocean_ML_Init_Deck.pptx`)

### Slide 1 — Title concept

**Title:** Learning MPAS-Ocean spinup states with a mesh GNN and fusion transformer  

**Subtitle:** GraphCast-style unstructured operators + LandSim-style multi-source, early-to-equilibrium workflow  

**Bullets:** Problem (long spinup, unstructured mesh); approach (mesh GNN + transformer over early runs and analyses); deliverable (restart-compatible NetCDF for existing `ocean_model` workflows).

### Slide 2 — GraphCast GNN: mesh and gridded I/O

Aligned with **§ GraphCast: how the GNN uses the mesh and simulation I/O** (lines 17–33 above). The slide includes a schematic figure: **`graphcast_gnn_mesh_schematic.png`** (grid ↔ unstructured mesh ↔ grid, three GNN stages, loss on lat–lon). Regenerate with **`generate_graphcast_schematic.py`** (requires matplotlib).

**Title:** GraphCast: how the GNN uses the mesh and simulation I/O  

**Subtitle:** Summary follows `graphcast/graphcast.py` and the module docstring there.

**Bullets:** Role of the mesh (not lat–lon-native GNN; icosahedral hierarchy, merged multi-scale edges, vertices, `get_graph_spatial_features`); three `DeepTypedGraphNet` stages—grid2mesh (`radius_query_indices`), mesh (`merge_meshes`, `faces_to_edges`), mesh2grid (`in_mesh_triangle_indices`); simulation data layout (stacked grid fields, loss/rollouts on regular grid); MPAS analogy (optional skip of grid2mesh/mesh2grid or bipartite reanalysis fusion).

### Slide 3 — Execution

**Title:** Roadmap, data, and validation on Perlmutter / Frontier  

**Bullets:** Inputs (user guide, spinup pairs, reanalysis); six-step technical roadmap; success = accuracy vs reference + wallclock saved per new case.

---

## 10. Next steps when spinup archive is available

1. Dump NetCDF headers for **restart** and **history** files and align with the user guide tables.  
2. Fix the training target horizon (e.g. “equilibrium” definition: calendar time vs drift threshold).  
3. Register exact meshes (QU240, EC30to60E2r2, etc.) used for training vs evaluation.  
4. Run the **short forward** restart test protocol from the HPC notes for every model version bump.

---

*Generated for the AI4MPASO / MPAS-Ocean ML initialization concept. Companion deck: `MPAS_Ocean_ML_Init_Deck.pptx`.*
