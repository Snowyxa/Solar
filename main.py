#!/usr/bin/env python3
"""
Solar Pipeline - Main Entry Point
Simple solar radiation scraper and battery prognosis calculator
"""

import sys
from src.solar_pipeline import run_pipeline
from src.config import load_config
from gui.viewer import launch_gui

if __name__ == '__main__':
    config = load_config()
    success = run_pipeline(config)
    
    if success:
        print("\nLaunching GUI viewer...")
        launch_gui()
    
    sys.exit(0 if success else 1)
