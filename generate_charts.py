"""
Generates the two charts referenced in README.md, from live data - not
hand-crafted images. Re-running this script reproduces the same figures
(numbers will drift slightly as new data accumulates via the daily
downloader).

Usage:
    python generate_charts.py
"""

import os

import matplotlib.pyplot as plt
import numpy as np

from db import read_df
from walkforward_common import PERIODS, collapse_to_episodes, forward_return, summarize

OUT_DIR = "charts"
DVOL_LOW = 0.05
HORIZON = 60

COLOR_SIGNAL = "#d95f02"
COLOR_BASELINE = "#1b9e77"


def load_data(symbol: str):
    df = read_df(
        """
        SELECT i.date, i.dvol_percentile_90d, c.close
        FROM indicators i
        JOIN candles c ON c.symbol = i.symbol AND c.open_time = i.date
        WHERE i.symbol = %(symbol)s
        ORDER BY i.date
        """,
        params={"symbol": symbol},
    )
    return df[df["dvol_percentile_90d"].notna()].reset_index(drop=True)


def chart_distribution():
    """Chart 1: forward-return distribution after the DVOL-low signal vs
    baseline, for BTC and ETH side by side - the core H6b finding."""
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), sharey=True)

    for ax, symbol in zip(axes, ["BTCUSDT", "ETHUSDT"]):
        df = load_data(symbol)
        episode_mask = collapse_to_episodes(df["dvol_percentile_90d"] < DVOL_LOW)
        fwd = forward_return(df["close"], HORIZON)

        signal_returns = fwd[episode_mask].dropna()
        baseline_returns = fwd.dropna()

        bins = np.linspace(-40, 100, 29)
        ax.hist(baseline_returns.clip(-40, 99.9), bins=bins, density=True,
                color=COLOR_BASELINE, alpha=0.55, label=f"Baseline (n={len(baseline_returns)})")
        ax.hist(signal_returns.clip(-40, 99.9), bins=bins, density=True,
                color=COLOR_SIGNAL, alpha=0.7, label=f"DVOL-low signal (n={len(signal_returns)})")

        ax.axvline(baseline_returns.mean(), color=COLOR_BASELINE, linestyle="--", linewidth=1.5)
        ax.axvline(signal_returns.mean(), color=COLOR_SIGNAL, linestyle="--", linewidth=1.5)

        ax.set_title(f"{symbol[:-4]}: {HORIZON}-day forward return")
        ax.set_xlabel("Return (%)")
        ax.legend(fontsize=9, loc="upper right")
        ax.axvline(0, color="grey", linewidth=0.8)

    axes[0].set_ylabel("Density")
    fig.suptitle("H6b: DVOL complacency precedes underperformance", fontsize=13, y=1.03)
    fig.tight_layout()
    path = os.path.join(OUT_DIR, "dvol_distribution.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {path}")


def chart_walkforward():
    """Chart 2: walk-forward consistency across years and both assets at
    the 60-day horizon - directly visualizes the 26/30 confirming result."""
    fig, ax = plt.subplots(figsize=(9, 4.5))

    period_labels = [label.split(" (")[0] for _, _, label in PERIODS]
    x = np.arange(len(PERIODS))
    width = 0.35

    for offset, symbol, color in [(-width / 2, "BTCUSDT", "#7570b3"), (width / 2, "ETHUSDT", "#e7298a")]:
        df = load_data(symbol)
        signal_mask = collapse_to_episodes(df["dvol_percentile_90d"] < DVOL_LOW)
        fwd = forward_return(df["close"], HORIZON)

        edges = []
        for start, end, _ in PERIODS:
            import pandas as pd
            period_mask = (df["date"] >= pd.Timestamp(start, tz="UTC")) & (df["date"] < pd.Timestamp(end, tz="UTC"))
            sig = summarize(fwd[period_mask & signal_mask])
            base = summarize(fwd[period_mask])
            edges.append(sig["mean"] - base["mean"] if sig["mean"] is not None and base["mean"] is not None else np.nan)

        bars = ax.bar(x + offset, edges, width, label=symbol[:-4], color=color)

    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(period_labels, rotation=20, ha="right")
    ax.set_ylabel("Return edge vs baseline (pp)")
    ax.set_title("H6b walk-forward: 60-day edge by period (negative = confirms)")
    ax.legend()
    fig.tight_layout()
    path = os.path.join(OUT_DIR, "walkforward_consistency.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {path}")


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    chart_distribution()
    chart_walkforward()
