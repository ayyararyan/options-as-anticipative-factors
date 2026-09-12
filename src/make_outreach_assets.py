#!/usr/bin/env python3
"""Build the email-ready Phase II figure, summary table, and one-page research note.

This script uses only versioned aggregate Phase II outputs. It does not require or read
licensed row-level option/spot data.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
plt.rcParams["svg.fonttype"] = "none"
import numpy as np
import pandas as pd
from matplotlib.colors import TwoSlopeNorm
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
FIGURES = RESULTS / "figures"
TABLES = RESULTS / "tables"
DOCS = ROOT / "docs"

SUMMARY_PATH = RESULTS / "phase2_summary.json"
WIDTH_PATH = TABLES / "phase2_width_sensitivity.csv"
FIGURE_PATH = FIGURES / "lehalle_anticipative_map.png"
FIGURE_SVG_PATH = FIGURES / "lehalle_anticipative_map.svg"
TABLE_PATH = TABLES / "lehalle_summary_table.csv"
PDF_PATH = DOCS / "lehalle_one_page_note.pdf"
MARKDOWN_PATH = DOCS / "lehalle_one_page_note.md"

NAVY = "#17365D"
BLUE = "#2E6F9E"
RED = "#A64B4B"
GREY = "#5A6573"
DARK = "#1F2933"


def load_inputs() -> tuple[dict, pd.DataFrame]:
    summary = json.loads(SUMMARY_PATH.read_text())
    width = pd.read_csv(WIDTH_PATH)
    return summary, width


def metric_pair(summary: dict, event: str) -> tuple[dict, dict]:
    rows = [r for r in summary["headline_metrics"] if r["event"] == event]
    base = next(r for r in rows if r["model"] == "level_controls")
    shape = next(r for r in rows if r["model"] == "plus_shape")
    return base, shape


def bootstrap_row(summary: dict, event: str) -> dict:
    return next(r for r in summary["bootstrap"] if r["event"] == event and r["metric"] == "brier")


def build_summary_table(summary: dict) -> pd.DataFrame:
    rows = []
    specs = [
        ("Any one-scale breach", "two_sided_1sigma"),
        ("Downside breach", "down_1sigma"),
        ("Upside breach", "up_1sigma"),
    ]
    for label, event in specs:
        base, shape = metric_pair(summary, event)
        widths = summary["width_sign_counts"][event]
        rows.append({
            "Task": label,
            "N / events": f'{base["n"]} / {base["events"]}',
            "Brier: level": base["brier"],
            "Brier: +shape": shape["brier"],
            "Delta Brier": shape["brier"] - base["brier"],
            "AUC: level": base["auc"],
            "AUC: +shape": shape["auc"],
            "Widths improved": f'{widths["n_brier_improvements"]}/{widths["n_widths"]}',
        })

    base, shape = summary["conditional_direction"]
    widths = summary["width_sign_counts"]["down_given_1sigma_breach"]
    rows.append({
        "Task": "Direction given a breach*",
        "N / events": f'{base["n"]} / {base["events"]}',
        "Brier: level": base["brier"],
        "Brier: +shape": shape["brier"],
        "Delta Brier": shape["brier"] - base["brier"],
        "AUC: level": base["auc"],
        "AUC: +shape": shape["auc"],
        "Widths improved": f'{widths["n_brier_improvements"]}/{widths["n_widths"]}',
    })
    out = pd.DataFrame(rows)
    out.to_csv(TABLE_PATH, index=False)
    return out


def build_figure(summary: dict, width: pd.DataFrame) -> None:
    tasks = [
        ("Any large move\n|z| >= 1", "two_sided_1sigma"),
        ("Downside tail\nz <= -1", "down_1sigma"),
        ("Upside tail\nz >= +1", "up_1sigma"),
        ("Direction, given\na large move*", "down_given_1sigma_breach"),
    ]

    deltas, los, his = [], [], []
    for _, event in tasks[:3]:
        base, shape = metric_pair(summary, event)
        boot = bootstrap_row(summary, event)
        deltas.append(shape["brier"] - base["brier"])
        los.append(boot["ci_lo_95"])
        his.append(boot["ci_hi_95"])
    cbase, cshape = summary["conditional_direction"]
    cboot = next(r for r in summary["conditional_direction_bootstrap"] if r["metric"] == "brier")
    deltas.append(cshape["brier"] - cbase["brier"])
    los.append(cboot["ci_lo_95"])
    his.append(cboot["ci_hi_95"])

    fig = plt.figure(figsize=(12.4, 8.1), constrained_layout=False)
    gs = fig.add_gridspec(2, 1, height_ratios=[1.0, 1.05], hspace=0.52, top=0.82, bottom=0.11, left=0.18, right=0.94)
    ax = fig.add_subplot(gs[0, 0])
    y = np.arange(len(tasks))
    for i, (d, lo, hi) in enumerate(zip(deltas, los, his)):
        color = BLUE if d < 0 else RED
        ax.errorbar(d, i, xerr=[[d - lo], [hi - d]], fmt="o", ms=9, lw=2.0, capsize=4, color=color, ecolor=color, zorder=3)
    ax.axvline(0, color="#7B8794", lw=1.2)
    ax.set_yticks(y, [t[0] for t in tasks], fontsize=11)
    ax.invert_yaxis()
    ax.set_xlabel("Change in out-of-sample Brier score after adding smile shape\n(negative = better)", fontsize=11)
    ax.set_xlim(-0.125, 0.025)
    ax.grid(axis="x", alpha=0.16)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.set_title("A. Incremental predictive content of smile geometry", loc="left", fontsize=13, fontweight="bold", color=DARK, pad=10)

    labels = ["No gain", "Tiny", "7.5% lower Brier", "14.9% lower Brier*"]
    for i, (d, lab) in enumerate(zip(deltas, labels)):
        offset = 0.004 if d >= 0 else -0.004
        ha = "left" if d >= 0 else "right"
        ax.text(d + offset, i, lab, va="center", ha=ha, fontsize=9.5, color=DARK, fontweight="bold" if i >= 2 else "normal")

    ax2 = fig.add_subplot(gs[1, 0])
    widths = [1, 2, 3, 4, 5, 6, 8, 10]
    row_events = [t[1] for t in tasks]
    mat = np.full((4, len(widths)), np.nan)
    for i, event in enumerate(row_events):
        for j, w in enumerate(widths):
            r = width[(width["event"] == event) & (width["width_index"] == w)]
            if not r.empty:
                mat[i, j] = float(r.iloc[0]["diff_brier_plus_shape_minus_level"])

    vmax = float(np.nanmax(np.abs(mat)))
    norm = TwoSlopeNorm(vmin=-vmax, vcenter=0, vmax=vmax)
    im = ax2.imshow(mat, aspect="auto", cmap="RdBu_r", norm=norm)
    ax2.set_xticks(np.arange(len(widths)), [str(w) for w in widths], fontsize=10)
    ax2.set_yticks(np.arange(4), [t[0].replace("\n", " ") for t in tasks], fontsize=10)
    ax2.set_xlabel("Symmetric wing-width index used to measure smile geometry", fontsize=11)
    ax2.set_title("B. Width robustness: the directional pattern survives every wing definition", loc="left", fontsize=13, fontweight="bold", color=DARK, pad=10)
    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            v = mat[i, j]
            text_color = "white" if abs(v) > 0.45 * vmax else DARK
            ax2.text(j, i, f"{v:+.3f}", ha="center", va="center", fontsize=8.5, color=text_color)
    for spine in ax2.spines.values():
        spine.set_visible(False)
    cbar = fig.colorbar(im, ax=ax2, fraction=0.025, pad=0.025)
    cbar.set_label("Delta Brier (+shape - level)", fontsize=9)
    cbar.ax.tick_params(labelsize=8)

    fig.text(0.08, 0.955, "Where does the smile's extra information live?", fontsize=22, fontweight="bold", color=NAVY)
    fig.text(0.08, 0.915, "In this sample, cross-strike shape adds little to the magnitude of risk - but repeatedly tilts its direction.", fontsize=12.5, color=GREY)
    fig.text(0.08, 0.875, "NIFTY weekly options | one earliest observation per expiry | evaluation: 2025-01-03 to 2026-05-13", fontsize=10.5, color=GREY)
    fig.text(0.08, 0.035, "73 evaluation expiries; 23 one-scale breaches. Error bars: paired expiry bootstrap, 95% interval.  *Conditional-direction panel is diagnostic: it conditions on a future breach (N=23).", fontsize=9.2, color=GREY)
    fig.savefig(FIGURE_PATH, dpi=240, bbox_inches="tight", facecolor="white")
    fig.savefig(FIGURE_SVG_PATH, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def build_pdf(summary: dict, table_df: pd.DataFrame) -> None:
    DOCS.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(PDF_PATH), pagesize=A4, rightMargin=13 * mm, leftMargin=13 * mm, topMargin=12 * mm, bottomMargin=10 * mm)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="TitleX", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=17.5, leading=20, textColor=colors.HexColor(NAVY), spaceAfter=3))
    styles.add(ParagraphStyle(name="SubX", parent=styles["Normal"], fontName="Helvetica", fontSize=8.7, leading=11, textColor=colors.HexColor(GREY), spaceAfter=6))
    styles.add(ParagraphStyle(name="BodyX", parent=styles["Normal"], fontName="Helvetica", fontSize=8.4, leading=11.1, textColor=colors.HexColor(DARK)))
    styles.add(ParagraphStyle(name="HeadX", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=10.2, leading=12, textColor=colors.HexColor(NAVY), spaceBefore=3, spaceAfter=3))
    styles.add(ParagraphStyle(name="SmallX", parent=styles["Normal"], fontName="Helvetica", fontSize=7.2, leading=9, textColor=colors.HexColor(GREY)))

    story = [
        Paragraph("Options as anticipative factors: where does the smile's information live?", styles["TitleX"]),
        Paragraph("Exploratory Phase II note - NIFTY weekly options, one non-overlapping observation per expiry", styles["SubX"]),
        Paragraph("<b>Question.</b> After conditioning on the ATM option-implied movement scale, does cross-strike smile geometry add information about the size of the future move, or about which side of the distribution is tilted?", styles["BodyX"]),
        Spacer(1, 3 * mm),
    ]
    img = Image(str(FIGURE_PATH))
    img.drawWidth = 182 * mm
    img.drawHeight = 119 * mm
    story += [img, Spacer(1, 1.8 * mm), Paragraph("Compact out-of-sample readout", styles["HeadX"])]

    headers = ["Task", "N/events", "Brier\nlevel", "Brier\n+shape", "Delta", "AUC\nlevel -> shape", "Widths\nimproved"]
    body = []
    for _, r in table_df.iterrows():
        body.append([r["Task"], r["N / events"], f'{r["Brier: level"]:.4f}', f'{r["Brier: +shape"]:.4f}', f'{r["Delta Brier"]:+.4f}', f'{r["AUC: level"]:.3f} -> {r["AUC: +shape"]:.3f}', r["Widths improved"]])
    t = Table([headers] + body, colWidths=[43*mm, 18*mm, 18*mm, 18*mm, 16*mm, 34*mm, 25*mm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor(NAVY)), ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"), ("FONTSIZE", (0,0), (-1,0), 7.1),
        ("LEADING", (0,0), (-1,0), 8.3), ("ALIGN", (1,0), (-1,-1), "CENTER"),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"), ("FONTNAME", (0,1), (-1,-1), "Helvetica"),
        ("FONTSIZE", (0,1), (-1,-1), 7.0), ("LEADING", (0,1), (-1,-1), 8.5),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#F6F8FA")]),
        ("GRID", (0,0), (-1,-1), 0.35, colors.HexColor("#CDD5DF")),
        ("LEFTPADDING", (0,0), (-1,-1), 4), ("RIGHTPADDING", (0,0), (-1,-1), 4),
        ("TOPPADDING", (0,0), (-1,-1), 4), ("BOTTOMPADDING", (0,0), (-1,-1), 4),
    ]))
    story += [t, Spacer(1, 2.0 * mm)]
    story.append(Paragraph("<b>Readout.</b> Smile shape does not improve the probability of a two-sided one-scale breach (0/8 wing definitions improve Brier). The strongest OOS signal is directional: upside-breach Brier falls from 0.1227 to 0.1134, and all 8/8 wing definitions improve it. Conditioning on an eventual breach, shape also improves downside-vs-upside classification at all 8/8 widths, but that N=23 diagnostic is not directly tradable and uncertainty remains wide.", styles["BodyX"]))
    story.append(Spacer(1, 1.2 * mm))
    story.append(Paragraph("<b>Interpretation.</b> The evidence is consistent with a decomposition in which ATM level mainly summarizes forward risk magnitude, while cross-strike state prices may encode distributional tilt. This is hypothesis-generating rather than conclusive; the natural next test is the same design using the historical eSSVI state (theta, rho, psi, RR/BF and their changes).", styles["BodyX"]))
    story.append(Spacer(1, 1.2 * mm))
    story.append(Paragraph("* Direction-given-breach conditions on a future event and is reported only as a mechanism diagnostic. Aggregate outputs and code are reproducible; licensed row-level market data are not redistributed.", styles["SmallX"]))
    doc.build(story)


def build_markdown(summary: dict, table_df: pd.DataFrame) -> None:
    rows = []
    for _, r in table_df.iterrows():
        rows.append(f'| {r["Task"]} | {r["N / events"]} | {r["Brier: level"]:.4f} | {r["Brier: +shape"]:.4f} | {r["Delta Brier"]:+.4f} | {r["AUC: level"]:.3f} -> {r["AUC: +shape"]:.3f} | {r["Widths improved"]} |')
    text = """# Options as anticipative factors: where does the smile's information live?\n\n**Exploratory Phase II note - NIFTY weekly options, one non-overlapping observation per expiry**\n\n**Question.** After conditioning on the ATM option-implied movement scale, does cross-strike smile geometry add information about the size of the future move, or about which side of the distribution is tilted?\n\n![Where does the smile's extra information live?](../results/figures/lehalle_anticipative_map.svg)\n\n## Compact out-of-sample readout\n\n| Task | N/events | Brier level | Brier +shape | Delta | AUC level -> shape | Widths improved |\n|---|---:|---:|---:|---:|---:|---:|\n""" + "\n".join(rows) + """\n\n**Readout.** Smile shape does not improve the probability of a two-sided one-scale breach (0/8 wing definitions improve Brier). The strongest OOS signal is directional: upside-breach Brier falls from 0.1227 to 0.1134, and all 8/8 wing definitions improve it. Conditioning on an eventual breach, shape also improves downside-vs-upside classification at all 8/8 widths, but that N=23 diagnostic is not directly tradable and uncertainty remains wide.\n\n**Interpretation.** The evidence is consistent with a decomposition in which ATM level mainly summarizes forward risk magnitude, while cross-strike state prices may encode distributional tilt. This is hypothesis-generating rather than conclusive; the natural next test is the same design using the historical eSSVI state (`theta`, `rho`, `psi`, RR/BF and their changes).\n\n*Direction-given-breach conditions on a future event and is reported only as a mechanism diagnostic. Aggregate outputs and code are reproducible; licensed row-level market data are not redistributed.*\n"""
    MARKDOWN_PATH.write_text(text)


def main() -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    TABLES.mkdir(parents=True, exist_ok=True)
    summary, width = load_inputs()
    table_df = build_summary_table(summary)
    build_figure(summary, width)
    build_pdf(summary, table_df)
    build_markdown(summary, table_df)
    print(FIGURE_PATH)
    print(FIGURE_SVG_PATH)
    print(TABLE_PATH)
    print(PDF_PATH)
    print(MARKDOWN_PATH)


if __name__ == "__main__":
    main()
