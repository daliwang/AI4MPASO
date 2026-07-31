# MPAS-Ocean Physics Config Inputs for AI Training

**Source list:** `data/OceanSpin_sample/mpaso_variables`  
**Namelist:** `data/OceanSpin_sample/mpaso_in`  
**Case context:** GMPAS-NYF / CORE2 Normal Year Forcing ocean spinup

These entries are **selected `mpaso_in` namelist parameters** (physics / numerics /
surface coupling), not NetCDF history fields. Treat them as **static model
configuration inputs** for AI training (conditioning features, experiment
metadata, or physics-regime labels), alongside DATM atmospheric forcing
documented in [`DATM_FORCING_VARIABLES.md`](DATM_FORCING_VARIABLES.md).

---

## Role in the AI input stack

| Input class | Source | Nature | Role |
|---|---|---|---|
| Atmospheric forcing (Tier-1 / 1b) | DATM NCEP + GXGXS | Time-varying fields | Primary dynamical / freshwater drivers |
| Ocean physics config (this doc) | `mpaso_in` via `mpaso_variables` | Scalar / flag / enum | Physics scheme and coefficient set |
| Ocean state / targets | history NetCDF | Spatiotemporal fields | Labels or prognostic targets (separate selection) |

For a single fixed spinup case, these configs are **constant in time** but still
important: they define viscosity, eddy closures, vertical mixing, bulk coupling,
and restoring that shape the ocean response the model learns.

---

## Selected parameters (from `mpaso_variables`)

### Horizontal momentum viscosity

| Parameter | Value | Meaning |
|---|---|---|
| `config_use_mom_del2` | `.true.` | Enable Laplacian (del²) viscosity |
| `config_mom_del2` | `4000.0` | Laplacian viscosity coefficient (m²/s) |
| `config_use_mom_del4` | `.true.` | Enable biharmonic (del⁴) viscosity |
| `config_mom_del4` | `2.0e14` | Biharmonic viscosity coefficient (m⁴/s) |

### Redi / isoneutral diffusion

| Parameter | Value | Meaning |
|---|---|---|
| `config_redi_closure` | `'constant'` | Redi diffusivity closure type |
| `config_redi_constant_kappa` | `900.0` | Constant Redi diffusivity (m²/s) |

### Submesoscale (Fox–Kemper / MLE)

| Parameter | Value | Meaning |
|---|---|---|
| `config_submesoscale_enable` | `.true.` | Enable submesoscale parameterization |
| `config_submesoscale_ce` | `0.08` | Efficiency coefficient |
| `config_submesoscale_ds_max` | `100000.0` | Max front width scale (m) |
| `config_submesoscale_lfmin` | `1000.0` | Minimum frontal length scale (m) |
| `config_submesoscale_tau` | `172800` | Timescale (s; 2 days) |

### Gent–McWilliams (GM) eddy transport

| Parameter | Value | Meaning |
|---|---|---|
| `config_gm_closure` | `'constant'` | GM closure type |
| `config_gm_constant_kappa` | `900.0` | Constant GM diffusivity (m²/s) |

### Eddy mixed-layer depth (eddyMLD)

| Parameter | Value | Meaning |
|---|---|---|
| `config_eddymld_dens_threshold` | `0.03` | Density threshold for eddy MLD |
| `config_eddymld_reference_depth` | `10` | Reference depth (m) |

### CVMix vertical mixing (background, convection, KPP, shear)

| Parameter | Value | Meaning |
|---|---|---|
| `config_cvmix_background_scheme` | `'constant'` | Background mixing scheme |
| `config_cvmix_background_viscosity` | `1.0e-4` | Background viscosity (m²/s) |
| `config_cvmix_convective_diffusion` | `1.0` | Convective diffusion (m²/s) |
| `config_cvmix_convective_viscosity` | `1.0` | Convective viscosity (m²/s) |
| `config_cvmix_kpp_criticalbulkrichardsonnumber` | `0.25` | KPP critical bulk Ri |
| `config_use_cvmix_convection` | `.true.` | Enable CVMix convection |
| `config_use_cvmix_kpp` | `.true.` | Enable KPP boundary layer |
| `config_use_cvmix_shear` | `.true.` | Enable shear mixing |

### Surface bulk forcing / coupling flags

| Parameter | Value | Meaning |
|---|---|---|
| `config_use_bulk_wind_stress` | `.true.` | Compute wind stress via bulk formulas |
| `config_bulk_wind_stress_interp_isotropic` | `.true.` | Isotropic interp of bulk wind stress |
| `config_use_bulk_thickness_flux` | `.true.` | Apply bulk thickness (freshwater) flux |
| `config_use_sgr_opt_kpp` | `.true.` | Subglacial runoff option with KPP |
| `config_precip_scaling_constant_factor` | `1.0` | Precipitation scaling factor |

These flags connect DATM atmospheric state (`u`, `v`, `t`, `slp`, `prc`, …) to
ocean surface fluxes. With bulk wind stress and thickness flux on, DATM state
(not history coupler fluxes) is the correct atmospheric input for training.

### Advection / remapping numerics

| Parameter | Value | Meaning |
|---|---|---|
| `config_horiz_tracer_adv_order` | `3` | Horizontal tracer advection order |
| `config_flux_limiter` | `'monotonic'` | Horizontal flux limiter |
| `config_remap_limiter` | `'monotonic'` | Vertical remap limiter |
| `config_vert_advection_method` | `'flux-form'` | Vertical advection formulation |

### Bottom drag

| Parameter | Value | Meaning |
|---|---|---|
| `config_bottom_drag_mode` | `'implicit'` | Bottom drag time treatment |
| `config_implicit_bottom_drag_type` | `'constant'` | Implicit drag formulation |
| `config_implicit_constant_bottom_drag_coeff` | `1.0e-3` | Quadratic drag coefficient |

### Equation of state / pressure gradient

| Parameter | Value | Meaning |
|---|---|---|
| `config_eos_type` | `'jm'` | Equation of state (Jackett–McDougall) |
| `config_pressure_gradient_type` | `'Jacobian_from_TS'` | Pressure-gradient method |

### Salinity restoring

| Parameter | Value | Meaning |
|---|---|---|
| `config_salinity_restoring_constant_piston_velocity` | `1.585e-6` | Restoring piston velocity (m/s) |
| `config_salinity_restoring_max_difference` | `0.5` | Max |ΔS| for restoring (PSU) |
| `config_salinity_restoring_under_sea_ice` | `.false.` | No restoring under sea ice |

---

## Suggested encoding for AI training

| Type | Examples | Encoding hint |
|---|---|---|
| Continuous scalars | `config_mom_del2`, `config_gm_constant_kappa`, `config_redi_constant_kappa`, drag / restoring coeffs | Float features; log-scale for large coeffs (`mom_del4`) |
| Booleans | `config_use_*`, `config_submesoscale_enable` | 0/1 flags |
| Categorical strings | `config_redi_closure`, `config_gm_closure`, `config_eos_type`, limiters | One-hot or integer codes |

If all training samples share one `mpaso_in`, these can be stored once as
**run metadata**. If the dataset spans multiple physics settings, include them
as **per-sample conditioning inputs**.

---

## Related documents

- Atmospheric forcing variables: [`DATM_FORCING_VARIABLES.md`](DATM_FORCING_VARIABLES.md)
- Selection file: `../OceanSpin_sample/mpaso_variables`
- Full namelist: `../OceanSpin_sample/mpaso_in`
