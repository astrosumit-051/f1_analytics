"""Report figures built only from committed result files.

    python report/figures/make_report_figures.py

Reads no pairs file and no outcome column. Every number comes from a results file
already on main:
- models/output/tuning/tune_metrics.csv (2024, model selection)
- evaluation/locked_results/test/{metrics,metric_intervals,calibration}.csv (2025)
- evaluation/locked_results/transfer/{metrics,metric_intervals,calibration}.csv (2026)
- data/derived/frozen/crossing_intervals.csv (frozen 2018-2024 window)
- evaluation/training_runs/common_h3/crossing_intervals.csv (2018-2023 window)

Writes four PNGs next to this script.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

INK, INK2, MUTED, GRID = "#1f2328", "#57606a", "#8c959f", "#e5e7eb"
FINAL, BASE = "#2a78d6", "#eb6834"          # categorical slots 1 and 2
D1, D23 = "#1d5e85", "#a34229"              # delay colours used in undercut_window.png
ZONES = ["#1c5cab", "#6da7ec", "#cde2fb"]   # one blue ramp: likely / marginal / long shot
SEASONS = {"test": "2025 locked test", "transfer": "2026 transfer"}

plt.rcParams.update({
    "font.size": 10, "axes.edgecolor": MUTED, "axes.labelcolor": INK2, "xtick.color": INK2,
    "ytick.color": INK2, "axes.spines.top": False, "axes.spines.right": False,
    "figure.facecolor": "white", "axes.facecolor": "white", "savefig.dpi": 200,
})


def read(rel: str) -> pd.DataFrame:
    return pd.read_csv(ROOT / rel)


def held_out() -> pd.DataFrame:
    """One row per season, outcome and model: scores and calibration-in-the-large."""
    rows = []
    tune = read("models/output/tuning/tune_metrics.csv").set_index("model_id")
    for model, src in (("final_v1", "primary_combined_v1"), ("baseline_gap_v1", "baseline_gap_v1")):
        r = tune.loc[src]
        rows.append(dict(season="2024 selection", outcome="success_h3", model_id=model,
                         pairs=r.scored_pairs, races=r.scored_races, log_loss=r.log_loss,
                         mean_prediction=r.mean_prediction, observed_rate=r.observed_rate))
    for split, label in SEASONS.items():
        m = read(f"evaluation/locked_results/{split}/metrics.csv")
        for r in m.itertuples():
            rows.append(dict(season=label, outcome=r.outcome, model_id=r.model_id, pairs=r.scored_pairs,
                             races=r.scored_races, log_loss=r.log_loss,
                             mean_prediction=r.mean_prediction, observed_rate=r.observed_rate))
    return pd.DataFrame(rows)


def differences() -> pd.DataFrame:
    """Final minus gap-only log loss per season; 2024 has no interval."""
    h = held_out().pivot_table(index=["season", "outcome"], columns="model_id", values="log_loss")
    out = []
    for (season, outcome), r in h.iterrows():
        out.append(dict(season=season, outcome=outcome, diff=r.final_v1 - r.baseline_gap_v1, lo=None, hi=None))
    out = pd.DataFrame(out).set_index(["season", "outcome"])
    for split, label in SEASONS.items():
        iv = read(f"evaluation/locked_results/{split}/metric_intervals.csv")
        iv = iv[iv.model_id.eq("final_v1") & iv.metric.eq("log_loss_minus_baseline")]
        for r in iv.itertuples():
            out.loc[(label, r.outcome), ["diff", "lo", "hi"]] = [r.estimate, r.p_lo, r.p_hi]
    return out.reset_index()


def fig_scoreboard(path: Path):
    d = differences()
    order = ["2024 selection", "2025 locked test", "2026 transfer"]
    counts = held_out().query("model_id == 'final_v1'").set_index(["season", "outcome"])
    fig, ax = plt.subplots(figsize=(7.6, 3.6))
    styles = {"success_h3": (0.12, "o", "Three laps after the stop"),
              "success_common_h3": (-0.12, "s", "Common lap")}
    for i, season in enumerate(order):
        y = len(order) - 1 - i
        for outcome, (dy, marker, _) in styles.items():
            row = d[(d.season == season) & (d.outcome == outcome)]
            if row.empty:
                continue
            r = row.iloc[0]
            if pd.notna(r.lo):
                ax.hlines(y + dy, r.lo, r.hi, color=FINAL, linewidth=2)
                ax.scatter(r["diff"], y + dy, color=FINAL, marker=marker, s=46, zorder=3,
                           edgecolor="white", linewidth=1.5)
            else:
                ax.scatter(r["diff"], y + dy, facecolor="white", edgecolor=FINAL, marker=marker, s=46,
                           linewidth=1.8, zorder=3)
            c = counts.loc[(season, outcome)]
            ax.annotate(f"{r['diff']:+.3f}   {int(c.pairs)} pairs, {int(c.races)} races",
                        (1.03, y + dy), xycoords=("axes fraction", "data"), color=INK2, fontsize=8.5,
                        va="center", annotation_clip=False)
    ax.axvline(0, color=INK, linewidth=1)
    ax.set_yticks(range(len(order)), order[::-1], color=INK)
    ax.set_xlim(-0.2, 0.25)
    ax.set_ylim(-0.6, len(order) - 0.4)
    ax.set_xlabel("Log loss, final model minus gap-only curve")
    ax.grid(axis="x", color=GRID)
    ax.tick_params(axis="y", length=0)
    ax.text(-0.195, len(order) - 0.45, "← final model better", color=INK2, fontsize=8.5, va="top")
    ax.text(0.245, len(order) - 0.45, "gap-only better →", color=INK2, fontsize=8.5, va="top", ha="right")
    handles = [Line2D([], [], color=FINAL, marker=m, linestyle="", label=lab, markersize=7)
               for _, m, lab in styles.values()]
    handles.append(Line2D([], [], color=FINAL, marker="o", markerfacecolor="white", linestyle="",
                          label="2024: chosen on this season, no interval", markersize=7))
    ax.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=3, frameon=False,
              fontsize=8.5)
    fig.tight_layout()
    fig.subplots_adjust(right=0.72)
    fig.savefig(path)
    plt.close(fig)


def fig_rates(path: Path):
    h = held_out().query("outcome == 'success_h3'")
    order = ["2024 selection", "2025 locked test", "2026 transfer"]
    fig, ax = plt.subplots(figsize=(7.2, 3.3))
    for i, season in enumerate(order):
        y = len(order) - 1 - i
        s = h[h.season == season].set_index("model_id")
        obs = s.observed_rate.iloc[0]
        lo = min(obs, s.mean_prediction.min())
        hi = max(obs, s.mean_prediction.max())
        ax.scatter(obs * 100, y, marker="D", color=INK, s=60, zorder=4)
        for model, color, dy in (("final_v1", FINAL, 0.2), ("baseline_gap_v1", BASE, -0.2)):
            p = s.loc[model, "mean_prediction"] * 100
            ax.plot([obs * 100, p], [y, y + dy], color=color, linewidth=1.2, alpha=0.6, zorder=2)
            ax.scatter(p, y + dy, color=color, s=70, zorder=3, edgecolor="white", linewidth=1.5)
            right = p >= obs * 100
            ax.annotate(f"{p:.1f}%", (p + (0.3 if right else -0.3), y + dy), color=INK2, fontsize=8,
                        va="center", ha="left" if right else "right")
        left = s.mean_prediction.min() >= obs  # put the label on the side with no connector lines
        ax.annotate(f"observed {obs:.1%}", (obs * 100 + (-0.35 if left else 0.35), y),
                    ha="right" if left else "left", va="center", color=INK, fontsize=8.5)
        n = int(s.pairs.iloc[0])
        ax.annotate(f"{n} pairs", (27.6, y), color=MUTED, fontsize=8.5, va="center")
    ax.set_yticks(range(len(order)), order[::-1], color=INK)
    ax.set_xlim(12.5, 29.5)
    ax.set_ylim(-0.6, len(order) - 0.4)
    ax.set_xlabel("Share of undercuts that kept the place, three laps after the stop (%)")
    ax.grid(axis="x", color=GRID)
    ax.tick_params(axis="y", length=0)
    handles = [Line2D([], [], marker="D", color=INK, linestyle="", label="Observed", markersize=7),
               Line2D([], [], marker="o", color=FINAL, linestyle="", label="Final model, mean prediction", markersize=8),
               Line2D([], [], marker="o", color=BASE, linestyle="", label="Gap-only curve, mean prediction", markersize=8)]
    ax.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=3, frameon=False, fontsize=8.5)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def fig_calibration(path: Path):
    fig, axes = plt.subplots(1, 2, figsize=(7.4, 3.7), sharey=True)
    for ax, (split, label) in zip(axes, SEASONS.items()):
        c = read(f"evaluation/locked_results/{split}/calibration.csv").query("outcome == 'success_h3'")
        ax.plot([0, 1], [0, 1], color=MUTED, linestyle=":", linewidth=1)
        for model, color, name in (("baseline_gap_v1", BASE, "Gap-only curve"), ("final_v1", FINAL, "Final model")):
            m = c[c.model_id == model].sort_values("mean_prediction")
            ax.scatter(m.mean_prediction, m.observed_rate, s=m.n * 7 + 14, color=color, edgecolor="white",
                       linewidth=1.5, zorder=3, alpha=0.9, label=name)
            for r in m.itertuples():
                ax.annotate(str(r.n), (r.mean_prediction, r.observed_rate), xytext=(9, 7),
                            textcoords="offset points", fontsize=7.5, color=color)
        ax.set_title(label, color=INK, fontsize=10, loc="left")
        ax.set_xlim(-0.02, 1.02)
        ax.set_ylim(-0.04, 1.04)
        ax.set_xlabel("Mean predicted probability")
        ax.grid(color=GRID)
        ax.set_aspect("equal")
    axes[0].set_ylabel("Observed share")
    axes[0].legend(frameon=False, fontsize=8.5, loc="upper left", markerscale=0.6)
    fig.text(0.5, 0.005, "Three-lap outcome, five probability bins. Numbers and marker area give the pairs "
             "in each bin; bins of one to three pairs swing widely.", ha="center", color=MUTED, fontsize=8)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(path)
    plt.close(fig)


def fig_window(path: Path):
    frozen = read("data/derived/frozen/crossing_intervals.csv")
    frozen = frozen[frozen.model_id.eq("final_v1") & frozen.outcome.eq("success_common_h3")]
    train = read("evaluation/training_runs/common_h3/crossing_intervals.csv")
    train = train[train.model_id.eq("final_v1")]
    fig, ax = plt.subplots(figsize=(7.6, 3.3))
    xmax = 5.0
    rows = [("d23", "Rival waits 2–3 laps", D23), ("d1", "Rival waits 1 lap", D1)]
    for y, (group, label, color) in enumerate(rows):
        f = frozen[frozen.delay_group.eq(group)].set_index("threshold")
        t = train[train.delay_group.eq(group)].set_index("threshold")
        c50, c25 = f.loc[0.5, "crossing_gap_sec"], f.loc[0.25, "crossing_gap_sec"]
        edges = [0, c50, c25, xmax]
        for k in range(3):
            ax.barh(y, edges[k + 1] - edges[k], left=edges[k], height=0.46, color=ZONES[k],
                    edgecolor="white", linewidth=2)
        for thr, yy in ((0.5, y + 0.33), (0.25, y + 0.47)):
            ax.errorbar(f.loc[thr, "crossing_gap_sec"], yy,
                        xerr=[[f.loc[thr, "crossing_gap_sec"] - f.loc[thr, "lo_sec"]],
                              [f.loc[thr, "hi_sec"] - f.loc[thr, "crossing_gap_sec"]]],
                        fmt="o", color=INK, markersize=4.5, linewidth=1.4, capsize=3, zorder=3)
            ax.annotate(f"{thr:.0%}: {f.loc[thr, 'crossing_gap_sec']:.2f} s",
                        (f.loc[thr, "hi_sec"] + 0.06, yy), ha="left", va="center", fontsize=8.5, color=INK)
            ax.scatter(t.loc[thr, "crossing_gap_sec"], y - 0.33, marker="v", facecolor="white", edgecolor=INK2,
                       s=30, linewidth=1.3, zorder=3)
        ax.text(-0.08, y, label, ha="right", va="center", color=color, fontsize=9.5, fontweight="bold")
    ax.set_xlim(0, xmax)
    ax.set_ylim(-0.6, 1.75)
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    ax.set_xlabel("Gap to the car ahead when the undercut starts (s)")
    ax.grid(axis="x", color=GRID)
    ax.set_axisbelow(True)
    handles = [Patch(color=ZONES[0], label="Better than even (> 50%)"),
               Patch(color=ZONES[1], label="Marginal (25–50%)"),
               Patch(color=ZONES[2], label="Long shot (< 25%)"),
               Line2D([], [], color=INK, marker="o", markersize=4, label="Frozen crossing, 95% range"),
               Line2D([], [], color=INK2, marker="v", markerfacecolor="white", linestyle="",
                      label="2018–2023 fit crossing")]
    ax.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.45, 1.0), ncol=3, frameon=False, fontsize=8.5)
    fig.tight_layout()
    fig.subplots_adjust(left=0.2)
    fig.savefig(path)
    plt.close(fig)


def main():
    fig_window(HERE / "window_zones.png")
    fig_scoreboard(HERE / "heldout_scoreboard.png")
    fig_rates(HERE / "predicted_vs_observed.png")
    fig_calibration(HERE / "calibration_2025_2026.png")
    print(differences().round(3).to_string(index=False))


if __name__ == "__main__":
    main()
