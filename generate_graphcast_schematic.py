#!/usr/bin/env python3
"""Regenerate graphcast_gnn_mesh_schematic.png for MPAS_Ocean_ML_Init_Deck slide 2."""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Polygon

BLUE = "#1a73e8"
BLUE_LIGHT = "#e8f4fd"
MESH = "#fce8e6"
MESH_EDGE = "#c5221f"
GRAY = "#5f6368"
FONT = "DejaVu Sans"
OUT = Path(__file__).resolve().parent / "graphcast_gnn_mesh_schematic.png"


def main() -> None:
    fig, ax = plt.subplots(figsize=(14, 3.8), dpi=200)
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 3.8)
    ax.axis("off")
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    def rnd_box(x, y, w, h, title, sub=None, fc=BLUE_LIGHT, ec=BLUE):
        p = FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.04,rounding_size=0.12",
            facecolor=fc,
            edgecolor=ec,
            linewidth=2,
        )
        ax.add_patch(p)
        ax.text(
            x + w / 2,
            y + h - 0.38,
            title,
            ha="center",
            va="top",
            fontsize=11,
            fontweight="bold",
            color="#174ea6",
            family=FONT,
        )
        if sub:
            ax.text(
                x + w / 2,
                y + 0.28,
                sub,
                ha="center",
                va="bottom",
                fontsize=9,
                color=GRAY,
                family=FONT,
            )

    def arrow(x1, y1, x2, y2, color=BLUE):
        arr = FancyArrowPatch(
            (x1, y1),
            (x2, y2),
            arrowstyle="-|>",
            mutation_scale=18,
            color=color,
            linewidth=2,
            shrinkA=3,
            shrinkB=3,
        )
        ax.add_patch(arr)

    rnd_box(
        0.35,
        1.0,
        2.2,
        1.85,
        "Regular lat–lon grid",
        "stacked inputs:\nsurface + levels + time",
        BLUE_LIGHT,
        BLUE,
    )
    rnd_box(
        5.35,
        0.85,
        3.3,
        2.15,
        "Unstructured mesh",
        "icosahedral △ hierarchy\nmerge_meshes · vertices",
        MESH,
        MESH_EDGE,
    )
    rnd_box(
        11.45,
        1.0,
        2.2,
        1.85,
        "Regular lat–lon grid",
        "outputs · training loss\nrollouts",
        BLUE_LIGHT,
        BLUE,
    )

    for gx, gy in [(4.15, 1.95), (4.35, 1.45), (4.2, 2.45)]:
        ax.add_patch(Circle((gx, gy), 0.06, facecolor=BLUE, edgecolor="white", zorder=5))
    ax.text(
        4.25,
        2.85,
        "radius query\ngrid2mesh",
        ha="center",
        fontsize=8,
        color=BLUE,
        style="italic",
    )

    tri_cx, tri_cy = 6.9, 1.55
    for ang in [0, 120, 240]:
        pts = []
        for da in [0, 120, 240]:
            r = np.radians(ang + da)
            pts.append([tri_cx + 0.35 * np.cos(r), tri_cy + 0.35 * np.sin(r)])
        ax.add_patch(
            Polygon(pts, closed=True, facecolor="#fff8f7", edgecolor=MESH_EDGE, linewidth=1)
        )
    ax.text(
        6.9,
        0.98,
        "mesh GNN\nmessage passing",
        ha="center",
        fontsize=8,
        color=MESH_EDGE,
        fontweight="bold",
    )

    arrow(2.6, 1.9, 5.32, 1.9)
    ax.text(3.85, 2.38, "grid2mesh\nGNN", ha="center", fontsize=9, fontweight="bold", color=BLUE)

    arrow(8.68, 1.9, 11.42, 1.9)
    ax.text(10.05, 2.38, "mesh2grid\nGNN", ha="center", fontsize=9, fontweight="bold", color=BLUE)

    for gx, gy in [(10.05, 1.95), (10.25, 1.45), (10.1, 2.45)]:
        ax.add_patch(Circle((gx, gy), 0.06, facecolor=BLUE, edgecolor="white", zorder=5))
    ax.text(
        10.15,
        2.85,
        "3 verts / triangle\nin_mesh_triangle",
        ha="center",
        fontsize=7.5,
        color=BLUE,
    )

    ax.text(
        7,
        3.45,
        "GraphCast: grid ↔ mesh via three DeepTypedGraphNet stages (TypedGraph)",
        ha="center",
        fontsize=12,
        fontweight="bold",
        color="#202124",
        family=FONT,
    )
    ax.text(
        7,
        3.12,
        "Loss and autoregressive rollouts are evaluated on the regular grid, not on an unstructured output mesh.",
        ha="center",
        fontsize=9,
        color=GRAY,
        family=FONT,
    )

    plt.tight_layout()
    fig.savefig(str(OUT), bbox_inches="tight", facecolor="white", pad_inches=0.08)
    plt.close()
    print("Wrote", OUT)


if __name__ == "__main__":
    main()
