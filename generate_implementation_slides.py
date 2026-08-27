#!/usr/bin/env python3
"""Build OceanAISpinup_Implementation_Slides.pptx for the team meeting."""
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import nsmap, qn
from pptx.util import Emu, Inches, Pt
from lxml import etree

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "OceanAISpinup_Implementation_Slides.pptx"
OHC_FIG = ROOT / "Ocean_EQ.png"

NAVY = RGBColor(0x1B, 0x36, 0x5D)
NAVY2 = RGBColor(0x24, 0x4A, 0x7A)
TEAL = RGBColor(0x0E, 0x7C, 0x7B)
TEAL_LT = RGBColor(0xE4, 0xF2, 0xF1)
GOLD = RGBColor(0xC0, 0x56, 0x21)
GOLD_LT = RGBColor(0xFD, 0xF0, 0xE6)
GREEN = RGBColor(0x2E, 0x7D, 0x32)
GREEN_LT = RGBColor(0xE8, 0xF5, 0xE9)
RED = RGBColor(0xB3, 0x26, 0x1E)
INK = RGBColor(0x1A, 0x1A, 0x1A)
MUTED = RGBColor(0x5A, 0x65, 0x70)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
BG = RGBColor(0xF6, 0xF7, 0xF9)
CARD = RGBColor(0xFF, 0xFF, 0xFF)
LINE = RGBColor(0xD5, 0xDC, 0xE3)
ROW_ALT = RGBColor(0xF3, 0xF6, 0xFA)

W = Inches(13.333)
H = Inches(7.5)


def _set_run(run, size, bold, color, font="Calibri"):
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    run.font.name = font


def _fill(shape, color):
    shape.fill.solid()
    shape.fill.fore_color.rgb = color
    shape.line.fill.background()


def _fill_line(shape, fill, line, width_pt=1.0):
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    shape.line.color.rgb = line
    shape.line.width = Pt(width_pt)


def rect(slide, l, t, w, h, fill, line=None, width_pt=1.0):
    s = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, l, t, w, h)
    if line is None:
        _fill(s, fill)
    else:
        _fill_line(s, fill, line, width_pt)
    s.shadow.inherit = False
    return s


def round_rect(slide, l, t, w, h, fill, line=None, width_pt=1.0):
    s = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, l, t, w, h)
    if line is None:
        _fill(s, fill)
    else:
        _fill_line(s, fill, line, width_pt)
    s.adjustments[0] = 0.08
    s.shadow.inherit = False
    return s


def txt(slide, l, t, w, h, text, size=18, bold=False, color=INK, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP):
    box = slide.shapes.add_textbox(l, t, w, h)
    tf = box.text_frame
    tf.word_wrap = True
    tf.auto_size = None
    try:
        tf._txBody.bodyPr.set("anchor", {MSO_ANCHOR.TOP: "t", MSO_ANCHOR.MIDDLE: "ctr", MSO_ANCHOR.BOTTOM: "b"}[anchor])
    except Exception:
        pass
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    _set_run(run, size, bold, color)
    return box


def bullets(slide, l, t, w, h, items, size=16, color=INK, spacing=8):
    box = slide.shapes.add_textbox(l, t, w, h)
    tf = box.text_frame
    tf.word_wrap = True
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.LEFT
        p.space_after = Pt(spacing)
        p.level = 0
        run = p.add_run()
        run.text = "•  " + item
        _set_run(run, size, False, color)
    return box


def notes(slide, text):
    slide.notes_slide.notes_text_frame.text = text


def set_run_font(cell, size=12, bold=False, color=INK):
    for p in cell.text_frame.paragraphs:
        p.space_before = Pt(2)
        p.space_after = Pt(2)
        for run in p.runs:
            _set_run(run, size, bold, color)


def shade_cell(cell, color):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    solid = etree.SubElement(tcPr, qn("a:solidFill"))
    srgb = etree.SubElement(solid, qn("a:srgbClr"))
    srgb.set("val", f"{color[0]:02X}{color[1]:02X}{color[2]:02X}")


def table(slide, l, t, w, h, rows, col_w=None, header=True, font=13):
    n_r, n_c = len(rows), len(rows[0])
    shp = slide.shapes.add_table(n_r, n_c, l, t, w, h)
    tbl = shp.table
    if col_w:
        for i, cw in enumerate(col_w):
            tbl.columns[i].width = cw
    for r, row in enumerate(rows):
        for c, val in enumerate(row):
            cell = tbl.cell(r, c)
            cell.text = val
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            is_hdr = header and r == 0
            set_run_font(cell, size=font if not is_hdr else font, bold=is_hdr, color=WHITE if is_hdr else INK)
            if is_hdr:
                shade_cell(cell, (0x1B, 0x36, 0x5D))
            elif r % 2 == 0:
                shade_cell(cell, (0xF3, 0xF6, 0xFA))
            else:
                shade_cell(cell, (0xFF, 0xFF, 0xFF))
    return shp


def chrome(slide, title, k, n, subtitle=None):
    rect(slide, 0, 0, W, H, BG)
    rect(slide, 0, 0, W, Inches(0.92), NAVY)
    rect(slide, 0, Inches(0.92), W, Inches(0.06), TEAL)
    txt(slide, Inches(0.45), Inches(0.18), Inches(11.5), Inches(0.42), title, 24, True, WHITE)
    if subtitle:
        txt(slide, Inches(0.45), Inches(0.52), Inches(11.5), Inches(0.32), subtitle, 13, False, RGBColor(0xC5, 0xD4, 0xE8))
    rect(slide, 0, Inches(7.18), W, Inches(0.32), NAVY)
    txt(
        slide,
        Inches(0.45),
        Inches(7.20),
        Inches(10.2),
        Inches(0.26),
        "OceanAISpinup  ·  Implementation plan  ·  AI4MPAS / ImPACTS",
        11,
        False,
        RGBColor(0xC5, 0xD4, 0xE8),
        anchor=MSO_ANCHOR.MIDDLE,
    )
    txt(
        slide,
        Inches(11.4),
        Inches(7.20),
        Inches(1.5),
        Inches(0.26),
        f"{k}  /  {n}",
        11,
        False,
        RGBColor(0xC5, 0xD4, 0xE8),
        align=PP_ALIGN.RIGHT,
        anchor=MSO_ANCHOR.MIDDLE,
    )


def card(slide, l, t, w, h, title, body_lines, accent=TEAL, title_size=14, body_size=13):
    round_rect(slide, l, t, w, h, CARD, LINE, 1.0)
    rect(slide, l, t, Inches(0.08), h, accent)
    txt(slide, l + Inches(0.22), t + Inches(0.10), w - Inches(0.35), Inches(0.32), title, title_size, True, accent)
    bullets(slide, l + Inches(0.18), t + Inches(0.42), w - Inches(0.32), h - Inches(0.52), body_lines, body_size, INK, 4)


def new_prs():
    prs = Presentation()
    prs.slide_width = W
    prs.slide_height = H
    return prs


def blank(prs):
    return prs.slides.add_slide(prs.slide_layouts[6])


def add_title(prs, n):
    s = blank(prs)
    rect(s, 0, 0, W, H, NAVY)
    rect(s, 0, 0, Inches(0.18), H, TEAL)
    txt(s, Inches(0.7), Inches(1.55), Inches(12), Inches(0.4), "AI4MPAS  /  ImPACTS", 16, False, RGBColor(0x8F, 0xC9, 0xC8))
    txt(s, Inches(0.7), Inches(2.05), Inches(12), Inches(1.1), "OceanAISpinup implementation plan", 36, True, WHITE)
    txt(
        s,
        Inches(0.7),
        Inches(3.20),
        Inches(12),
        Inches(0.7),
        "Native MPAS mesh GNN  ·  LandSim pairing  ·  QU240 prototype",
        20,
        False,
        RGBColor(0xC5, 0xD4, 0xE8),
    )
    # three chips
    chips = [
        (Inches(0.7), "Schema locked", "GMPAS-NYF_QU240 headers"),
        (Inches(4.85), "Not training-ready", "Need the long restart archive"),
        (Inches(9.0), "MVP path", "Track A residual GNN on deep T/S"),
    ]
    for x, a, b in chips:
        round_rect(s, x, Inches(4.35), Inches(3.7), Inches(1.15), NAVY2)
        txt(s, x + Inches(0.2), Inches(4.48), Inches(3.3), Inches(0.4), a, 16, True, WHITE)
        txt(s, x + Inches(0.2), Inches(4.90), Inches(3.3), Inches(0.4), b, 13, False, RGBColor(0xC5, 0xD4, 0xE8))
    txt(s, Inches(0.7), Inches(6.85), Inches(12), Inches(0.3), "27 August 2026   ·   Dali, Alice, Hyun, Olawale", 14, False, RGBColor(0x8F, 0xC9, 0xC8))
    notes(
        s,
        "Open with status, not architecture. Schema is locked from Kang’s QU240 sample. "
        "We can design and start a graph builder. We cannot train until we have many restart years.",
    )
    return s


def add_agenda(prs, k, n):
    s = blank(prs)
    chrome(s, "What this meeting needs to decide", k, n, "Three questions from the implementation plan")
    items = [
        ("01", "Is Kang’s sample enough?", "Yes for architecture and IO. No for training volume, forcing sensitivity, or diffusion."),
        ("02", "How should the model work?", "Conditional residual map on the native MPAS C-grid. Not a weather rollout. Not a lat–lon ViT."),
        ("03", "How do we get training data?", "Treat the long spinup as a trajectory of pairs. 0661/0681 is format only."),
    ]
    y = Inches(1.25)
    for num, title, body in items:
        round_rect(s, Inches(0.5), y, Inches(12.3), Inches(1.55), CARD, LINE)
        rect(s, Inches(0.5), y, Inches(0.12), Inches(1.55), TEAL)
        txt(s, Inches(0.85), y + Inches(0.22), Inches(1.0), Inches(0.45), num, 22, True, TEAL)
        txt(s, Inches(1.9), y + Inches(0.22), Inches(10.4), Inches(0.45), title, 22, True, NAVY)
        txt(s, Inches(1.9), y + Inches(0.72), Inches(10.4), Inches(0.6), body, 16, False, MUTED)
        y += Inches(1.72)
    notes(s, "Keep the meeting on these three questions. Architecture details live on later slides.")
    return s


def add_verdict(prs, k, n):
    s = blank(prs)
    chrome(s, "Direct answer: is the sample enough?", k, n, "Enough to design. Not enough to train.")
    table(
        s,
        Inches(0.45),
        Inches(1.20),
        Inches(12.4),
        Inches(4.55),
        [
            ["Question", "Locked from sample", "Still missing"],
            ["Mesh / names", "7153 cells, 60 levels; T, S, h, un", "Restart .nc arrays on disk"],
            ["Deep target", "k = 46…60; OHC 2000 m–bottom", "OHC script vs history field"],
            ["Pairing", "Intended 50 yr → 600 yr", "Full rst year list from Hyun"],
            ["Atmosphere", "DATM CORE2 NYF (T62, cycled)", "Does not vary across pairs"],
            ["Physics θ", "mpaso_in values (GM κ=900, …)", "One case → θ not identifiable"],
            ["Training N", "Two format restarts (20 yr apart)", "Annual checkpoints ~20–600 yr"],
        ],
        col_w=[Inches(2.3), Inches(5.3), Inches(4.8)],
        font=13,
    )
    round_rect(s, Inches(0.45), Inches(5.90), Inches(12.4), Inches(1.10), TEAL_LT, TEAL)
    txt(
        s,
        Inches(0.7),
        Inches(6.05),
        Inches(12.0),
        Inches(0.80),
        "On this sample, F and θ are run-level metadata. The mesh is the spatial operator. "
        "A QU240 loader can start now; multi-run data plugs in later without changing the IO contract.",
        15,
        False,
        NAVY,
        anchor=MSO_ANCHOR.MIDDLE,
    )
    notes(
        s,
        "Stress the last row. Two restarts are not a dataset. NYF cycles, so atmosphere cannot teach "
        "parameter or forcing sensitivity until we have more cases.",
    )
    return s


def add_sample(prs, k, n):
    s = blank(prs)
    chrome(s, "Local sample: v3.GMPAS-NYF_QU240", k, n, "Headers and namelists in data/OceanSpin_sample/  ·  NetCDF gitignored")
    cards = [
        (Inches(0.45), "Ocean", ["QU240 ~240 km spherical C-grid", "nCells 7153  ·  nEdges 22403", "nVertLevels 60  ·  z-star", "dt = 1 h, noleap, split-explicit"]),
        (Inches(4.75), "Atmosphere", ["DATM CORE2_NYF, taxmode=cycle", "NCEP T62 94×192, 6-hourly", "GXGXS precip (monthly)", "GISS SW/LW (monthly)"]),
        (Inches(9.05), "Physics θ", ["GM / Redi κ = 900 (constant)", "mom_del2=4000, del4=2e14", "KPP + convection + shear", "EOS jm  ·  bulk wind + FW flux"]),
    ]
    for x, title, lines in cards:
        card(s, x, Inches(1.20), Inches(3.85), Inches(2.55), title, lines, TEAL, 16, 13)
    round_rect(s, Inches(0.45), Inches(3.95), Inches(12.4), Inches(2.95), CARD, LINE)
    txt(s, Inches(0.7), Inches(4.10), Inches(12), Inches(0.35), "Format files named in the headers (not the 50→600 scientific pair)", 16, True, NAVY)
    table(
        s,
        Inches(0.7),
        Inches(4.50),
        Inches(11.9),
        Inches(2.20),
        [
            ["File", "Time", "Role"],
            ["mpaso.rst.0661-01-01_00000.nc", "year 661", "Restart format exemplar (late run)"],
            ["mpaso.rst.0681-01-01_00000.nc", "year 681", "+20 yr residual for IO / persistence"],
            ["hist … timeSeriesStatsMonthly.0678-11-01", "Nov 678", "OHC / SSH / MLD diagnostics"],
        ],
        col_w=[Inches(6.2), Inches(1.8), Inches(3.9)],
        font=13,
    )
    notes(
        s,
        "NERSC pointer: /global/cfs/cdirs/m4259/hgkang/data_for_others/Dali_OceanSpinup_sample. "
        "Mesh connectivity lives in the restart — no separate mesh file needed for the graph builder.",
    )
    return s


def add_ohc(prs, k, n):
    s = blank(prs)
    chrome(s, "Why deep ocean (2000 m–bottom)", k, n, "Slowest spinup signal  ·  Alice / Hyun index  ·  Ocean_EQ.png")
    if OHC_FIG.exists():
        s.shapes.add_picture(str(OHC_FIG), Inches(0.40), Inches(1.15), Inches(8.15), Inches(5.75))
    round_rect(s, Inches(8.70), Inches(1.20), Inches(4.20), Inches(5.70), CARD, LINE)
    txt(s, Inches(8.90), Inches(1.35), Inches(3.85), Inches(0.40), "Takeaways for ML", 16, True, TEAL)
    bullets(
        s,
        Inches(8.90),
        Inches(1.85),
        Inches(3.85),
        Inches(4.80),
        [
            "Upper ocean equilibrates; deep OHC keeps drifting.",
            "v1 predicts only k = 46…60 (15 levels, ~2075–5500 m).",
            "Shallow levels copied from the early restart / template.",
            "History QC field: timeMonthly_avg_oceanHeatContent2000mToBot.",
            "OHC = ρ₀ cp Σ T h A   with ρ₀=1026, cp=3996.",
            "ssh is not in the restart. Write layerThickness only.",
        ],
        14,
        INK,
        8,
    )
    notes(
        s,
        "This figure is the scientific motivation. We are not trying to correct mixed-layer weather. "
        "We are trying to jump the slow deep-ocean heat-content adjustment.",
    )
    return s


def add_io(prs, k, n):
    s = blank(prs)
    chrome(s, "Locked IO  —  restart names are source of truth", k, n, "History aliases are QC only  ·  do not write ssh")
    table(
        s,
        Inches(0.45),
        Inches(1.18),
        Inches(12.4),
        Inches(3.55),
        [
            ["Role", "Restart name", "Shape", "History (QC only)"],
            ["Potential temperature", "temperature", "Time, nCells, nVertLevels", "activeTracers_temperature"],
            ["Salinity", "salinity", "Time, nCells, nVertLevels", "activeTracers_salinity"],
            ["Layer thickness", "layerThickness", "Time, nCells, nVertLevels", "layerThickness"],
            ["Edge-normal velocity", "normalVelocity", "Time, nEdges, nVertLevels", "normalVelocity  (phase 2)"],
            ["SSH", "not in restart", "—", "timeMonthly_avg_ssh"],
        ],
        col_w=[Inches(3.1), Inches(2.7), Inches(3.4), Inches(3.2)],
        font=13,
    )
    card(
        s,
        Inches(0.45),
        Inches(4.90),
        Inches(6.05),
        Inches(2.05),
        "Deep mask (this mesh)",
        [
            "refBottomDepth[k] > 2000",
            "and k ≤ maxLevelCell[i]  and  bottomDepth[i] > 2000",
            "k = 46…60 (1-based)  ·  15 deep levels",
        ],
        GOLD,
        14,
        13,
    )
    card(
        s,
        Inches(6.70),
        Inches(4.90),
        Inches(6.15),
        Inches(2.05),
        "DATM, not coupler fluxes",
        [
            "Use NCEP u,v,t,slp + GXGXS prc",
            "Do not train on windStress / latentHeat / rainFlux",
            "Those depend on SST and ice",
        ],
        TEAL,
        14,
        13,
    )
    notes(s, "If someone asks about SSH writeback: reconstruct from layerThickness inside MPAS. Do not invent an ssh variable.")
    return s


def add_problem(prs, k, n):
    s = blank(prs)
    chrome(s, "Learning problem: a spinup operator, not weather", k, n, "Conditional residual on the deep mask")
    round_rect(s, Inches(0.45), Inches(1.20), Inches(12.4), Inches(1.55), NAVY)
    txt(
        s,
        Inches(0.7),
        Inches(1.45),
        Inches(12.0),
        Inches(0.50),
        "x̂  t+Δ   =   x t   +   Δx ( x t ,  F ,  θ ,  G )",
        26,
        True,
        WHITE,
        PP_ALIGN.CENTER,
        MSO_ANCHOR.MIDDLE,
    )
    txt(
        s,
        Inches(0.7),
        Inches(2.05),
        Inches(12.0),
        Inches(0.40),
        "Predict the residual. Persistence  x̂ = x t  is the first baseline we must beat.",
        14,
        False,
        RGBColor(0xC5, 0xD4, 0xE8),
        PP_ALIGN.CENTER,
    )
    specs = [
        ("x t", "Early restart", "Deep T, S, h  (u later)"),
        ("x t+Δ", "Later restart", "Same fields, same mesh"),
        ("F", "DATM NYF", "12-month climatology"),
        ("θ", "mpaso_in", "GM, visc, KPP, …"),
        ("G", "MPAS graph", "cellsOnCell, areas, f"),
        ("Δ", "Lead time", "20 / 50 / ~550 yr"),
    ]
    x = Inches(0.45)
    for a, b, c in specs:
        round_rect(s, x, Inches(3.00), Inches(2.00), Inches(1.85), CARD, LINE)
        txt(s, x + Inches(0.08), Inches(3.12), Inches(1.84), Inches(0.40), a, 18, True, TEAL, PP_ALIGN.CENTER)
        txt(s, x + Inches(0.08), Inches(3.52), Inches(1.84), Inches(0.40), b, 13, True, NAVY, PP_ALIGN.CENTER)
        txt(s, x + Inches(0.08), Inches(3.95), Inches(1.84), Inches(0.70), c, 12, False, MUTED, PP_ALIGN.CENTER)
        x += Inches(2.13)
    round_rect(s, Inches(0.45), Inches(5.10), Inches(12.4), Inches(1.85), GOLD_LT, GOLD)
    bullets(
        s,
        Inches(0.70),
        Inches(5.25),
        Inches(12.0),
        Inches(1.55),
        [
            "This is LandSim’s early→eq map, with spatial coupling on G — not GraphCast’s 6-hour atmosphere rollout.",
            "F and θ are conditions (FiLM). They do not differentiate samples until we have ensembles.",
            "Diffusion / flow is the target wrapper, not the first training job. Two restarts will overfit.",
        ],
        15,
        INK,
        6,
    )
    notes(s, "If asked about probabilistic models: yes later, as a drop-in denoiser around the same mesh GNN.")
    return s


def add_arch(prs, k, n):
    s = blank(prs)
    chrome(s, "Architecture: LandSim pairing + GraphCast mesh operators", k, n, "Native MPAS incidence. No ocean lat–lon interpolate.")
    boxes = [
        (Inches(0.40), "x t  +  G", "cells / edges\nfrom restart"),
        (Inches(3.55), "Encoders", "DATM B1  ·  θ FiLM\nnode embed"),
        (Inches(6.70), "Mesh GNN", "10–12 MP steps\n128–256 latent"),
        (Inches(9.85), "ΔT, ΔS  (+Δh)", "residual add\n+ deep mask"),
    ]
    y = Inches(1.35)
    for i, (x, title, sub) in enumerate(boxes):
        round_rect(s, x, y, Inches(2.95), Inches(1.55), TEAL_LT, TEAL, 1.5)
        txt(s, x + Inches(0.1), y + Inches(0.18), Inches(2.75), Inches(0.45), title, 16, True, NAVY, PP_ALIGN.CENTER)
        txt(s, x + Inches(0.1), y + Inches(0.70), Inches(2.75), Inches(0.70), sub, 13, False, MUTED, PP_ALIGN.CENTER)
        if i < 3:
            txt(s, x + Inches(2.85), y + Inches(0.50), Inches(0.75), Inches(0.45), "→", 28, True, TEAL, PP_ALIGN.CENTER)
    txt(s, Inches(0.45), Inches(3.10), Inches(12.4), Inches(0.35), "Reuse vs replace", 16, True, NAVY)
    table(
        s,
        Inches(0.45),
        Inches(3.45),
        Inches(12.4),
        Inches(3.45),
        [
            ["Keep", "From", "Do not copy"],
            ["Pairing, scalers, restart overwrite", "LandSim", "Per-cell IID Transformer"],
            ["TypedGraph, geometric edges, residual heads", "GraphCast / GenCast", "Icosahedral mesh, ERA5 lat–lon loss"],
            ["areaCell × thickness weighted Huber", "MPAS measure", "GraphCast latitude weights"],
            ["DATM bilinear T62 → cells (B1)", "E3SM mapalgo", "ViT on interpolated ocean maps"],
        ],
        col_w=[Inches(5.0), Inches(3.2), Inches(4.2)],
        font=13,
    )
    notes(
        s,
        "QU240 is 7k cells — full-graph GNN or even dense attention is feasible. "
        "EC30to60 later needs sparse / METIS multi-scale, not GraphCast merge_meshes.",
    )
    return s


def add_tracks(prs, k, n):
    s = blank(prs)
    chrome(s, "Three tracks  —  same IO, swap the processor", k, n, "Train A now. Keep C as a drop-in denoiser.")
    tracks = [
        (GREEN, GREEN_LT, "A  ·  MVP", "Deterministic mesh GNN", ["DeepTypedGraphNet-style MP", "Area-weighted Huber on Δx", "Cell T/S first; velocity later", "Start as soon as one restart .nc is local"]),
        (TEAL, TEAL_LT, "B  ·  if needed", "Mesh transformer", ["Dense attention is OK on 7k cells", "Sparse k-hop for EC meshes", "Same residual objective as A", "Use if MP receptive field is too local"]),
        (GOLD, GOLD_LT, "C  ·  later", "Conditional flow / diffusion", ["Same GNN as the denoiser", "Noise the residual, condition on xt,F,θ,G", "Needs O(10²)+ pairs", "Ensemble of 4–8 late states"]),
    ]
    x = Inches(0.40)
    for acc, bg, tag, title, lines in tracks:
        round_rect(s, x, Inches(1.20), Inches(4.05), Inches(4.35), CARD, LINE)
        rect(s, x, Inches(1.20), Inches(4.05), Inches(0.90), acc)
        txt(s, x + Inches(0.18), Inches(1.28), Inches(3.70), Inches(0.35), tag, 13, True, WHITE)
        txt(s, x + Inches(0.18), Inches(1.58), Inches(3.70), Inches(0.40), title, 16, True, WHITE)
        bullets(s, x + Inches(0.20), Inches(2.25), Inches(3.65), Inches(3.10), lines, 14, INK, 8)
        x += Inches(4.20)
    round_rect(s, Inches(0.40), Inches(5.70), Inches(12.5), Inches(1.25), GOLD_LT, GOLD)
    txt(
        s,
        Inches(0.65),
        Inches(5.90),
        Inches(12.1),
        Inches(0.90),
        "Do not start Track C on two sample restarts. Prefer flow matching over vanilla DDPM when pair count allows. "
        "Never diffuse F or θ — they are conditions, not generated fields.",
        15,
        False,
        INK,
        anchor=MSO_ANCHOR.MIDDLE,
    )
    notes(s, "Recommend Track A as the team’s near-term build. Track C is an interface, not this quarter’s training run.")
    return s


def add_pairs(prs, k, n):
    s = blank(prs)
    chrome(s, "Pair factory: the long trajectory is the dataset", k, n, "One 50→600 map per run is one example. That cannot train a net.")
    table(
        s,
        Inches(0.45),
        Inches(1.18),
        Inches(12.4),
        Inches(2.55),
        [
            ["Stream", "Source", "Per sample"],
            ["X / Y", "Restarts at t and t+Δ", "Deep T, S, layerThickness  (± normalVelocity)"],
            ["F / θ / G", "DATM NYF, mpaso_in, restart geometry", "Shared across NYF samples; graph cached once"],
            ["QC", "Monthly history (optional)", "OHC 2000 m–bottom time series"],
        ],
        col_w=[Inches(1.8), Inches(4.2), Inches(6.4)],
        font=13,
    )
    recipes = [
        ("Sliding annual", "Consecutive Jan-1 restarts", "Dense local residuals"),
        ("Multi-horizon", "Δ ∈ {20, 50, 100, …} yr", "Condition on Δ (or log Δ)"),
        ("Curriculum", "Short Δ first, then longer", "Stabilizes residual learning"),
        ("Later ensembles", "GM/Redi, IAF, 2nd mesh", "Makes F and θ identifiable"),
    ]
    x = Inches(0.45)
    for title, a, b in recipes:
        round_rect(s, x, Inches(3.95), Inches(3.05), Inches(1.70), CARD, LINE)
        txt(s, x + Inches(0.12), Inches(4.05), Inches(2.80), Inches(0.35), title, 14, True, TEAL)
        txt(s, x + Inches(0.12), Inches(4.42), Inches(2.80), Inches(0.50), a, 12, False, INK)
        txt(s, x + Inches(0.12), Inches(4.95), Inches(2.80), Inches(0.50), b, 12, False, MUTED)
        x += Inches(3.18)
    round_rect(s, Inches(0.45), Inches(5.80), Inches(12.4), Inches(1.15), TEAL_LT, TEAL)
    txt(
        s,
        Inches(0.70),
        Inches(5.95),
        Inches(12.0),
        Inches(0.90),
        "Ask of Hyun: all annual (or 5-year) rst files from ~year 20 to ~year 600, plus paths for the intended 50 yr and 600 yr restarts. "
        "Hold out a late window or a basin — not random cells.",
        15,
        False,
        NAVY,
        anchor=MSO_ANCHOR.MIDDLE,
    )
    notes(s, "Identity join on cell/edge indices. No lat/lon KD-tree. Deep-only tensors cut volume ~4×.")
    return s


def add_wps(prs, k, n):
    s = blank(prs)
    chrome(s, "Work packages", k, n, "WP0 schema is done locally. Critical path is payloads + year list.")
    rows = [
        ["WP", "What", "Status / gate"],
        ["0  Schema", "Names, deep mask, DATM, θ tokens", "Done in repo. Open: year list + .nc files"],
        ["1  Graph + data", "TypedGraph from restart; Dataset; persistence RMSE", "Starts with one rst.nc (0661 enough)"],
        ["2  Track A GNN", "Cell residual ΔT, ΔS; FiLM stubs; writeback", "Needs pairs beyond 0661/0681 to train"],
        ["3  Forward test", "N-day MPAS run from ML restart; MPAS-Analysis", "After writeback works"],
        ["4  Edges + flow", "normalVelocity; Δ-conditioned; flow matching", "Only if N ≳ 100 pairs"],
        ["5  Generalize", "2nd mpaso_in / forcing / mesh", "New simulations required"],
    ]
    table(s, Inches(0.45), Inches(1.18), Inches(12.4), Inches(4.55), rows, col_w=[Inches(2.2), Inches(5.7), Inches(4.5)], font=13)
    round_rect(s, Inches(0.45), Inches(5.90), Inches(12.4), Inches(1.05), GOLD_LT, GOLD)
    txt(
        s,
        Inches(0.70),
        Inches(6.05),
        Inches(12.0),
        Inches(0.75),
        "First number to publish: area-weighted persistence RMSE 0661 → 0681 on deep T. Any GNN must beat persistence and linear drift.",
        15,
        True,
        INK,
        anchor=MSO_ANCHOR.MIDDLE,
    )
    notes(s, "Olawale: Ocean_dataGEN pairing. Dali: graph builder. Hyun: year list. Alice: OHC thresholds.")
    return s


def add_card_v1(prs, k, n):
    s = blank(prs)
    chrome(s, "v1 model card  —  freeze these choices", k, n, "Unambiguous enough to implement without re-litigating architecture")
    table(
        s,
        Inches(0.45),
        Inches(1.18),
        Inches(12.4),
        Inches(5.75),
        [
            ["Item", "v1 choice"],
            ["Mesh", "QU240 only (nCells = 7153)"],
            ["State", "Deep k=46–60 temperature, salinity; optional layerThickness"],
            ["Velocity", "Deferred (cell-only Track A)"],
            ["Atmosphere F", "NYF 12-month means remapped to cells (constant for this case)"],
            ["Config θ", "mpaso_variables vector (constant for this case)"],
            ["Lead Δ", "Conditioning token; train on all available checkpoint gaps"],
            ["Processor", "10–12 step interaction GNN, 128–256 latent, residual"],
            ["Loss", "Huber, areaCell × restingThickness, deep mask"],
            ["Generative", "Interface ready (noise / FiLM slot); not trained until pair count allows"],
            ["Output", "Residual add + mask → overwrite selected 3D restart fields"],
        ],
        col_w=[Inches(2.6), Inches(9.8)],
        font=14,
    )
    notes(s, "Ask the team to accept this card. Changes after WP1 should be explicit.")
    return s


def add_asks(prs, k, n):
    s = blank(prs)
    chrome(s, "Asks and next two weeks", k, n, "Schema dump is done. Remaining work is data logistics + WP1.")
    people = [
        (GREEN, "Hyun", ["Publish the full rst.*.nc year list", "Confirm ~50 yr and ~600 yr paths", "Copy at least 0661 .nc to the workdir", "MPAS-Analysis / plot utilities"]),
        (TEAL, "Alice", ["Confirm deep-OHC as the eq index", "Review k=46…60 mask", "Drift / OHC thresholds for ‘near eq’"]),
        (NAVY2, "Olawale", ["Ocean_dataGEN pairing from LandSim", "Index of (t, t+Δ) once the year list exists", "Scaler + identity cell/edge join"]),
        (GOLD, "Dali", ["mpas_mesh_to_typedgraph.py on 0661", "Persistence RMSE 0661→0681", "Track A skeleton + writeback"]),
    ]
    x = Inches(0.40)
    for acc, name, lines in people:
        round_rect(s, x, Inches(1.20), Inches(3.05), Inches(3.95), CARD, LINE)
        rect(s, x, Inches(1.20), Inches(3.05), Inches(0.55), acc)
        txt(s, x + Inches(0.15), Inches(1.28), Inches(2.75), Inches(0.40), name, 18, True, WHITE)
        bullets(s, x + Inches(0.12), Inches(1.90), Inches(2.80), Inches(3.05), lines, 13, INK, 6)
        x += Inches(3.20)
    round_rect(s, Inches(0.40), Inches(5.35), Inches(12.5), Inches(1.60), NAVY)
    txt(s, Inches(0.65), Inches(5.50), Inches(12.1), Inches(0.35), "Do not wait on", 14, True, RGBColor(0x8F, 0xC9, 0xC8))
    txt(
        s,
        Inches(0.65),
        Inches(5.90),
        Inches(12.1),
        Inches(0.80),
        "A ViT on interpolated maps  ·  Diffusion on two restarts  ·  Learning F or θ from one NYF case  ·  "
        "Inventing ssh in the restart  ·  Treating 0661/0681 as the training set.",
        16,
        False,
        WHITE,
        anchor=MSO_ANCHOR.TOP,
    )
    notes(
        s,
        "Close by repeating: copy one restart file and we can build the graph this week. "
        "The year list unblocks everyone else.",
    )
    return s


def main():
    prs = new_prs()
    slides = [
        add_title,
        add_agenda,
        add_verdict,
        add_sample,
        add_ohc,
        add_io,
        add_problem,
        add_arch,
        add_tracks,
        add_pairs,
        add_wps,
        add_card_v1,
        add_asks,
    ]
    n = len(slides)
    add_title(prs, n)
    for i, fn in enumerate(slides[1:], start=2):
        fn(prs, i, n)
    prs.save(OUT)
    print(f"Wrote {OUT}  ({n} slides)")


if __name__ == "__main__":
    main()
