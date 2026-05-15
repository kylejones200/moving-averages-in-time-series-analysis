"""Moving averages using Polars and DuckDB."""

from pathlib import Path

import duckdb
import matplotlib.pyplot as plt
import numpy as np
import polars as pl


def compute_moving_averages(
    df: pl.DataFrame, value_col: str, window: int
) -> pl.DataFrame:
    """AMA and GMA via DuckDB window functions; EWMA via Polars (no native DuckDB EWMA)."""
    result = duckdb.sql(f"""
        SELECT
            {value_col},
            AVG({value_col})
                OVER (ROWS BETWEEN {window - 1} PRECEDING AND CURRENT ROW) AS ama,
            POWER(
                EXP(SUM(LN({value_col})) OVER (ROWS BETWEEN {window - 1} PRECEDING AND CURRENT ROW)),
                1.0 / {window}
            ) AS gma
        FROM df
    """).pl()

    return result.with_columns(pl.col(value_col).ewm_mean(alpha=0.3).alias("ewma"))


def compute_crossover_strategy(
    df: pl.DataFrame,
    date_col: str,
    price_col: str,
    short_window: int = 20,
    long_window: int = 50,
) -> pl.DataFrame:
    """SMA crossover signals and strategy returns — all DuckDB window functions."""
    return duckdb.sql(f"""
        WITH smas AS (
            SELECT
                {date_col},
                {price_col},
                AVG({price_col}) OVER (ORDER BY {date_col} ROWS BETWEEN {short_window - 1} PRECEDING AND CURRENT ROW) AS sma_short,
                AVG({price_col}) OVER (ORDER BY {date_col} ROWS BETWEEN {long_window - 1} PRECEDING AND CURRENT ROW)  AS sma_long
            FROM df
        ),
        signals AS (
            SELECT *,
                CASE
                    WHEN sma_short > sma_long THEN  1
                    WHEN sma_short < sma_long THEN -1
                    ELSE 0
                END AS signal
            FROM smas
        )
        SELECT *,
            signal - LAG(signal, 1, 0) OVER (ORDER BY {date_col}) AS crossover,
            LAG(signal, 1, 0) OVER (ORDER BY {date_col})
                * ({price_col} - LAG({price_col}, 1) OVER (ORDER BY {date_col}))
                / NULLIF(LAG({price_col}, 1) OVER (ORDER BY {date_col}), 0) AS strategy_return
        FROM signals
        ORDER BY {date_col}
    """).pl()


def plot_moving_averages(
    df: pl.DataFrame, value_col: str, output_dir: Path, plot: bool = False
):
    for col, label, color in [
        ("ama", "Arithmetic Moving Average", "#D4A574"),
        ("gma", "Geometric Moving Average", "#8B6F9E"),
        ("ewma", "Exponentially Weighted Moving Average", "#E07B54"),
    ]:
        if plot:
            fig, ax = plt.subplots(figsize=(8, 4))
            ax.plot(
                df[value_col].to_list(),
                label="Original Data",
                color="#4A90A4",
                linewidth=1.5,
            )
            ax.plot(
                df[col].to_list(),
                label=label,
                color=color,
                linestyle="--",
                linewidth=1.5,
            )
            ax.set_title(label)
            ax.set_xlabel("Time")
            ax.set_ylabel("Value")
            ax.legend()
            plt.tight_layout()
            plt.savefig(output_dir / f"{col}.png", dpi=100, bbox_inches="tight")
            plt.close()


def plot_crossover_strategy(
    df: pl.DataFrame,
    date_col: str,
    price_col: str,
    output_path: Path,
    plot: bool = False,
):
    dates = df[date_col].to_list()
    prices = df[price_col].to_list()
    sma_short = df["sma_short"].to_list()
    sma_long = df["sma_long"].to_list()

    buy_mask = [c == 2 for c in df["crossover"].to_list()]
    sell_mask = [c == -2 for c in df["crossover"].to_list()]
    buy_dates = [d for d, m in zip(dates, buy_mask) if m]
    buy_prices = [p for p, m in zip(prices, buy_mask) if m]
    sell_dates = [d for d, m in zip(dates, sell_mask) if m]
    sell_prices = [p for p, m in zip(prices, sell_mask) if m]

    sma_diff_pct = [(s - l) / l * 100 if l else 0 for s, l in zip(sma_short, sma_long)]

    if plot:
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 10))

        ax1.plot(dates, prices, label="Price", alpha=0.7, color="gray")
        ax1.plot(
            dates, sma_short, label=f"{len(sma_short) // 10}-day SMA", color="blue"
        )
        ax1.plot(dates, sma_long, label=f"{len(sma_long) // 4}-day SMA", color="red")
        ax1.scatter(
            buy_dates, buy_prices, marker="^", color="green", s=100, label="Buy Signal"
        )
        ax1.scatter(
            sell_dates, sell_prices, marker="v", color="red", s=100, label="Sell Signal"
        )
        ax1.set_title("Moving Average Crossover Strategy")
        ax1.legend()

        ax2.fill_between(
            dates,
            sma_diff_pct,
            0,
            where=[v > 0 for v in sma_diff_pct],
            color="green",
            alpha=0.3,
            label="Bullish Divergence",
        )
        ax2.fill_between(
            dates,
            sma_diff_pct,
            0,
            where=[v < 0 for v in sma_diff_pct],
            color="red",
            alpha=0.3,
            label="Bearish Divergence",
        )
        ax2.axhline(0, color="black", linestyle="-", alpha=0.3)
        ax2.set_title("Signal Strength (% Difference between SMAs)")
        ax2.legend()

        plt.tight_layout()
        plt.savefig(output_path, dpi=100, bbox_inches="tight")
        plt.close()
