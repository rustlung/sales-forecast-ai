from __future__ import annotations

import argparse
import logging
from pathlib import Path

from sales_forecast.logging_config import configure_logging
from sales_forecast.services.demo_data import DEFAULT_DEMO_SEED, RU_DEMO_SEED, generate_demo_csv


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate deterministic synthetic sales CSV data.")
    parser.add_argument("--profile", choices=("default", "ru"), default="default")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--seed", type=int)
    args = parser.parse_args()

    configure_logging("INFO")
    logger = logging.getLogger(__name__)
    output = args.output or Path("demo_data/sales_demo_ru.csv" if args.profile == "ru" else "demo_data/sales_demo.csv")
    seed = args.seed if args.seed is not None else (RU_DEMO_SEED if args.profile == "ru" else DEFAULT_DEMO_SEED)
    logger.info("Generating %s synthetic demo data at %s with seed %s", args.profile, output, seed)
    rows_count = generate_demo_csv(output, seed=seed, profile=args.profile)
    logger.info("Generated %s rows in %s", rows_count, output)
    print(f"Generated {rows_count} rows: {output}")


if __name__ == "__main__":
    main()
