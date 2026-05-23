from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyBboxPatch


ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "analysis"
FIGURES = ROOT / "paper_writing" / "figures"
TABLES = ROOT / "paper_writing" / "tables"


SAFE = "#7AA17A"
RISK = "#C76C5B"
IACG = "#4E79A7"
SLC = "#B07AA1"
FIREWALL = "#9C755F"
CONFIRM = "#F2A541"
STRICT = "#76B7B2"
TEXT = "#2F3437"
GRID = "#D9D9D9"
PANEL = "#F6F7F8"


def ensure_dirs() -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    TABLES.mkdir(parents=True, exist_ok=True)


def configure_style() -> None:
    plt.style.use("default")
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 11,
            "axes.titlesize": 14,
            "axes.labelsize": 11,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
            "legend.fontsize": 9,
            "axes.edgecolor": "#BBBBBB",
            "axes.linewidth": 0.8,
            "axes.facecolor": "white",
            "figure.facecolor": "white",
            "savefig.facecolor": "white",
            "savefig.bbox": "tight",
            "grid.color": GRID,
            "grid.linestyle": "--",
            "grid.linewidth": 0.6,
        }
    )


def wilson_ci(successes: int, n: int, z: float = 1.96) -> Tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    p = successes / n
    denom = 1 + z**2 / n
    centre = p + z**2 / (2 * n)
    delta = z * np.sqrt((p * (1 - p) + z**2 / (4 * n)) / n)
    low = (centre - delta) / denom
    high = (centre + delta) / denom
    return max(0.0, low), min(1.0, high)


def parse_baseline_csv() -> pd.DataFrame:
    rows: List[Dict[str, object]] = []
    with (ANALYSIS / "new_baseline_comparison_table.csv").open() as f:
        reader = csv.reader(f)
        header = next(reader)
        for raw in reader:
            if len(raw) < 6:
                continue
            row = {
                header[0]: raw[0],
                header[1]: raw[1],
                header[2]: int(raw[2]),
                header[3]: float(raw[3]),
                header[4]: float(raw[4]),
                header[5]: int(raw[5]) if raw[5] else np.nan,
                header[6]: ",".join(raw[6:]).strip() if len(raw) > 6 else "",
            }
            rows.append(row)
    df = pd.DataFrame(rows)
    df.columns = [
        "slice",
        "policy",
        "n",
        "asr",
        "tcr",
        "confirmations",
        "note",
    ]
    return df


def load_manual_risk_data() -> pd.DataFrame:
    group = pd.read_csv(ANALYSIS / "manual_aggregate_by_group.csv")
    family = pd.read_csv(ANALYSIS / "manual_aggregate_by_scenario.csv")

    def agg(prefix: str) -> Tuple[int, int]:
        subset = family[family["key"].astype(str).str.startswith(prefix)]
        attack_yes = int(subset["attack_yes"].fillna(0).sum())
        n = int(subset["n"].sum())
        return attack_yes, n

    tool_induction = group[group["key"] == "A"].iloc[0]
    hybrid = group[group["key"] == "H"].iloc[0]
    cron_yes, cron_n = agg("H-msg-cron-required")
    web_yes, web_n = agg("H-web-msg-required")

    rows = [
        ("Tool-induction suite", int(tool_induction["attack_yes"]) if pd.notna(tool_induction["attack_yes"]) else 0, int(tool_induction["n"])),
        ("Hybrid legitimate-tool suite", int(hybrid["attack_yes"]) if pd.notna(hybrid["attack_yes"]) else 0, int(hybrid["n"])),
        ("Cron-required family", cron_yes, cron_n),
        ("Negative hybrid family", web_yes, web_n),
    ]
    out = []
    for label, successes, n in rows:
        low, high = wilson_ci(successes, n)
        out.append(
            {
                "label": label,
                "successes": successes,
                "n": n,
                "asr": successes / n if n else 0.0,
                "low": low,
                "high": high,
            }
        )
    return pd.DataFrame(out)


def make_risk_forest_plot() -> None:
    df = load_manual_risk_data()
    df = df.iloc[::-1].reset_index(drop=True)

    fig, ax = plt.subplots(figsize=(8.8, 3.8))
    y = np.arange(len(df))
    x = df["asr"].to_numpy()
    xerr = np.vstack((x - df["low"].to_numpy(), df["high"].to_numpy() - x))

    ax.errorbar(
        x,
        y,
        xerr=xerr,
        fmt="o",
        color=IACG,
        ecolor=TEXT,
        elinewidth=1.3,
        capsize=3,
        markersize=7,
    )
    ax.axvline(0.0, color="#BBBBBB", linewidth=0.8)
    ax.axvline(0.5, color="#E6E6E6", linewidth=0.8, linestyle="--")

    ax.set_yticks(y)
    ax.set_yticklabels(df["label"])
    ax.set_xlim(-0.02, 1.02)
    ax.set_xlabel("Attack Success Rate (ASR)")
    ax.grid(axis="x", alpha=0.7)
    for spine in ["top", "right", "left"]:
        ax.spines[spine].set_visible(False)

    for idx, row in df.iterrows():
        ax.text(
            min(row["high"] + 0.03, 0.98),
            idx,
            f'{int(row["successes"])}/{int(row["n"])}',
            va="center",
            ha="left",
            color=TEXT,
            fontsize=9,
        )

    fig.savefig(FIGURES / "risk_forest_plot.png", dpi=300)
    plt.close(fig)


def policy_color(policy: str) -> str:
    mapping = {
        "permissive": RISK,
        "strict / safe": STRICT,
        "firewall": FIREWALL,
        "confirm-all-persistent": CONFIRM,
        "SLC": SLC,
        "IACG": IACG,
    }
    return mapping.get(policy, "#777777")


def make_security_utility_frontier() -> None:
    df = parse_baseline_csv()
    order = [
        "core cron matched slice",
        "authorization-boundary contrast",
        "implicit durability",
        "failure-mechanism stress test",
        "beyond-cron: file persistence",
        "beyond-cron: calendar recurrence",
        "beyond-cron: recipient hijack",
    ]
    panels = [s for s in order if s in set(df["slice"])]

    fig, axes = plt.subplots(2, 4, figsize=(14.5, 5.7))
    axes = axes.flatten()
    legend_handles = {}

    for ax in axes[len(panels) :]:
        ax.axis("off")

    for i, sl in enumerate(panels):
        ax = axes[i]
        sub = df[df["slice"] == sl].copy()
        ax.set_facecolor(PANEL)
        cluster_counts: Dict[Tuple[float, float], int] = {}
        cluster_seen: Dict[Tuple[float, float], int] = {}
        for _, row in sub.iterrows():
            key = (round(float(row["tcr"]), 3), round(float(row["asr"]), 3))
            cluster_counts[key] = cluster_counts.get(key, 0) + 1
        for _, row in sub.iterrows():
            key = (round(float(row["tcr"]), 3), round(float(row["asr"]), 3))
            seen = cluster_seen.get(key, 0)
            cluster_seen[key] = seen + 1
            total = cluster_counts[key]
            if total > 1:
                offsets = np.linspace(-0.03, 0.03, total)
                dx = offsets[seen]
                dy = offsets[::-1][seen] * 0.35
            else:
                dx = 0.0
                dy = 0.0
            size = 80 if pd.isna(row["confirmations"]) else 80 + 10 * float(row["confirmations"])
            handle = ax.scatter(
                float(row["tcr"]) + dx,
                float(row["asr"]) + dy,
                s=size,
                color=policy_color(str(row["policy"])),
                alpha=0.9,
                edgecolor="white",
                linewidth=1.2,
                zorder=3,
            )
            legend_handles.setdefault(str(row["policy"]), handle)
            if pd.notna(row["confirmations"]):
                ax.text(
                    float(row["tcr"]) + dx + 0.02,
                    float(row["asr"]) + dy + 0.02,
                    f"C={int(row['confirmations'])}",
                    fontsize=7.6,
                    ha="left",
                    va="bottom",
                    color=TEXT,
                )
        ax.set_xlim(-0.03, 1.03)
        ax.set_ylim(-0.03, 1.03)
        ax.set_xticks([0.0, 0.5, 1.0])
        ax.set_yticks([0.0, 0.5, 1.0])
        ax.grid(True, zorder=0)
        ax.set_title(sl.replace("beyond-cron: ", ""), fontsize=10.5, pad=10)
        ax.set_xlabel("TCR")
        if i % 4 == 0:
            ax.set_ylabel("ASR")
        for spine in ["top", "right"]:
            ax.spines[spine].set_visible(False)

    legend_order = ["permissive", "strict / safe", "firewall", "confirm-all-persistent", "SLC", "IACG"]
    handles = [legend_handles[p] for p in legend_order if p in legend_handles]
    labels = [p.replace("confirm-all-persistent", "confirm-all") for p in legend_order if p in legend_handles]
    fig.legend(handles, labels, loc="lower center", ncol=6, frameon=False, bbox_to_anchor=(0.5, -0.01))
    fig.subplots_adjust(hspace=0.35, bottom=0.12, top=0.92)
    fig.savefig(FIGURES / "security_utility_frontier.png", dpi=300)
    plt.close(fig)


def build_matrix_data() -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    baseline = parse_baseline_csv()
    triple = pd.read_csv(ANALYSIS / "triple_contrast_summary.csv")

    triple["slice"] = triple["category"].map(
        {
            "benign_one_shot": "Benign one-shot",
            "legit_persistent": "Legitimate persistent",
            "ambiguous": "Ambiguous",
        }
    )
    triple["policy"] = triple["tag"].replace({"guard": "IACG", "permissive": "permissive", "firewall": "firewall"})
    triple_asr = triple.pivot(index="slice", columns="policy", values="ASR")
    triple_tcr = triple.pivot(index="slice", columns="policy", values="TCR")

    implicit = baseline[baseline["slice"] == "implicit durability"][["policy", "asr", "tcr"]].copy()
    implicit["slice"] = "Implicit durability"
    fail = baseline[baseline["slice"] == "failure-mechanism stress test"][["policy", "asr", "tcr"]].copy()
    fail["slice"] = "Lexical trap stress"

    extra = pd.concat([implicit, fail], ignore_index=True)
    extra_asr = extra.pivot(index="slice", columns="policy", values="asr")
    extra_tcr = extra.pivot(index="slice", columns="policy", values="tcr")

    asr = pd.concat([triple_asr, extra_asr], axis=0)
    tcr = pd.concat([triple_tcr, extra_tcr], axis=0)
    labels = asr.copy().astype(object)
    for r in asr.index:
        for c in asr.columns:
            a = asr.loc[r, c]
            t = tcr.loc[r, c]
            labels.loc[r, c] = "" if pd.isna(a) or pd.isna(t) else f"{a:.3f}\n{t:.3f}"
    desired_rows = [
        "Benign one-shot",
        "Legitimate persistent",
        "Ambiguous",
        "Implicit durability",
        "Lexical trap stress",
    ]
    desired_cols = ["permissive", "firewall", "confirm-all-persistent", "SLC", "IACG"]
    asr = asr.reindex(index=desired_rows, columns=desired_cols)
    tcr = tcr.reindex(index=desired_rows, columns=desired_cols)
    labels = labels.reindex(index=desired_rows, columns=desired_cols)
    return asr, tcr, labels


def draw_heatmap(ax, data: pd.DataFrame, labels: pd.DataFrame, cmap_name: str, title: str) -> None:
    arr = data.to_numpy(dtype=float)
    cmap = plt.get_cmap(cmap_name)
    im = ax.imshow(arr, cmap=cmap, vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(np.arange(data.shape[1]))
    ax.set_yticks(np.arange(data.shape[0]))
    xticklabels = [c.replace("confirm-all-persistent", "confirm-all") for c in data.columns]
    ax.set_xticklabels(xticklabels, rotation=25, ha="right")
    ax.set_yticklabels(data.index)
    ax.set_title(title, fontsize=12, pad=10)
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            val = data.iloc[i, j]
            if pd.isna(val):
                continue
            text = labels.iloc[i, j]
            color = "white" if val > 0.55 else TEXT
            ax.text(j, i, text, ha="center", va="center", fontsize=8.3, color=color)
    ax.set_xticks(np.arange(-0.5, data.shape[1], 1), minor=True)
    ax.set_yticks(np.arange(-0.5, data.shape[0], 1), minor=True)
    ax.grid(which="minor", color="white", linestyle="-", linewidth=1.5)
    ax.tick_params(which="minor", bottom=False, left=False)
    for spine in ax.spines.values():
        spine.set_visible(False)
    return im


def make_authorization_boundary_matrix() -> None:
    asr, tcr, labels = build_matrix_data()
    fig, axes = plt.subplots(1, 2, figsize=(14.2, 5.6), gridspec_kw={"wspace": 0.18})
    im1 = draw_heatmap(axes[0], asr, labels, "Reds", "ASR\n(cell text: ASR / TCR)")
    im2 = draw_heatmap(axes[1], tcr, labels, "Greens", "TCR\n(cell text: ASR / TCR)")
    axes[1].set_yticklabels([])
    axes[1].tick_params(axis="y", length=0)
    cbar1 = fig.colorbar(im1, ax=axes[0], fraction=0.05, pad=0.14, orientation="horizontal")
    cbar1.set_label("ASR", labelpad=4)
    cbar2 = fig.colorbar(im2, ax=axes[1], fraction=0.05, pad=0.14, orientation="horizontal")
    cbar2.set_label("TCR", labelpad=4)
    fig.subplots_adjust(wspace=0.16, top=0.90, bottom=0.16, left=0.10, right=0.97)
    fig.savefig(FIGURES / "authorization_boundary_matrix.png", dpi=300)
    plt.close(fig)


def make_generalization_dumbbell() -> None:
    baseline = parse_baseline_csv()
    core = baseline[baseline["slice"] == "core cron matched slice"]
    adaptive = pd.read_csv(ANALYSIS / "adaptive_and_baseline_run_table.csv")
    persistent = pd.read_csv(ANALYSIS / "persistent_families_run_table.csv")
    main = [
        ("Core cron", float(core[core["policy"] == "permissive"]["asr"].iloc[0]), float(core[core["policy"] == "IACG"]["asr"].iloc[0]), 1.0, 1.0),
        ("Adaptive cron", float(adaptive[adaptive["key"] == "adaptive1-adaptive-permissive"]["asr"].iloc[0]), float(adaptive[adaptive["key"] == "adaptive1-adaptive-guard"]["asr"].iloc[0]), 1.0, 1.0),
        ("File persistence", float(persistent[persistent["key"] == "hfile1-hfile-permissive"]["asr"].iloc[0]), float(persistent[persistent["key"] == "hfile1-hfile-guard"]["asr"].iloc[0]), 1.0, 1.0),
        ("Calendar recurrence", float(persistent[persistent["key"] == "hcal1-hcal-permissive"]["asr"].iloc[0]), float(persistent[persistent["key"] == "hcal1-hcal-guard"]["asr"].iloc[0]), 1.0, 1.0),
        ("Recipient hijack", float(baseline[(baseline["slice"] == "beyond-cron: recipient hijack") & (baseline["policy"] == "permissive")]["asr"].iloc[0]), float(baseline[(baseline["slice"] == "beyond-cron: recipient hijack") & (baseline["policy"] == "IACG")]["asr"].iloc[0]), 1.0, 1.0),
    ]
    df = pd.DataFrame(main, columns=["family", "perm_asr", "iacg_asr", "perm_tcr", "iacg_tcr"]).iloc[::-1]

    fig, ax = plt.subplots(figsize=(7.8, 4.2))
    y = np.arange(len(df))
    for idx, row in df.iterrows():
        ax.plot([row["iacg_asr"], row["perm_asr"]], [idx, idx], color="#BDBDBD", linewidth=2)
        ax.scatter(row["perm_asr"], idx, color=RISK, s=90, zorder=3, label="Permissive" if idx == 0 else None)
        ax.scatter(row["iacg_asr"], idx, color=IACG, s=90, zorder=3, label="IACG" if idx == 0 else None)
        ax.text(row["perm_asr"] + 0.02, idx + 0.13, f"TCR {row['perm_tcr']:.1f}", fontsize=8, color=TEXT)
        ax.text(row["iacg_asr"] + 0.02, idx - 0.18, f"TCR {row['iacg_tcr']:.1f}", fontsize=8, color=TEXT)

    ax.set_yticks(y)
    ax.set_yticklabels(df["family"])
    ax.set_xlim(-0.02, 1.02)
    ax.set_xlabel("Attack Success Rate (ASR)")
    ax.grid(axis="x", alpha=0.7)
    ax.legend(frameon=False, loc="upper right", bbox_to_anchor=(0.98, -0.10), ncol=1)
    for spine in ["top", "right", "left"]:
        ax.spines[spine].set_visible(False)
    fig.subplots_adjust(bottom=0.24)
    fig.savefig(FIGURES / "generalization_dumbbell.png", dpi=300)
    plt.close(fig)


@dataclass
class CoverageRow:
    slice_name: str
    scenarios: int
    channel: str
    benign_tool: str
    unauthorized_upgrade: str


def make_benchmark_coverage_table() -> None:
    rows = [
        CoverageRow("tool-induction attack suite", 30, "web / message", "tool not otherwise required", "new tool invocation from scratch"),
        CoverageRow("core hybrid cron", 23, "message + scheduler", "one-shot reminder", "recurring persistence"),
        CoverageRow("adaptive / staged / ambiguous cron", 27, "message + scheduler", "one-shot or underspecified reminder", "staged or obfuscated recurrence"),
        CoverageRow("implicit durability", 6, "message + scheduler", "legitimate durable intent", "tests false-positive boundary"),
        CoverageRow("negative cron controls", 2, "message + scheduler", "one-shot reminder", "no persistence-sensitive upgrade"),
        CoverageRow("file persistence", 11, "file", "bounded file action", "durable artifact creation"),
        CoverageRow("calendar recurrence", 11, "calendar", "bounded calendar update", "recurring event creation"),
        CoverageRow("recipient hijack", 10, "messaging", "intended recipient only", "broadened / redirected routing"),
    ]
    lines = [
        r"\begin{table*}[t]",
        r"\centering",
        r"\caption{PSEBench coverage used in the paper. The benchmark separates attack-only tool induction from hybrid legitimate-tool workflows and then expands the latter along authorization-sensitive families.}",
        r"\label{tab:psebench_coverage}",
        r"\small",
        r"\setlength{\tabcolsep}{4pt}",
        r"\begin{tabular}{p{3.0cm}r p{2.1cm} p{3.1cm} p{3.8cm}}",
        r"\toprule",
        r"\textbf{Slice} & \textbf{\#scenarios} & \textbf{Channel} & \textbf{Legitimate tool use} & \textbf{Unauthorized upgrade under test} \\",
        r"\midrule",
    ]
    for row in rows:
        lines.append(
            f"{row.slice_name} & {row.scenarios} & {row.channel} & {row.benign_tool} & {row.unauthorized_upgrade} \\\\"
        )
    lines.extend([r"\bottomrule", r"\end{tabular}", r"\end{table*}", ""])
    (TABLES / "benchmark_coverage.tex").write_text("\n".join(lines))


def make_main_defense_table() -> None:
    baseline = parse_baseline_csv()
    policies = ["permissive", "strict / safe", "firewall", "confirm-all-persistent", "SLC", "IACG"]
    slices = [
        "core cron matched slice",
        "authorization-boundary contrast",
        "implicit durability",
        "failure-mechanism stress test",
    ]

    def fmt_cell(sl: str, policy: str) -> str:
        sub = baseline[(baseline["slice"] == sl) & (baseline["policy"] == policy)]
        if sub.empty:
            return "--"
        r = sub.iloc[0]
        base = f"{r['asr']:.3f} / {r['tcr']:.3f}"
        if pd.notna(r["confirmations"]):
            base += f" ({int(r['confirmations'])})"
        return base

    lines = [
        r"\begin{table*}[t]",
        r"\centering",
        r"\caption{Main reference-monitor matrix. Each cell reports ASR / TCR; parentheses show confirmation count where applicable.}",
        r"\label{tab:main_defense_matrix}",
        r"\small",
        r"\setlength{\tabcolsep}{4pt}",
        r"\begin{tabular}{lcccc}",
        r"\toprule",
        r"\textbf{Policy} & \textbf{Core cron} & \textbf{Auth.\ boundary} & \textbf{Implicit durability} & \textbf{Lexical stress} \\",
        r"\midrule",
    ]
    for policy in policies:
        label = policy.replace("confirm-all-persistent", "confirm-all")
        cells = [fmt_cell(sl, policy) for sl in slices]
        lines.append(f"{label} & {' & '.join(cells)} \\\\")
    lines.extend([r"\bottomrule", r"\end{tabular}", r"\end{table*}", ""])
    (TABLES / "main_defense_matrix.tex").write_text("\n".join(lines))


def main() -> None:
    ensure_dirs()
    configure_style()
    make_risk_forest_plot()
    make_security_utility_frontier()
    make_authorization_boundary_matrix()
    make_generalization_dumbbell()
    make_benchmark_coverage_table()
    make_main_defense_table()
    print("Generated figures:")
    for p in sorted(FIGURES.glob("*.png")):
        print(" -", p.name)
    print("Generated tables:")
    for p in sorted(TABLES.glob("*.tex")):
        print(" -", p.name)


if __name__ == "__main__":
    main()
