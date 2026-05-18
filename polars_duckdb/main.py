#!/usr/bin/env python3
"""Moving averages — Polars + DuckDB rewrite."""

import logging
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import polars as pl
from core import (
    compute_crossover_strategy,
    compute_moving_averages,
    plot_crossover_strategy,
    plot_moving_averages,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
OUTPUT_DIR = Path(__file__).parent.parent / "images"
OUTPUT_DIR.mkdir(exist_ok=True)


def demo_simple_moving_averages():
    data = [10, 12, 14, 13, 15, 16, 14, 13, 17, 18]
    df = pl.DataFrame({"Value": data})
    result = compute_moving_averages(df, "Value", window=3)
    plot_moving_averages(result, "Value", OUTPUT_DIR)
    logging.info("Simple moving average plots saved.")


def demo_crossover_strategy():
    rng = np.random.default_rng(42)
    n_days = 200
    returns = rng.normal(loc=0.001, scale=0.02, size=n_days)
    prices = 100 * np.exp(np.cumsum(returns))
    start = date(2023, 1, 1)
    dates = [start + timedelta(days=i) for i in range(n_days)]
    df = pl.DataFrame({"Date": dates, "Price": prices.tolist()})
    result = compute_crossover_strategy(df, "Date", "Price", short_window=20, long_window=50)
    plot_crossover_strategy(result, "Date", "Price", OUTPUT_DIR / "moving_average_crossover.png")
    buy_count = result.filter(pl.col("crossover") == 2).height
    sell_count = result.filter(pl.col("crossover") == -2).height
    total_return = (1 + result["strategy_return"].fill_null(0)).product() - 1
    logging.info(f"Buy signals:  {buy_count}")
    logging.info(f"Sell signals: {sell_count}")
    logging.info(f"Strategy total return: {total_return:.2%}")


def main():
    demo_simple_moving_averages()
    demo_crossover_strategy()
    logging.info(f"Analysis complete. Figures saved to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
