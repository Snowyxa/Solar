"""Configuration management for Solar Pipeline.

All user-facing knobs live here so beginners can change numbers instead of logic.
"""

import yaml
from pathlib import Path
from typing import Dict, Any

CONFIG_FILE = Path("config.yaml")

# Default, beginner-friendly settings. Users change these either in config.yaml
# or via the GUI form (which writes the same keys).
DEFAULT_CONFIG = {
    'location': 'Deinze',
    'base_url': 'https://en.tutiempo.net',
    'fallback_url': 'https://en.tutiempo.net/solar-radiation/deinze.html',
    'max_retries': 3,
    'retry_delay': 2,
    'timeout': 10,
    'solar_panel': {
        'count': 8,                    # How many panels are installed
        'efficiency': 0.20,            # Panel efficiency from manufacturer datasheet (fraction)
        'area_per_panel_m2': 1.8,      # Size of ONE panel in square meters
    },
    'system': {
        'efficiency': 0.85,            # Wiring/inverter losses (fraction)
    },
    'battery': {
        'count': 1,                           # Number of batteries
        'capacity_kwh_per_battery': 10.0,     # Storage per battery (kWh)
        'max_charge_rate_kw_per_battery': 5.0 # How fast one battery can charge (kW)
    }
}


def _deep_merge(base: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge two dicts so nested config keys override cleanly."""
    merged = dict(base)
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config() -> Dict[str, Any]:
    """Load configuration from YAML or use defaults."""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = yaml.safe_load(f) or {}
                return _deep_merge(DEFAULT_CONFIG, config)
        except Exception as e:
            print(f"Warning: Error loading config: {e}, using defaults")
    return DEFAULT_CONFIG


def get_config(key: str, default: Any = None) -> Any:
    """Get a config value with dot notation"""
    config = load_config()
    keys = key.split('.')
    value = config
    
    for k in keys:
        if isinstance(value, dict):
            value = value.get(k)
            if value is None:
                return default
        else:
            return default
    
    return value
