# Solar Pipeline (CLI Version)

Minimal, portable solar forecast → energy estimate → battery charge prognosis.

No GUI — fast, efficient, and easy to automate.

## Project Overview
- Pulls solar radiation forecast (daily + hourly) from tutiempo.net
- Calculates per-panel and total system yield, plus chargeable energy for your batteries
- Outputs CSV files for further analysis

## Installation
```bash
pip install -r requirements.txt
```

## Usage
```bash
python main.py
```

Results are saved to `data/` folder as CSV files.

## Configuration
Edit `config.yaml` to adjust your system parameters:

| Setting | Description |
|---------|-------------|
| `solar_panel.count` | Number of panels |
| `solar_panel.efficiency` | Panel efficiency (0.20 = 20%) |
| `solar_panel.area_per_panel_m2` | Size of one panel (m²) |
| `battery.count` | Number of batteries |
| `battery.capacity_kwh_per_battery` | Storage per battery (kWh) |
| `battery.max_charge_rate_kw_per_battery` | Charge speed per battery (kW) |
| `system.efficiency` | Inverter/wiring efficiency |

## Outputs

| File | Description |
|------|-------------|
| `data/solar_report.html` | **Visual report** - open in browser |
| `data/extracted/daily_forecast.csv` | Daily solar radiation forecast |
| `data/extracted/hourly_detail.csv` | Hourly solar radiation |
| `data/prognosis/battery_prognosis.csv` | Calculated yields, chargeable energy, charge % |

History files (deduplicated) are stored in `data/history/`.
