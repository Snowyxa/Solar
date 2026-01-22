#!/usr/bin/env python3
"""
Solar Pipeline - CLI Version
Minimal, portable solar radiation scraper and battery prognosis calculator
"""

import sys

from src.config import load_config
from src.solar_pipeline import run_pipeline


if __name__ == "__main__":
    config = load_config()
    success = run_pipeline(config)
    sys.exit(0 if success else 1)
