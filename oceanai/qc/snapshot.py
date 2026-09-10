"""Snapshot an ML restart vs early (X) and late (Y) ground-truth restarts.

Compares the v1 writeback contract and deep T/S/OHC. Writes a markdown report
plus JSON (and optional SVG maps) under ``prototype/snapshots/``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from oceanai.baselines.persistence import pair_metrics
from oceanai.data.extract import _read_xtime, read_deep_state
from oceanai.mesh.deep_mask import load_deep_mask
from oceanai.paths import (
    FILL,
    REPO_ROOT,
    early_rst,
    late_rst,
    processed_dirs,
)
from oceanai.qc.ohc import ohc_from_state


def _finite(a: np.ndarray) -> np.ndarray:
    a = np.asarray(a, dtype=np.float64)
    return np.isfinite(a) & (np.abs(a) < FILL / 10)


def _weighted_stats(vals: np.ndarray, valid: np.ndarray, w: np.ndarray) -> dict:
    m = valid & np.isfinite(vals)
    ww = np.where(m, w, 0.0)
    wsum = float(ww.sum())
    v = np.where(m, vals, 0.0)
    if wsum <= 0:
        return {"mean": None, "min": None, "max": None, "n": 0}
    return {
        "mean": float((ww * v).sum() / wsum),
        "min": float(vals[m].min()),
        "max": float(vals[m].max()),
        "n": int(m.sum()),
    }


def _max_abs_diff(a: np.ndarray, b: np.ndarray) -> float:
    m = _finite(a) & _finite(b)
    if not np.any(m):
        return float("nan")
    return float(np.max(np.abs(a[m] - b[m])))


def _read_restart_arrays(path: Path, names: list[str]) -> dict:
    from netCDF4 import Dataset

    out = {}
    with Dataset(path, "r") as ds:
        out["xtime"] = _read_xtime(ds)
        out["dims"] = {k: int(len(ds.dimensions[k])) for k in ("nCells", "nEdges", "nVertLevels") if k in ds.dimensions}
        for name in names:
            if name not in ds.variables:
                continue
            v = np.asarray(ds.variables[name][:])
            if v.ndim >= 2 and v.shape[0] == 1:
                v = v[0]
            out[name] = v
    return out


def _pick_example_cells(mask: dict) -> list[dict]:
    """A few columns: deepest, near equator, southernmost deep cell."""
    deep_col = mask["mask"].any(axis=1)
    lat = mask["latCell"]
    lon = mask["lonCell"]
    bot = mask["bottomDepth"]
    idx = np.where(deep_col)[0]
    picks = {
        "deepest": int(idx[np.argmax(bot[idx])]),
        "near_equator": int(idx[np.argmin(np.abs(lat[idx]))]),
        "southernmost": int(idx[np.argmin(lat[idx])]),
    }
    rows = []
    for label, i in picks.items():
        rows.append(
            {
                "label": label,
                "cell": i,
                "lat_deg": float(np.degrees(lat[i])),
                "lon_deg": float(np.degrees(lon[i]) % 360),
                "bottomDepth_m": float(bot[i]),
            }
        )
    return rows


def _level_means(t: np.ndarray, valid: np.ndarray, w: np.ndarray, ref: np.ndarray) -> list[dict]:
    rows = []
    for j in range(t.shape[1]):
        st = _weighted_stats(t[:, j], valid[:, j], w[:, j])
        st["k_1based"] = int(46 + j)
        st["refBottomDepth_m"] = float(ref[j])
        rows.append(st)
    return rows


def _svg_map(lon_deg, lat_deg, values, valid_col, path: Path, title: str, vmin, vmax, unit: str = "°C") -> None:
    """Longitude–latitude scatter of column-mean deep T. No matplotlib required."""
    n = lon_deg.size
    w, h = 900, 460
    pad = 40

    def xy(lo, la):
        x = pad + (np.mod(lo, 360.0) / 360.0) * (w - 2 * pad)
        y = pad + ((90.0 - la) / 180.0) * (h - 2 * pad)
        return x, y

    def color(v):
        if not np.isfinite(v):
            return "#cccccc"
        t = (v - vmin) / max(vmax - vmin, 1e-12)
        t = float(np.clip(t, 0.0, 1.0))
        # blue → white → red
        if t < 0.5:
            u = t * 2
            r, g, b = int(255 * u), int(255 * u), 255
        else:
            u = (t - 0.5) * 2
            r, g, b = 255, int(255 * (1 - u)), int(255 * (1 - u))
        return f"#{r:02x}{g:02x}{b:02x}"

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">',
        '<rect width="100%" height="100%" fill="#111827"/>',
        f'<text x="{w/2}" y="22" fill="#e5e7eb" text-anchor="middle" font-size="16" font-family="sans-serif">{title}</text>',
        f'<text x="{pad}" y="{h-12}" fill="#9ca3af" font-size="11" font-family="sans-serif">lon 0–360</text>',
        f'<text x="{w-pad}" y="{h-12}" fill="#9ca3af" font-size="11" font-family="sans-serif" text-anchor="end">{vmin:.2f} … {vmax:.2f} {unit}</text>',
    ]
    order = np.argsort(lat_deg)
    for i in order:
        if not valid_col[i]:
            continue
        x, y = xy(lon_deg[i], lat_deg[i])
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="1.6" fill="{color(values[i])}"/>')
    parts.append("</svg>")
    path.write_text("\n".join(parts))


def compare_restarts(
    path_x: Path,
    path_y: Path,
    path_ml: Path,
    mask: dict | None = None,
) -> dict:
    mask = mask or load_deep_mask()
    sl = mask["level_slice"]
    names = [
        "temperature",
        "salinity",
        "layerThickness",
        "normalVelocity",
        "normalBarotropicVelocity",
        "bottomDepth",
        "refBottomDepth",
    ]
    x = _read_restart_arrays(path_x, names)
    y = _read_restart_arrays(path_y, names)
    ml = _read_restart_arrays(path_ml, names)

    sx = read_deep_state(path_x, mask)
    sy = read_deep_state(path_y, mask)
    sm = read_deep_state(path_ml, mask)
    valid = sx["valid"] & sy["valid"] & sm["valid"]
    area = mask["areaCell"]
    w = area[:, None] * sx["layerThickness"]

    metrics_ml = pair_metrics(
        {
            "t_y": sy["temperature"],
            "s_y": sy["salinity"],
            "h_y": sy["layerThickness"],
            "h_x": sx["layerThickness"],
            "valid": valid,
        },
        sm["temperature"],
        sm["salinity"],
        area,
        h_hat=sx["layerThickness"],
    )
    metrics_persist = pair_metrics(
        {
            "t_y": sy["temperature"],
            "s_y": sy["salinity"],
            "h_y": sy["layerThickness"],
            "h_x": sx["layerThickness"],
            "valid": valid,
        },
        sx["temperature"],
        sx["salinity"],
        area,
        h_hat=sx["layerThickness"],
    )
    ohc_x = ohc_from_state(sx["temperature"], sx["layerThickness"], valid, area)
    ohc_y = ohc_from_state(sy["temperature"], sy["layerThickness"], valid, area)
    ohc_ml = ohc_from_state(sm["temperature"], sm["layerThickness"], valid, area)

    t_x, t_y, t_ml = x["temperature"], y["temperature"], ml["temperature"]
    shallow = slice(0, sl.start)
    contract = {
        "shallow_T_maxabs_ML_minus_X": _max_abs_diff(t_ml[:, shallow], t_x[:, shallow]),
        "shallow_S_maxabs_ML_minus_X": _max_abs_diff(ml["salinity"][:, shallow], x["salinity"][:, shallow]),
        "layerThickness_maxabs_ML_minus_X": _max_abs_diff(ml["layerThickness"], x["layerThickness"]),
        "layerThickness_maxabs_Y_minus_X": _max_abs_diff(y["layerThickness"], x["layerThickness"]),
    }
    if "normalVelocity" in ml and "normalVelocity" in x:
        contract["normalVelocity_maxabs_ML_minus_X"] = _max_abs_diff(ml["normalVelocity"], x["normalVelocity"])
    if "normalBarotropicVelocity" in ml and "normalBarotropicVelocity" in x:
        contract["normalBarotropicVelocity_maxabs_ML_minus_X"] = _max_abs_diff(
            ml["normalBarotropicVelocity"], x["normalBarotropicVelocity"]
        )

    examples = _pick_example_cells(mask)
    for ex in examples:
        i = ex["cell"]
        ex["T_profile_C"] = {
            "k_1based": list(range(46, 61)),
            "X": [float(sx["temperature"][i, j]) for j in range(15)],
            "ML": [float(sm["temperature"][i, j]) for j in range(15)],
            "Y": [float(sy["temperature"][i, j]) for j in range(15)],
            "valid": [bool(valid[i, j]) for j in range(15)],
        }
        ex["S_profile"] = {
            "X": [float(sx["salinity"][i, j]) for j in range(15)],
            "ML": [float(sm["salinity"][i, j]) for j in range(15)],
            "Y": [float(sy["salinity"][i, j]) for j in range(15)],
        }

    col_ok = valid.any(axis=1)
    tcol = lambda t: np.where(col_ok, np.where(valid, t, np.nan).mean(axis=1), np.nan)

    pack = {
        "files": {
            "X_early": str(path_x),
            "ML": str(path_ml),
            "Y_truth": str(path_y),
        },
        "xtime": {"X": x["xtime"], "ML": ml["xtime"], "Y": y["xtime"]},
        "dims": ml["dims"],
        "contract_ML_is_copy_of_X_except_deep_TS": contract,
        "deep_T_C": {
            "X": _weighted_stats(sx["temperature"], valid, w),
            "ML": _weighted_stats(sm["temperature"], valid, w),
            "Y": _weighted_stats(sy["temperature"], valid, w),
        },
        "deep_S": {
            "X": _weighted_stats(sx["salinity"], valid, w),
            "ML": _weighted_stats(sm["salinity"], valid, w),
            "Y": _weighted_stats(sy["salinity"], valid, w),
        },
        "deep_T_mean_by_level": {
            "X": _level_means(sx["temperature"], valid, w, mask["ref_deep"]),
            "ML": _level_means(sm["temperature"], valid, w, mask["ref_deep"]),
            "Y": _level_means(sy["temperature"], valid, w, mask["ref_deep"]),
        },
        "vs_Y": {"ML": metrics_ml, "persistence_X": metrics_persist},
        "OHC_2000m_to_bottom_J": {
            "X": ohc_x["global"],
            "ML": ohc_ml["global"],
            "Y": ohc_y["global"],
            "ML_minus_Y": ohc_ml["global"] - ohc_y["global"],
            "X_minus_Y": ohc_x["global"] - ohc_y["global"],
            "ML_rel_err_vs_Y": abs(ohc_ml["global"] - ohc_y["global"]) / abs(ohc_y["global"]),
            "X_rel_err_vs_Y": abs(ohc_x["global"] - ohc_y["global"]) / abs(ohc_y["global"]),
        },
        "example_columns": examples,
        "_maps": {
            "lon_deg": np.degrees(mask["lonCell"]) % 360,
            "lat_deg": np.degrees(mask["latCell"]),
            "valid_col": col_ok,
            "T_col_X": tcol(sx["temperature"]),
            "T_col_ML": tcol(sm["temperature"]),
            "T_col_Y": tcol(sy["temperature"]),
            "S_col_X": tcol(sx["salinity"]),
            "S_col_ML": tcol(sm["salinity"]),
            "S_col_Y": tcol(sy["salinity"]),
        },
    }
    return pack


def _fmt(v, digits=4):
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return "—"
    if abs(v) >= 1e4 or (abs(v) < 1e-3 and v != 0):
        return f"{v:.4e}"
    return f"{v:.{digits}f}"


def write_markdown(pack: dict, out: Path) -> None:
    c = pack["contract_ML_is_copy_of_X_except_deep_TS"]
    t = pack["deep_T_C"]
    s = pack["deep_S"]
    ohc = pack["OHC_2000m_to_bottom_J"]
    mlm = pack["vs_Y"]["ML"]
    pers = pack["vs_Y"]["persistence_X"]
    lines = [
        "# Restart snapshot: early X vs AI vs late Y",
        "",
        "Holdout pair **0055-01 → 0605-01**. Deep T/S only (k=46…60).",
        "",
        "| Role | File | `xtime` |",
        "|---|---|---|",
        f"| **X** early (initial) | `{Path(pack['files']['X_early']).name}` | `{pack['xtime']['X']}` |",
        f"| **ML** AI writeback | `{Path(pack['files']['ML']).name}` | `{pack['xtime']['ML']}` |",
        f"| **Y** late (ground truth) | `{Path(pack['files']['Y_truth']).name}` | `{pack['xtime']['Y']}` |",
        "",
        "## Contract (ML should match X except deep T/S)",
        "",
        "| Check | max \\|ML − X\\| | Expect |",
        "|---|---|---|",
        f"| Shallow T (k=1…45) | {_fmt(c['shallow_T_maxabs_ML_minus_X'], 6)} °C | ~0 |",
        f"| Shallow S | {_fmt(c['shallow_S_maxabs_ML_minus_X'], 6)} | ~0 |",
        f"| `layerThickness` | {_fmt(c['layerThickness_maxabs_ML_minus_X'], 6)} m | ~0 (copy X) |",
        f"| `normalVelocity` | {_fmt(c.get('normalVelocity_maxabs_ML_minus_X'), 6)} m/s | ~0 |",
        f"| `normalBarotropicVelocity` | {_fmt(c.get('normalBarotropicVelocity_maxabs_ML_minus_X'), 6)} m/s | ~0 |",
        "",
        f"Y vs X thickness (not overwritten; for context): max \\|Y−X\\| h = {_fmt(c['layerThickness_maxabs_Y_minus_X'], 4)} m.",
        "",
        "## Deep temperature (°C), area×thickness weighted",
        "",
        "| | mean | min | max | RMSE vs Y | bias (this − Y) |",
        "|---|---|---|---|---|---|",
        f"| X (persistence) | {_fmt(t['X']['mean'])} | {_fmt(t['X']['min'])} | {_fmt(t['X']['max'])} | {_fmt(pers['rmse_t'])} | {_fmt(-pers['bias_t'])} |",
        f"| **ML** | {_fmt(t['ML']['mean'])} | {_fmt(t['ML']['min'])} | {_fmt(t['ML']['max'])} | **{_fmt(mlm['rmse_t'])}** | {_fmt(-mlm['bias_t'])} |",
        f"| Y (truth) | {_fmt(t['Y']['mean'])} | {_fmt(t['Y']['min'])} | {_fmt(t['Y']['max'])} | 0 | 0 |",
        "",
        "## Deep salinity",
        "",
        "| | mean | min | max | RMSE vs Y | bias (this − Y) |",
        "|---|---|---|---|---|---|",
        f"| X | {_fmt(s['X']['mean'])} | {_fmt(s['X']['min'])} | {_fmt(s['X']['max'])} | {_fmt(pers['rmse_s'])} | {_fmt(-pers['bias_s'])} |",
        f"| **ML** | {_fmt(s['ML']['mean'])} | {_fmt(s['ML']['min'])} | {_fmt(s['ML']['max'])} | {_fmt(mlm['rmse_s'])} | {_fmt(-mlm['bias_s'])} |",
        f"| Y | {_fmt(s['Y']['mean'])} | {_fmt(s['Y']['min'])} | {_fmt(s['Y']['max'])} | 0 | 0 |",
        "",
        "## OHC 2000 m–bottom (J)",
        "",
        "Uses T in Kelvin, ρ₀=1026, cₚ=3996, X layer thickness.",
        "",
        "| | OHC (J) | rel. err. vs Y |",
        "|---|---|---|",
        f"| X | {_fmt(ohc['X'], 6)} | {_fmt(ohc['X_rel_err_vs_Y'], 5)} |",
        f"| **ML** | {_fmt(ohc['ML'], 6)} | **{_fmt(ohc['ML_rel_err_vs_Y'], 5)}** |",
        f"| Y | {_fmt(ohc['Y'], 6)} | 0 |",
        "",
        "## Mean deep T by level (°C)",
        "",
        "| k | z_ref (m) | X | ML | Y | ML−Y | X−Y |",
        "|---|---|---|---|---|---|---|",
    ]
    xs, ms, ys = (
        pack["deep_T_mean_by_level"]["X"],
        pack["deep_T_mean_by_level"]["ML"],
        pack["deep_T_mean_by_level"]["Y"],
    )
    for a, b, clev in zip(xs, ms, ys):
        lines.append(
            f"| {a['k_1based']} | {a['refBottomDepth_m']:.0f} | {_fmt(a['mean'])} | {_fmt(b['mean'])} | {_fmt(clev['mean'])} | "
            f"{_fmt((b['mean'] or 0) - (clev['mean'] or 0))} | {_fmt((a['mean'] or 0) - (clev['mean'] or 0))} |"
        )
    lines += ["", "## Example columns (deep T °C)", ""]
    for ex in pack["example_columns"]:
        lines += [
            f"### {ex['label']} — cell {ex['cell']}  lat {ex['lat_deg']:.2f}°  lon {ex['lon_deg']:.1f}°  "
            f"bottom {ex['bottomDepth_m']:.0f} m",
            "",
            "| k | X | ML | Y | ML−Y |",
            "|---|---|---|---|---|",
        ]
        for j, k in enumerate(ex["T_profile_C"]["k_1based"]):
            if not ex["T_profile_C"]["valid"][j]:
                continue
            tx, tm, ty = ex["T_profile_C"]["X"][j], ex["T_profile_C"]["ML"][j], ex["T_profile_C"]["Y"][j]
            lines.append(f"| {k} | {_fmt(tx)} | {_fmt(tm)} | {_fmt(ty)} | {_fmt(tm - ty)} |")
        lines.append("")
    lines += [
        "## Maps",
        "",
        "Column-mean deep T: `map_T_X.svg`, `map_T_ML.svg`, `map_T_Y.svg`, `map_T_ML_minus_Y.svg`.",
        "",
        "Column-mean deep S: `map_S_X.svg`, `map_S_ML.svg`, `map_S_Y.svg`, `map_S_ML_minus_Y.svg`.",
        "",
        "Regenerate: `python -m oceanai.qc.snapshot`.",
        "",
    ]
    out.write_text("\n".join(lines))


def snapshot_holdout_jan(
    ml_path: Path | None = None,
    out_dir: Path | None = None,
) -> Path:
    dirs = processed_dirs()
    path_x = early_rst(55, 1)
    path_y = late_rst(605, 1)
    path_ml = Path(ml_path) if ml_path else dirs["restarts_ml"] / "rst.0055-01-01.ml.nc"
    if not path_ml.exists():
        raise FileNotFoundError(f"ML restart not found: {path_ml}")
    dest = Path(out_dir) if out_dir else REPO_ROOT / "prototype" / "snapshots" / "0055-01"
    dest.mkdir(parents=True, exist_ok=True)

    pack = compare_restarts(path_x, path_y, path_ml)
    maps = pack.pop("_maps")
    json_path = dest / "compare.json"
    json_path.write_text(json.dumps(pack, indent=2))
    write_markdown(pack, dest / "compare.md")

    lon, lat, ok = maps["lon_deg"], maps["lat_deg"], maps["valid_col"]
    tmin = float(np.nanmin([maps["T_col_X"], maps["T_col_ML"], maps["T_col_Y"]]))
    tmax = float(np.nanmax([maps["T_col_X"], maps["T_col_ML"], maps["T_col_Y"]]))
    _svg_map(lon, lat, maps["T_col_X"], ok, dest / "map_T_X.svg", "Deep-column mean T — X (year 55)", tmin, tmax)
    _svg_map(lon, lat, maps["T_col_ML"], ok, dest / "map_T_ML.svg", "Deep-column mean T — ML restart", tmin, tmax)
    _svg_map(lon, lat, maps["T_col_Y"], ok, dest / "map_T_Y.svg", "Deep-column mean T — Y (year 605 truth)", tmin, tmax)
    dty = maps["T_col_ML"] - maps["T_col_Y"]
    amax = float(np.nanmax(np.abs(dty)))
    _svg_map(lon, lat, dty, ok, dest / "map_T_ML_minus_Y.svg", "Deep-column mean T — ML minus Y", -amax, amax)

    smin = float(np.nanmin([maps["S_col_X"], maps["S_col_ML"], maps["S_col_Y"]]))
    smax = float(np.nanmax([maps["S_col_X"], maps["S_col_ML"], maps["S_col_Y"]]))
    _svg_map(lon, lat, maps["S_col_X"], ok, dest / "map_S_X.svg", "Deep-column mean S — X (year 55)", smin, smax, unit="PSU")
    _svg_map(lon, lat, maps["S_col_ML"], ok, dest / "map_S_ML.svg", "Deep-column mean S — ML restart", smin, smax, unit="PSU")
    _svg_map(lon, lat, maps["S_col_Y"], ok, dest / "map_S_Y.svg", "Deep-column mean S — Y (year 605 truth)", smin, smax, unit="PSU")
    dsy = maps["S_col_ML"] - maps["S_col_Y"]
    sabs = float(np.nanmax(np.abs(dsy)))
    _svg_map(lon, lat, dsy, ok, dest / "map_S_ML_minus_Y.svg", "Deep-column mean S — ML minus Y", -sabs, sabs, unit="PSU")
    print(f"snapshot → {dest / 'compare.md'}")
    print(
        f"deep T RMSE vs Y:  ML={pack['vs_Y']['ML']['rmse_t']:.4f} C   "
        f"persistence={pack['vs_Y']['persistence_X']['rmse_t']:.4f} C"
    )
    print(
        f"deep S RMSE vs Y:  ML={pack['vs_Y']['ML']['rmse_s']:.4f}   "
        f"persistence={pack['vs_Y']['persistence_X']['rmse_s']:.4f}"
    )
    return dest


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Snapshot ML restart vs early X and late Y")
    p.add_argument("--ml", type=Path, default=None, help="ML restart path (default: processed restarts_ml/rst.0055-01-01.ml.nc)")
    p.add_argument("--out", type=Path, default=None)
    args = p.parse_args(argv)
    snapshot_holdout_jan(ml_path=args.ml, out_dir=args.out)


if __name__ == "__main__":
    main()
