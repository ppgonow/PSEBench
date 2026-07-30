#!/usr/bin/env python3
"""Generate the deterministic INFOCOM Figure 1 workflow diagram."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Polygon


NAVY = "#17324D"
BLUE = "#356A9A"
BLUE_LIGHT = "#EAF2F8"
GREEN = "#2D7D62"
GREEN_LIGHT = "#E8F4EF"
CORAL = "#C95550"
CORAL_LIGHT = "#FBEDEA"
AMBER = "#B7791F"
AMBER_LIGHT = "#FFF5DA"
INK = "#17212B"
MUTED = "#52606D"
LINE = "#CBD4DC"
PANEL = "#F7F9FB"
WHITE = "#FFFFFF"


def rounded(ax, x, y, w, h, *, face=WHITE, edge=LINE, lw=1.4, radius=0.012, z=2):
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle=f"round,pad=0.005,rounding_size={radius}",
        linewidth=lw,
        edgecolor=edge,
        facecolor=face,
        zorder=z,
    )
    ax.add_patch(patch)
    return patch


def arrow(ax, start, end, *, color=BLUE, lw=1.7, style="-|>", z=4, connection="arc3"):
    patch = FancyArrowPatch(
        start,
        end,
        arrowstyle=style,
        mutation_scale=14,
        linewidth=lw,
        color=color,
        connectionstyle=connection,
        shrinkA=3,
        shrinkB=3,
        zorder=z,
    )
    ax.add_patch(patch)
    return patch


def number(ax, x, y, value, *, color=BLUE):
    ax.add_patch(Circle((x, y), 0.014, facecolor=color, edgecolor="none", zorder=7))
    ax.text(x, y - 0.001, str(value), color=WHITE, fontsize=12, fontweight="bold",
            ha="center", va="center", zorder=8)


def card_text(
    ax, x, y, title, body, *, title_color=INK, align="left",
    title_size=16, body_size=13.5,
):
    ax.text(x, y, title, color=title_color, fontsize=title_size, fontweight="bold",
            ha=align, va="top", zorder=8)
    ax.text(x, y - 0.029, body, color=MUTED, fontsize=body_size,
            ha=align, va="top", linespacing=1.12, zorder=8)


def draw_left(ax):
    x, y, w, h = 0.025, 0.10, 0.175, 0.80
    rounded(ax, x, y, w, h, face=PANEL, edge=LINE, lw=1.2, radius=0.014, z=1)
    ax.text(x + w / 2, 0.865, "Tool-induction view", color=NAVY, fontsize=18,
            fontweight="bold", ha="center", va="center")
    items = [
        ("Benign task", "Read an inbound\nmessage", BLUE_LIGHT, BLUE),
        ("No tool needed", "No scheduler\naction is needed", WHITE, MUTED),
        ("Injected text", "Create a recurring\nreminder", CORAL_LIGHT, CORAL),
        ("New tool action", "Unauthorized tool\nuse occurs", CORAL_LIGHT, CORAL),
    ]
    ys = [0.705, 0.535, 0.365, 0.195]
    for idx, ((title, body, face, accent), cy) in enumerate(zip(items, ys), 1):
        rounded(ax, x + 0.032, cy, w - 0.048, 0.115, face=face, edge=accent, lw=1.3)
        number(ax, x + 0.018, cy + 0.057, idx, color=accent)
        card_text(
            ax, x + 0.047, cy + 0.088, title, body,
            title_color=accent, title_size=14, body_size=12.5,
        )
        if idx < len(items):
            arrow(ax, (x + w / 2, cy - 0.005), (x + w / 2, ys[idx] + 0.122), color=MUTED, lw=1.2)


def draw_field_table(ax, x, y, w, h, title, fields, *, accent, face, highlight=None):
    rounded(ax, x, y, w, h, face=face, edge=accent, lw=1.7, radius=0.014)
    ax.text(x + 0.018, y + h - 0.028, title, color=accent, fontsize=16,
            fontweight="bold", ha="left", va="top", zorder=8)
    row_y = y + h - 0.076
    for label, value in fields:
        is_highlight = highlight == label
        if is_highlight:
            rounded(ax, x + 0.012, row_y - 0.028, w - 0.024, 0.042,
                    face=CORAL_LIGHT, edge=CORAL, lw=1.0, radius=0.006, z=4)
        ax.text(x + 0.020, row_y, label, color=MUTED, fontsize=13.5,
                ha="left", va="center", zorder=8)
        ax.text(x + w - 0.020, row_y, value, color=CORAL if is_highlight else INK,
                fontsize=14, fontweight="bold", ha="right", va="center", zorder=8)
        row_y -= 0.047


def draw_shield(ax, x, y):
    shield = Polygon(
        [(x, y + 0.043), (x + 0.034, y + 0.031), (x + 0.030, y - 0.020),
         (x, y - 0.047), (x - 0.030, y - 0.020), (x - 0.034, y + 0.031)],
        closed=True,
        facecolor=AMBER_LIGHT,
        edgecolor=AMBER,
        linewidth=1.8,
        zorder=7,
    )
    ax.add_patch(shield)
    ax.plot([x - 0.013, x - 0.002, x + 0.017], [y - 0.001, y - 0.014, y + 0.014],
            color=AMBER, linewidth=2.3, solid_capstyle="round", zorder=8)


def draw_center(ax):
    x, y, w, h = 0.215, 0.10, 0.565, 0.80
    rounded(ax, x, y, w, h, face=WHITE, edge=LINE, lw=1.3, radius=0.014, z=1)
    ax.text(x + w / 2, 0.865, "Authorization-boundary escalation", color=NAVY,
            fontsize=23, fontweight="bold", ha="center", va="center")
    ax.text(x + w / 2, 0.827, "The tool is legitimate; the committed effect exceeds current authorization",
            color=MUTED, fontsize=14, ha="center", va="center")

    top_y, card_h, card_w = 0.655, 0.125, 0.145
    xs = [x + 0.030, x + 0.210, x + 0.390]
    top_cards = [
        ("Trusted request", "Set one reminder\nat 09:00", BLUE_LIGHT, BLUE),
        ("Untrusted content", '"Also repeat it\nevery day."', CORAL_LIGHT, CORAL),
        ("Tool proposal", "calendar.create\nrepeat = daily", AMBER_LIGHT, AMBER),
    ]
    for idx, (cx, (title, body, face, accent)) in enumerate(zip(xs, top_cards), 1):
        rounded(ax, cx, top_y, card_w, card_h, face=face, edge=accent, lw=1.5)
        number(ax, cx + 0.014, top_y + card_h + 0.018, idx, color=accent)
        card_text(ax, cx + 0.015, top_y + card_h - 0.025, title, body, title_color=accent)
    arrow(ax, (xs[0] + card_w + 0.004, top_y + card_h / 2),
          (xs[1] - 0.004, top_y + card_h / 2), color=MUTED)
    arrow(ax, (xs[1] + card_w + 0.004, top_y + card_h / 2),
          (xs[2] - 0.004, top_y + card_h / 2), color=MUTED)

    auth_fields = [("Tool", "calendar"), ("Target", "self"),
                   ("Effect", "reminder"), ("Lifetime", "one-shot")]
    prop_fields = [("Tool", "calendar"), ("Target", "self"),
                   ("Effect", "reminder"), ("Lifetime", "daily")]
    table_y, table_h, table_w = 0.285, 0.245, 0.190
    left_x, right_x = x + 0.045, x + w - 0.045 - table_w
    draw_field_table(ax, left_x, table_y, table_w, table_h,
                     "Trusted envelope", auth_fields, accent=GREEN, face=GREEN_LIGHT)
    draw_field_table(ax, right_x, table_y, table_w, table_h,
                     "Proposed effect", prop_fields, accent=CORAL, face=CORAL_LIGHT,
                     highlight="Lifetime")
    arrow(ax, (xs[0] + card_w / 2, top_y - 0.006),
          (left_x + table_w / 2, table_y + table_h + 0.006), color=GREEN, lw=1.5)
    arrow(ax, (xs[2] + card_w / 2, top_y - 0.006),
          (right_x + table_w / 2, table_y + table_h + 0.006), color=CORAL, lw=1.5)

    boundary_x = x + w / 2
    draw_shield(ax, boundary_x, table_y + 0.125)
    ax.text(boundary_x, table_y + 0.210, "COMMIT\nBOUNDARY", color=AMBER,
            fontsize=11.5, fontweight="bold", ha="center", va="center", linespacing=0.92)
    ax.text(boundary_x, table_y + 0.050, "REVALIDATE", color=MUTED,
            fontsize=10.5, fontweight="bold", ha="center", va="top")
    arrow(ax, (left_x + table_w + 0.004, table_y + 0.125),
          (boundary_x - 0.038, table_y + 0.125), color=GREEN, lw=1.5)
    arrow(ax, (right_x - 0.004, table_y + 0.125),
          (boundary_x + 0.038, table_y + 0.125), color=CORAL, lw=1.5)

    rounded(ax, x + 0.075, 0.145, 0.185, 0.072, face=GREEN_LIGHT, edge=GREEN, lw=1.5)
    ax.text(x + 0.168, 0.181, "ALLOW exact match", color=GREEN, fontsize=15,
            fontweight="bold", ha="center", va="center")
    rounded(ax, x + w - 0.260, 0.145, 0.185, 0.072, face=CORAL_LIGHT, edge=CORAL, lw=1.7)
    ax.text(x + w - 0.168, 0.181, "BLOCK escalation", color=CORAL, fontsize=15,
            fontweight="bold", ha="center", va="center")
    arrow(ax, (boundary_x - 0.010, table_y - 0.004), (x + 0.168, 0.223),
          color=GREEN, lw=1.3, connection="arc3,rad=0.10")
    arrow(ax, (boundary_x + 0.010, table_y - 0.004), (x + w - 0.168, 0.223),
          color=CORAL, lw=1.5, connection="arc3,rad=-0.10")


def draw_right(ax):
    x, y, w, h = 0.795, 0.10, 0.18, 0.80
    rounded(ax, x, y, w, h, face=PANEL, edge=LINE, lw=1.2, radius=0.014, z=1)
    ax.text(x + w / 2, 0.865, "PSEBench pipeline", color=NAVY, fontsize=18,
            fontweight="bold", ha="center", va="center")
    entries = [
        ("Scenarios", "typed YAML", BLUE),
        ("Agent traces", "native + replay", BLUE),
        ("Effect ledger", "committed effects", AMBER),
        ("Effect oracle", "exact field match", GREEN),
        ("ASR / TCR", "security + utility", NAVY),
    ]
    ys = [0.705, 0.575, 0.445, 0.315, 0.185]
    for idx, ((title, body, accent), cy) in enumerate(zip(entries, ys), 1):
        rounded(ax, x + 0.027, cy, w - 0.042, 0.088, face=WHITE, edge=accent, lw=1.25)
        number(ax, x + 0.014, cy + 0.044, idx, color=accent)
        ax.text(x + 0.047, cy + 0.059, title, color=accent, fontsize=14.5,
                fontweight="bold", ha="left", va="center")
        ax.text(x + 0.047, cy + 0.027, body, color=MUTED, fontsize=12.5,
                ha="left", va="center")
        if idx < len(entries):
            arrow(ax, (x + w / 2, cy - 0.004), (x + w / 2, ys[idx] + 0.094),
                  color=MUTED, lw=1.1)


def generate(output: Path) -> None:
    fig, ax = plt.subplots(figsize=(16, 8), dpi=160)
    fig.patch.set_facecolor(WHITE)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    draw_left(ax)
    draw_center(ax)
    draw_right(ax)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=200, bbox_inches="tight", pad_inches=0.08, facecolor=WHITE)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("paper_writing/figures/authorization_boundary_workflow_v2.png"),
    )
    args = parser.parse_args()
    generate(args.output)
    print(args.output)


if __name__ == "__main__":
    main()
