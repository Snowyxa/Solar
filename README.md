# Solar Pipeline

Beginner-friendly solar forecast → energy estimate → battery charge prognosis.

This project downloads a 15‑day solar radiation forecast (kWh/m²), estimates how much energy your solar panels could produce (kWh), then estimates how much of that could charge your batteries.

## Project Overview
- Pulls solar radiation forecast (daily + hourly) from tutiempo.net.
- Calculates per-panel and total system yield, plus chargeable energy for your batteries.
- Lets you change key numbers (panel count, efficiency from datasheet, battery count/capacity) in one place or via a GUI form.


## Installation / Setup
1) Install Python 3.8+
2) Install dependencies (run in this project folder):

```bash
pip install -r requirements.txt
```

## Start / Run Commands
Run the pipeline (downloads forecast + exports CSVs):

```bash
python main.py
```

Open the GUI (edit settings + re-run + view results):

```bash
python -c "from gui.viewer import launch_gui; launch_gui()"
```

## Configuration (what you can change and why)
All user settings live in `config.yaml` (or use the GUI form). You only change numbers here — no code changes needed.
- `solar_panel.count` — number of panels.
- `solar_panel.efficiency` — **Research your panel model and get the exact efficiency from the manufacturer datasheet** (look for "Module Efficiency" at STC conditions). Enter as decimal (0.20 = 20%) or percentage (20).
- `solar_panel.area_per_panel_m2` — size of one panel.
- `battery.count` — how many batteries.
- `battery.capacity_kwh_per_battery` — storage per battery (kWh).
- `battery.max_charge_rate_kw_per_battery` — charge speed per battery (kW).
- `system.efficiency` — inverter/wiring efficiency (fraction).

## Prognosis / Calculations (with math examples)
### Key ideas (plain language)
- Solar radiation is shown as **kWh per square meter** (kWh/m²).
- Your panels turn a fraction of that sunlight into electricity (efficiency).
- More panels → more total area → more energy.
- Batteries have a total storage limit (kWh) and a maximum charge speed (kW).

### Formulas (per day)
- Per-panel yield: $$Y_{panel} = R_{kWh/m^2} \times A_{panel} \times \eta_{panel} \times \eta_{system}$$
- Total yield (all panels): $$Y_{total} = Y_{panel} \times N_{panels}$$
- Battery capacity (all batteries): $$C_{batt} = C_{one} \times N_{batt}$$
- Max chargeable energy (8h charge window): $$E_{charge} = \min\big(C_{batt},\ (P_{rate\_one} \times N_{batt}) \times 8,\ Y_{total}\big)$$
- Charge percent: $$\text{Charge\%} = \frac{E_{charge}}{C_{batt}} \times 100$$

Also:
- Battery storage total: $$\text{Storage}_{total} = \text{capacity\_kwh\_per\_battery} \times N_{batt}$$


---

Worked example (defaults in `config.yaml`):
- Panels: `N_panels = 8`, `A_panel = 1.8 m²`, `η_panel = 0.20` (20% from datasheet), `η_system = 0.85`.
- Batteries: `N_batt = 1`, `C_one = 10 kWh`, `P_rate_one = 5 kW`.
- Forecast for the day: `R = 1.10 kWh/m²`.
- Per-panel yield: $$Y_{panel} = 1.10 \times 1.8 \times 0.20 \times 0.85 \approx 0.3366\ \text{kWh}$$
- Total yield: $$Y_{total} = 0.3366 \times 8 \approx 2.6928\ \text{kWh}$$
- Battery capacity: $$C_{batt} = 10\ \text{kWh}$$
- Chargeable: $$E_{charge} = \min(10,\ 5 \times 8,\ 2.6928) = 2.6928\ \text{kWh}$$
- Charge %: $$\text{Charge\%} = 2.6928 / 10 \times 100 \approx 26.9\%$$

What to tweak to see different outcomes:
- Change `count` for panels or batteries to model larger/smaller systems.
- Adjust `capacity_kwh_per_battery` and `max_charge_rate_kw_per_battery` to explore storage and charge-speed limits.
- Update `efficiency` to match your exact panel datasheet value.

## Outputs
- `data/exports/daily_forecast.csv` — daily solar radiation forecast.
- `data/exports/hourly_detail.csv` — hourly solar radiation.
- `data/exports/battery_prognosis.csv` — includes panel/battery counts, per-panel yield, total yield, chargeable energy, and charge %.

