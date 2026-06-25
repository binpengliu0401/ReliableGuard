"""Generate the five conceptual diagrams (Figures 1-5) for ReliableGuard_Thesis_v9.

These are the hand-drawable diagrams left as [FIGURE N] placeholders in the thesis. The visual style
deliberately follows the convention of the closest related papers (tasks/papers/: tau-bench,
AgentSpec, FActScore, AGrail): a muted pastel palette with light role-coded fills and thin darker
borders, generous whitespace, no text crossing a line, light grouping bands, numbered step circles,
and pill tags for code identifiers. Saturated colour is used only for small accents. The figure
title is NOT drawn inside the canvas; the bold "Figure N." caption lives in the thesis markdown,
mirroring the related work.

Run from the repo root:  python3 eval/make_concept_figures.py
Output:                   docs/thesis/figures_v9/figure1..5.png
"""

from __future__ import annotations

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Ellipse, FancyArrowPatch, FancyBboxPatch, PathPatch
from matplotlib.path import Path

OUT_DIR = "docs/thesis/figures_v9"

# Muted academic palette: light fills, a shade-darker thin border, role-coded after tau-bench
# (gray = neutral/tools/unreachable, blue = agent/structural, green = answer channel, red = user/
# oracle/intent, amber = neural stage).
F_AGENT, E_AGENT = "#dbe6f3", "#3a6ea5"
F_ANSWER, E_ANSWER = "#dcefe1", "#4e9a6b"
F_USER, E_USER = "#f7ddd8", "#c2584e"
F_NEUT, E_NEUT = "#ededed", "#8a8a8a"
F_NEURAL, E_NEURAL = "#fbeed0", "#c79a33"
BAND = "#f4f6f9"      # light grouping band
BAND_GRAY = "#eceef0"  # unreachable band
INK = "#242424"
MUTE = "#6c6c6c"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 11,
    "savefig.facecolor": "white",
})


def box(ax, x, y, w, h, text, *, fc, ec, fs=10, bold=False, lw=1.0, sub=None, sub_fs=8,
        text_color=None, round_size=0.10):
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle=f"round,pad=0.015,rounding_size={round_size}",
        facecolor=fc, edgecolor=ec, linewidth=lw, mutation_aspect=1.0, zorder=3))
    cy = y + h / 2 + (0.12 * h if sub else 0)
    ax.text(x + w / 2, cy, text, ha="center", va="center", fontsize=fs,
            fontweight="bold" if bold else "normal", color=text_color or INK, zorder=5)
    if sub:
        ax.text(x + w / 2, y + h / 2 - 0.26 * h, sub, ha="center", va="center",
                fontsize=sub_fs, color=MUTE, style="italic", zorder=5)


def band(ax, x, y, w, h, *, fc=BAND, ec="none", ls="-", lw=1.0, round_size=0.08):
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle=f"round,pad=0.02,rounding_size={round_size}",
        facecolor=fc, edgecolor=ec, linewidth=lw, linestyle=ls, zorder=1))


def tag(ax, x, y, w, h, text, *, fc="#ffffff", ec=E_NEUT, fs=8.5, mono=True):
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.012,rounding_size=0.18",
        facecolor=fc, edgecolor=ec, linewidth=0.9, zorder=4))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs,
            family="DejaVu Sans Mono" if mono else "DejaVu Sans", color=INK, zorder=5)


def arrow(ax, p0, p1, *, color=INK, lw=1.2, style="-|>", ls="-", rad=0.0):
    ax.add_patch(FancyArrowPatch(
        p0, p1, arrowstyle=style, mutation_scale=11, color=color, linewidth=lw,
        linestyle=ls, connectionstyle=f"arc3,rad={rad}", zorder=4,
        shrinkA=2, shrinkB=2))


def step_num(ax, x, y, n, *, color):
    ax.add_patch(Circle((x, y), 0.16, facecolor="white", edgecolor=color, linewidth=1.3, zorder=6))
    ax.text(x, y, str(n), ha="center", va="center", fontsize=8.5, fontweight="bold",
            color=color, zorder=7)


def col_title(ax, x, y, text, color=INK):
    ax.text(x, y, text, ha="center", va="center", fontsize=11.5, color=color,
            fontweight="bold")


# --------------------------------------------------------------------------------------------------
# Figure 1 — Observable channels and the locus taxonomy (left to right).
# --------------------------------------------------------------------------------------------------
def figure1():
    fig, ax = plt.subplots(figsize=(14.6, 6.8))
    ax.set_xlim(0, 14.6)
    ax.set_ylim(0, 6.8)
    ax.axis("off")
    ty = 6.35

    # Column grouping bands.
    band(ax, 2.55, 0.45, 3.1, 5.45, fc=BAND)
    band(ax, 6.2, 0.45, 3.35, 5.45, fc=BAND)
    col_title(ax, 1.25, ty, "Agent")
    col_title(ax, 4.1, ty, "Observation channels", E_AGENT)
    col_title(ax, 7.85, ty, "Locus of ground truth")
    col_title(ax, 12.85, ty, "Verdict")

    # Agent.
    box(ax, 0.3, 2.55, 1.9, 1.7, "Agent\nexecution", fc=F_NEUT, ec=E_NEUT, bold=True, fs=11,
        sub="black box", sub_fs=8)

    # Channels (each tinted by the locus colour it feeds).
    chans = [
        (4.55, "Answer text", "respond turns", F_ANSWER, E_ANSWER),
        (2.95, "Tool trace", "env.actions", F_AGENT, E_AGENT),
        (1.35, "Database state", "env.data Δ", F_AGENT, E_AGENT),
    ]
    cxm = 2.75 + 2.7 / 2  # channel-box centre, used to centre the code pill
    for yc, name, code, fc, ec in chans:
        box(ax, 2.75, yc, 2.7, 1.25, name, fc=fc, ec=ec, fs=10.5, bold=True)
        tw = 0.34 + len(code) * 0.072  # pill width sized to its monospace text
        tag(ax, cxm - tw / 2, yc + 0.14, tw, 0.36, code, fs=8.5)
        arrow(ax, (2.2, 3.4), (2.75, yc + 0.62), color=E_NEUT, lw=1.1)

    # Loci, top to bottom. Reachable loci get a colour-matched channel arrow.
    loci = [
        (5.05, "answer-local", F_ANSWER, E_ANSWER, 4.55, None),
        (3.85, "trace-local", F_AGENT, E_AGENT, 2.95, None),
        (2.65, "state-local", F_AGENT, E_AGENT, 1.35, None),
        (1.50, "evidence-local", F_NEUT, E_NEUT, None, "no KB channel"),
        (0.55, "intent-local", F_NEUT, E_NEUT, None, "ground truth in user goal"),
    ]
    # Unreachable grouping band behind the two gray loci.
    band(ax, 6.4, 0.45, 2.95, 2.0, fc=BAND_GRAY, ec=E_NEUT, ls=(0, (4, 3)), lw=1.1)
    ax.text(7.875, 0.27, "beyond any black-box monitor", ha="center", fontsize=8.2,
            style="italic", color=MUTE)
    for yc, name, fc, ec, ch_y, note in loci:
        box(ax, 6.5, yc, 2.75, 0.92, name, fc=fc, ec=ec, fs=10.5, bold=True,
            sub=note, sub_fs=7.5)
        if ch_y is not None:
            arrow(ax, (5.45, ch_y + 0.62), (6.5, yc + 0.46), color=ec, lw=1.4)

    # Verdict pills (pushed right to leave a clean gap after the locus band at x=9.35).
    vx = 11.85
    verdicts = [
        (4.35, "PASS_VERIFIED", E_ANSWER),
        (2.95, "BLOCK", E_USER),
        (1.55, "AUDIT_FAILED", E_NEURAL),
    ]
    for yc, name, ec in verdicts:
        box(ax, vx, yc, 2.35, 0.95, name, fc="white", ec=ec, fs=9.5, bold=True, text_color=ec)
    # Straight horizontal arrow from the locus band into BLOCK, label centred in the clear gap.
    arrow(ax, (9.7, 3.42), (vx, 3.42), color=INK, lw=1.3)
    ax.text((9.7 + vx) / 2, 3.66, "ReliableGuard μ", ha="center", fontsize=8.5, style="italic",
            color=MUTE)

    fig.savefig(os.path.join(OUT_DIR, "figure1_concept_overview.png"), dpi=200, bbox_inches="tight")
    plt.close(fig)


# --------------------------------------------------------------------------------------------------
# Figure 2 — Observability boundary as a concentric reach diagram.
# --------------------------------------------------------------------------------------------------
def figure2():
    fig, ax = plt.subplots(figsize=(9.4, 6.6))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 9)
    ax.axis("off")
    cx, cy = 4.6, 4.2

    # Ellipses sized so each text label sits in a clear band, never on an arc. The answer-local
    # core is kept small to widen the blue band that holds the (long) trace+state label.
    rings = [
        (8.6, 6.9, F_NEUT, E_NEUT, "-", "intent-local", cy + 3.05),
        (6.7, 5.3, "#f3f3f3", E_NEUT, (0, (5, 3)), "evidence-local", cy + 2.25),
        (4.9, 3.9, F_AGENT, E_AGENT, "-", "trace-local + state-local", cy + 1.15),
        (2.2, 1.55, F_ANSWER, E_ANSWER, "-", "answer-local", cy + 0.0),
    ]
    for w, h, fc, ec, ls, _, _ in rings:
        ax.add_patch(Ellipse((cx, cy), w, h, facecolor=fc, edgecolor=ec, linewidth=1.4,
                             linestyle=ls, zorder=1))
    # Ring labels, shrunk proportionally so the longest one clears the blue arc.
    label_fs = [11, 9.5, 9.5, 10]
    label_col = [MUTE, MUTE, E_AGENT, E_ANSWER]
    for (w, h, fc, ec, ls, name, ly), fs, col in zip(rings, label_fs, label_col):
        ax.text(cx, ly, name, ha="center", fontsize=fs, fontweight="bold", color=col, zorder=5)

    ax.text(cx, 8.05, "All reward-0 failures", ha="center", fontsize=12, fontweight="bold")

    # Side legend (kept entirely outside the rings so no text crosses a line).
    lx = 9.5
    band(ax, lx - 0.3, 1.4, 2.7, 4.0, fc=BAND, ec="#d8dde3", lw=1.0)
    ax.text(lx + 1.05, 5.05, "Monitor reach", ha="center", fontsize=10.5, fontweight="bold")
    legend = [
        (4.55, F_ANSWER, E_ANSWER, "V_answer:", "answer-local core"),
        (3.55, F_AGENT, E_AGENT, "V_structural:", "+ trace + state"),
        (2.45, F_NEUT, E_NEUT, "unreachable:", "evidence / intent"),
    ]
    for yy, fc, ec, head, body in legend:
        ax.add_patch(FancyBboxPatch((lx, yy), 0.34, 0.34, boxstyle="round,pad=0.01,rounding_size=0.08",
                                    facecolor=fc, edgecolor=ec, linewidth=1.1, zorder=4))
        ax.text(lx + 0.5, yy + 0.32, head, ha="left", va="center", fontsize=9.2, fontweight="bold")
        ax.text(lx + 0.5, yy + 0.02, body, ha="left", va="center", fontsize=8.6, color=MUTE)
    ax.text(lx + 1.05, 1.62, "dashed = not\nimplemented here", ha="center", fontsize=7.6,
            style="italic", color=MUTE)

    fig.savefig(os.path.join(OUT_DIR, "figure2_observability_boundary.png"), dpi=200,
                bbox_inches="tight")
    plt.close(fig)


# --------------------------------------------------------------------------------------------------
# Figure 3 — End-to-end six-stage pipeline.
# --------------------------------------------------------------------------------------------------
def figure3():
    fig, ax = plt.subplots(figsize=(17.2, 5.4))
    ax.set_xlim(0, 17.2)
    ax.set_ylim(0, 5.4)
    ax.axis("off")

    yb, h, w, gap, x0 = 3.05, 1.05, 1.55, 0.62, 2.05
    box(ax, 0.15, yb, 1.3, h, "Trajectory\nrecord T", fc=F_NEUT, ec=E_NEUT, bold=True, fs=9.5)

    stages = [
        ("Extract\nClaims", F_NEURAL, E_NEURAL),
        ("Classify\nVerifiability", F_AGENT, E_AGENT),
        ("Verify\nClaims", F_AGENT, E_AGENT),
        ("Score\nRisks", F_AGENT, E_AGENT),
        ("Decide\nInterventions", F_AGENT, E_AGENT),
        ("Generate\nReport", F_AGENT, E_AGENT),
    ]
    lefts = [x0 + i * (w + gap) for i in range(6)]
    # Symbolic grouping band behind stages 2-6.
    band(ax, lefts[1] - 0.12, yb - 0.28, (lefts[5] + w) - (lefts[1] - 0.12) + 0.12, h + 0.56,
         fc=BAND, ec="#cdd6e0", lw=1.0)
    for i, (label, fc, ec) in enumerate(stages):
        box(ax, lefts[i], yb, w, h, label, fc=fc, ec=ec, bold=True, fs=9.5)
        step_num(ax, lefts[i] + 0.22, yb + h - 0.16, i + 1, color=ec)
    xout = lefts[5] + w + gap
    box(ax, xout, yb, 1.75, h, "Reliability\nReport\n+ trace JSON", fc=F_ANSWER, ec=E_ANSWER,
        bold=True, fs=8.8)

    arrow(ax, (1.45, yb + h / 2), (x0, yb + h / 2), lw=1.4)
    for i in range(5):
        arrow(ax, (lefts[i] + w, yb + h / 2), (lefts[i + 1], yb + h / 2), lw=1.4)
    arrow(ax, (lefts[5] + w, yb + h / 2), (xout, yb + h / 2), lw=1.4)

    # Phase brackets above.
    by = yb + h + 0.5
    ax.annotate("", xy=(lefts[0], by), xytext=(lefts[0] + w, by),
                arrowprops=dict(arrowstyle="-", color=E_NEURAL, lw=2.2))
    ax.text(lefts[0] + w / 2, by + 0.2, "one neural call", ha="center", fontsize=9.5,
            color=E_NEURAL, fontweight="bold")
    ax.annotate("", xy=(lefts[1], by), xytext=(lefts[5] + w, by),
                arrowprops=dict(arrowstyle="-", color=E_AGENT, lw=2.2))
    ax.text((lefts[1] + lefts[5] + w) / 2, by + 0.2, "deterministic symbolic (stages 2-6)",
            ha="center", fontsize=9.5, color=E_AGENT, fontweight="bold")

    # Channel branch under stage 3 (Verify Claims).
    s3 = lefts[2] + w / 2
    box(ax, s3 - 2.85, 0.5, 2.55, 1.0, "V_answer", fc="white", ec=E_ANSWER, fs=9.5, bold=True,
        text_color=E_ANSWER, sub="answer channel only", sub_fs=8)
    box(ax, s3 + 0.3, 0.5, 2.75, 1.0, "V_structural", fc="white", ec=E_AGENT, fs=9.5, bold=True,
        text_color=E_AGENT, sub="+ trace + state channels", sub_fs=8)
    arrow(ax, (s3, yb), (s3 - 1.55, 1.5), color=E_ANSWER, lw=1.4, rad=0.18)
    arrow(ax, (s3, yb), (s3 + 1.65, 1.5), color=E_AGENT, lw=1.4, rad=-0.18)
    ax.text(s3, 0.22, "channel set gates which artifacts the verifier reads — no re-extraction",
            ha="center", fontsize=8.4, style="italic", color=MUTE)

    fig.savefig(os.path.join(OUT_DIR, "figure3_pipeline.png"), dpi=200, bbox_inches="tight")
    plt.close(fig)


# --------------------------------------------------------------------------------------------------
# Figure 4 — Non-circularity: disjoint monitor and oracle inputs.
# --------------------------------------------------------------------------------------------------
def figure4():
    fig, ax = plt.subplots(figsize=(11, 5.6))
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 5.6)
    ax.axis("off")

    # Left panel: monitor.
    band(ax, 0.3, 0.5, 4.5, 4.5, fc=F_AGENT, ec=E_AGENT, lw=1.4)
    ax.text(2.55, 4.62, "Monitor  μ  reads", ha="center", fontsize=12, fontweight="bold",
            color=E_AGENT)
    for i, t in enumerate(["answer_text", "env.actions  (tool trace)", "env.data  (state Δ)"]):
        tag(ax, 0.75, 3.5 - i * 0.78, 3.6, 0.52, t, fc="white", ec=E_AGENT, fs=9.5)
    box(ax, 0.6, 0.72, 3.9, 0.66, "verdict ∈ {PASS, WARN, BLOCK}", fc=F_AGENT, ec=E_AGENT,
        fs=9, bold=True)
    arrow(ax, (2.55, 1.72), (2.55, 1.38), color=E_AGENT, lw=1.3)

    # Right panel: oracle.
    band(ax, 6.2, 0.5, 4.5, 4.5, fc=F_USER, ec=E_USER, lw=1.4)
    ax.text(8.45, 4.62, "Oracle reads", ha="center", fontsize=12, fontweight="bold", color=E_USER)
    tag(ax, 6.65, 3.15, 3.6, 0.6, "r_actions (gold goal annotation)", fc="white", ec=E_USER, fs=9.2)
    tag(ax, 6.65, 2.05, 3.6, 0.55, "calculate_reward()", fc="white", ec=E_USER, fs=9.2)
    box(ax, 7.55, 0.72, 1.8, 0.62, "gold reward y", fc=F_USER, ec=E_USER, fs=9.5, bold=True)
    arrow(ax, (8.45, 3.15), (8.45, 2.6), color=E_USER, lw=1.3)
    arrow(ax, (8.45, 2.05), (8.45, 1.34), color=E_USER, lw=1.3)

    # Divider.
    ax.plot([5.5, 5.5], [0.4, 4.85], color=INK, linewidth=2.6, zorder=5)
    ax.text(5.5, 5.18, "disjoint inputs", ha="center", fontsize=11, fontweight="bold")
    ax.text(5.5, 0.16, "non-circular by construction — no arrow crosses the divider", ha="center",
            fontsize=8.8, style="italic", color=MUTE)

    fig.savefig(os.path.join(OUT_DIR, "figure4_non_circularity.png"), dpi=200, bbox_inches="tight")
    plt.close(fig)


# --------------------------------------------------------------------------------------------------
# Figure 5 — Three statistical claims, each at its correct unit of analysis.
# --------------------------------------------------------------------------------------------------
def figure5():
    """Why the design keeps three claims at three different units of analysis.

    Each card states the method, the unit (with concrete N), and -- crucially -- the question it
    answers, so the reader sees why mixing the units would be a fallacy (e.g. claiming significance
    at N=4 models, or treating K repeats as independent evidence of an effect).
    """
    fig, ax = plt.subplots(figsize=(12.2, 6.4))
    ax.set_xlim(0, 12.2)
    ax.set_ylim(0, 6.4)
    ax.axis("off")

    ax.text(6.1, 6.15, "One captured matrix, three statistical claims at three units",
            ha="center", fontsize=12.5, fontweight="bold")

    cards = [
        ("Significance", "Per-task paired\nMcNemar test", "V_answer vs V_structural,\nsame task",
         "unit: task   (N ≈ 164 / model)", "Is the detection lift real,\nor run-to-run noise?",
         F_AGENT, E_AGENT, "paired"),
        ("Generality", "ΔRDR across the\n4 audited vendors", "deepseek · mimo ·\nglm · qwen",
         "unit: model   (N = 4)", "Does the lift hold across\nmodel families?  (not a\nsignificance claim at N=4)",
         F_ANSWER, E_ANSWER, "bars"),
        ("Noise", "Std across K = 10\nunseeded repeats", "same (task, model),\nrepeated",
         "unit: repeat   (K = 10)", "How stable is the rate\nunder LLM non-determinism?",
         F_USER, E_USER, "spread"),
    ]
    cw, gap, x0, ytop, ch = 3.66, 0.26, 0.5, 4.85, 3.55
    for i, (title, method, scope, unit, question, fc, ec, icon) in enumerate(cards):
        x = x0 + i * (cw + gap)
        band(ax, x, ytop - ch, cw, ch, fc=BAND, ec=ec, lw=1.5)
        # Header strip.
        ax.add_patch(FancyBboxPatch((x, ytop - 0.62), cw, 0.62,
                     boxstyle="round,pad=0,rounding_size=0.06", facecolor=ec, edgecolor="none",
                     zorder=3))
        ax.text(x + cw / 2, ytop - 0.31, title, ha="center", va="center", fontsize=13,
                fontweight="bold", color="white", zorder=5)
        ax.text(x + cw / 2, ytop - 1.05, method, ha="center", va="center", fontsize=10.5,
                fontweight="bold", color=INK, zorder=5)
        ax.text(x + cw / 2, ytop - 1.72, scope, ha="center", va="center", fontsize=9,
                color=MUTE, style="italic", zorder=5)
        # Unit pill.
        ax.add_patch(FancyBboxPatch((x + 0.35, ytop - 2.32), cw - 0.7, 0.42,
                     boxstyle="round,pad=0.02,rounding_size=0.12", facecolor=ec, alpha=0.9,
                     edgecolor="none", zorder=3))
        ax.text(x + cw / 2, ytop - 2.11, unit, ha="center", va="center", fontsize=9.3,
                color="white", fontweight="bold", zorder=5)
        # Question answered.
        ax.text(x + cw / 2, ytop - 2.95, "Answers:", ha="center", fontsize=8.5,
                fontweight="bold", color=ec)
        ax.text(x + cw / 2, ytop - 3.32, question, ha="center", va="center", fontsize=8.6,
                color=INK, zorder=5)

        # Small concrete icon under the card.
        iy = ytop - ch - 0.7
        cxm = x + cw / 2
        if icon == "paired":
            for dx in (-0.9, -0.3, 0.3, 0.9):
                ax.plot([cxm + dx, cxm + dx], [iy - 0.32, iy + 0.32], color="#cfd6de", lw=1.1)
                ax.plot(cxm + dx, iy + 0.18, "s", color=E_AGENT, ms=7)
                ax.plot(cxm + dx, iy - 0.18, "o", color=F_AGENT, mec=E_AGENT, mew=1.1, ms=8)
        elif icon == "bars":
            for j, dx in enumerate((-0.9, -0.3, 0.3, 0.9)):
                hh = 0.32 + 0.1 * j
                ax.add_patch(FancyBboxPatch((cxm + dx - 0.13, iy - hh / 2), 0.26, hh,
                             boxstyle="square,pad=0", facecolor=fc, edgecolor=ec, linewidth=1.1))
                ax.plot([cxm + dx - 0.13, cxm + dx + 0.13], [iy, iy], color=ec, lw=1.8)
        else:
            xs = [cxm - 1.0 + 0.2 * k for k in range(11)]
            ys = [iy + 0.22 * (0.5 - ((k * 7) % 5) / 5.0) for k in range(11)]
            ax.plot(xs, ys, "-o", color=ec, mfc=fc, ms=4.5, lw=1.2)

    ax.text(6.1, 0.18, "Each unit = one (task, model, repeat) trajectory, audited by both "
            "V_answer and V_structural.", ha="center", fontsize=9, style="italic", color=MUTE)

    fig.savefig(os.path.join(OUT_DIR, "figure5_statistical_design.png"), dpi=200,
                bbox_inches="tight")
    plt.close(fig)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    figure1()
    figure2()
    figure3()
    figure4()
    figure5()
    print(f"wrote figure1..5 to {OUT_DIR}")


if __name__ == "__main__":
    main()
