#!/usr/bin/env python3
"""
Solar Pipeline - Main Entry Point
Simple solar radiation scraper and battery prognosis calculator
"""

import argparse
import sys

from src.config import load_config
from src.solar_pipeline import run_pipeline


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Solar forecast → battery prognosis.")
    parser.add_argument(
        "--no-gui",
        action="store_true",
        help="Run pipeline and exit (do not open the GUI). Useful for daily automation.",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = _parse_args(sys.argv[1:])

    config = load_config()
    success = run_pipeline(config)

    if success and not args.no_gui:
        from gui.viewer import launch_gui

        print("\nLaunching GUI viewer...")
        launch_gui()

    sys.exit(0 if success else 1)
