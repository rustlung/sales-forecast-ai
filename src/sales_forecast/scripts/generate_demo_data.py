from __future__ import annotations

import argparse
import logging
from pathlib import Path

from sales_forecast.logging_config import configure_logging
from sales_forecast.services.demo_data import DEFAULT_DEMO_SEED, generate_demo_csv


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate deterministic synthetic sales CSV data.")
    parser.add_argument("--output", type=Path, default=Path("demo_data/sales_demo.csv"))
    parser.add_argument("--seed", type=int, default=DEFAULT_DEMO_SEED)
    args = parser.parse_args()

    configure_logging("INFO")
    logger = logging.getLogger(__name__)
    logger.info("Generating synthetic demo data at %s with seed %s", args.output, args.seed)
    rows_count = generate_demo_csv(args.output, seed=args.seed)
    logger.info("Generated %s rows in %s", rows_count, args.output)
    print(f"Generated {rows_count} rows: {args.output}")


if __name__ == "__main__":
    main()
