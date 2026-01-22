"""Solar Pipeline - Solar Radiation Scraper & Battery Prognosis Calculator"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import re
import logging
import pandas as pd
from pathlib import Path
import time
import hashlib
import json
from .config import load_config
from .storage import write_snapshot_csv, upsert_history_csv

# Setup logging (overwrite each run - history is in CSV files)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[
        logging.FileHandler('solar_pipeline.log', mode='w'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

DATA_DIR = Path("data")
# Separate folders so it's obvious what's extracted vs calculated.
EXTRACTED_DIR = DATA_DIR / "extracted"   # parsed/cleaned data extracted from the website
PROGNOSIS_DIR = DATA_DIR / "prognosis"   # calculated battery prognosis output
HISTORY_DIR = DATA_DIR / "history"
HISTORY_EXTRACTED_DIR = HISTORY_DIR / "extracted"
HISTORY_PROGNOSIS_DIR = HISTORY_DIR / "prognosis"
# Legacy folder name used by older versions (kept for compatibility).
EXPORT_DIR = DATA_DIR / "exports"
REPORT_FILE = DATA_DIR / "solar_report.html"


def generate_html_report(prognosis_data, config, location):
    """Generate a nice HTML report file."""
    panel_cfg = config.get('solar_panel', {})
    battery_cfg = config.get('battery', {})
    system_eff = config.get('system', {}).get('efficiency', 0.85)
    
    total_production = sum(r['Production_kWh'] for r in prognosis_data)
    avg_charge = sum(r['ChargePercentage'] for r in prognosis_data) / len(prognosis_data)
    best_day = max(prognosis_data, key=lambda x: x['ChargePercentage'])
    
    # Build table rows
    rows_html = ""
    for r in prognosis_data:
        charge_pct = r['ChargePercentage']
        if charge_pct >= 50:
            color = "#4CAF50"  # green
        elif charge_pct >= 25:
            color = "#FF9800"  # orange
        else:
            color = "#f44336"  # red
        
        rows_html += f"""
        <tr>
            <td>{r['Date']}</td>
            <td>{r['DayName']}</td>
            <td>{r['SolarRadiation_kWh_m2']:.2f}</td>
            <td>{r['Production_kWh']:.2f}</td>
            <td style="color: {color}; font-weight: bold;">{charge_pct:.1f}%</td>
            <td><div style="background: linear-gradient(90deg, {color} {charge_pct}%, #333 {charge_pct}%); height: 20px; border-radius: 4px;"></div></td>
        </tr>"""
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Solar Forecast - {location}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #1a1a2e; 
            color: #eee; 
            padding: 20px;
            min-height: 100vh;
        }}
        .container {{ max-width: 1000px; margin: 0 auto; }}
        h1 {{ 
            color: #ffd700; 
            margin-bottom: 5px;
            font-size: 28px;
        }}
        .subtitle {{ color: #888; margin-bottom: 20px; }}
        .stats {{ 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); 
            gap: 15px; 
            margin-bottom: 25px; 
        }}
        .stat {{ 
            background: #252540; 
            padding: 15px; 
            border-radius: 8px;
            border-left: 4px solid #ffd700;
        }}
        .stat-label {{ color: #888; font-size: 12px; text-transform: uppercase; }}
        .stat-value {{ font-size: 24px; font-weight: bold; color: #fff; }}
        .stat-detail {{ font-size: 12px; color: #666; }}
        table {{ 
            width: 100%; 
            border-collapse: collapse; 
            background: #252540;
            border-radius: 8px;
            overflow: hidden;
        }}
        th {{ 
            background: #1a1a2e; 
            padding: 12px 8px; 
            text-align: left;
            color: #ffd700;
            font-weight: 600;
        }}
        td {{ padding: 10px 8px; border-bottom: 1px solid #333; }}
        tr:hover {{ background: #2a2a4a; }}
        .bar-col {{ width: 150px; }}
        .footer {{ margin-top: 20px; color: #666; font-size: 12px; text-align: center; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>☀️ Solar Forecast - {location}</h1>
        <p class="subtitle">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | Forecast: {prognosis_data[0]['Date']} to {prognosis_data[-1]['Date']}</p>
        
        <div class="stats">
            <div class="stat">
                <div class="stat-label">System</div>
                <div class="stat-value">{panel_cfg.get('count', 1)} Panels</div>
                <div class="stat-detail">{panel_cfg.get('area_per_panel_m2', 1.8)}m² @ {int(panel_cfg.get('efficiency', 0.2)*100)}% eff</div>
            </div>
            <div class="stat">
                <div class="stat-label">Battery</div>
                <div class="stat-value">{battery_cfg.get('capacity_kwh_per_battery', 10) * battery_cfg.get('count', 1):.0f} kWh</div>
                <div class="stat-detail">{battery_cfg.get('count', 1)}x {battery_cfg.get('capacity_kwh_per_battery', 10)} kWh</div>
            </div>
            <div class="stat">
                <div class="stat-label">Total Production ({len(prognosis_data)} days)</div>
                <div class="stat-value">{total_production:.1f} kWh</div>
                <div class="stat-detail">Avg {total_production/len(prognosis_data):.1f} kWh/day</div>
            </div>
            <div class="stat">
                <div class="stat-label">Avg Charge</div>
                <div class="stat-value">{avg_charge:.1f}%</div>
                <div class="stat-detail">Best: {best_day['DayName'][:3]} {best_day['ChargePercentage']:.0f}%</div>
            </div>
        </div>
        
        <table>
            <thead>
                <tr>
                    <th>Date</th>
                    <th>Day</th>
                    <th>Solar (kWh/m²)</th>
                    <th>Production (kWh)</th>
                    <th>Charge %</th>
                    <th class="bar-col">Battery</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>
        
        <p class="footer">Solar Pipeline CLI • System efficiency: {int(system_eff*100)}%</p>
    </div>
</body>
</html>"""
    
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text(html, encoding='utf-8')
    return REPORT_FILE


def _config_hash(config: dict) -> str:
    """Stable hash for the parts of config that affect prognosis calculations."""
    relevant = {
        "location": config.get("location"),
        "solar_panel": config.get("solar_panel", {}),
        "battery": config.get("battery", {}),
        "system": config.get("system", {}),
    }
    payload = json.dumps(relevant, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha1(payload).hexdigest()[:12]


def fetch_html(url, max_retries, retry_delay, timeout):
    """Fetch HTML with retry logic"""
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=timeout)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            if attempt < max_retries:
                time.sleep(retry_delay * attempt)
            else:
                logger.error(f"Failed to fetch data after {max_retries} attempts: {e}")
    return None


def find_url(location, base_url, fallback_url):
    """Find solar radiation URL for location"""
    location_lower = location.lower().replace(' ', '-')
    urls = [
        f"{base_url}/solar-radiation/{location_lower}.html",
        f"{base_url}/solar-radiation/{location_lower.replace('-', '_')}.html",
        f"{base_url}/solar-radiation/{location_lower.replace('-', '')}.html",
    ]
    
    for url in urls:
        html = fetch_html(url, 1, 1, 10)
        if html and ('solar' in html.lower() or 'radiation' in html.lower()):
            logger.info(f"Found: {url}")
            return url
    
    logger.warning(f"Using fallback URL: {fallback_url}")
    return fallback_url


def parse_date(text, today, index, seen_dates):
    """Parse date from text with improved logic"""
    text_lower = text.lower()
    
    # Check for "today" or "tomorrow" first
    if 'today' in text_lower:
        date = today
        if date not in seen_dates:
            seen_dates.add(date)
            return date
    elif 'tomorrow' in text_lower:
        date = today + timedelta(days=1)
        if date not in seen_dates:
            seen_dates.add(date)
            return date
    
    # Look for month names and dates
    months = {
        'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
        'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12,
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'jun': 6,
        'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
    }
    
    # Try to find date patterns like "January 19" or "Feb 2"
    for month_name, month_num in months.items():
        if month_name in text_lower:
            # Look for day number near the month name
            # Pattern: month name followed by optional comma/space and 1-2 digit day
            pattern = rf'{re.escape(month_name)}\s*,?\s*(\d{{1,2}})'
            match = re.search(pattern, text_lower)
            if match:
                day = int(match.group(1))
                # Determine year - if month is before current month, assume next year
                current_month = today.month
                if month_num < current_month or (month_num == current_month and day < today.day):
                    year = today.year + 1
                else:
                    year = today.year
                try:
                    date = datetime(year, month_num, day)
                    if date not in seen_dates:
                        seen_dates.add(date)
                        return date
                except ValueError:
                    pass
    
    # Try to find date patterns like "2026-01-19" or "19/01/2026"
    date_patterns = [
        (r'(\d{4})-(\d{1,2})-(\d{1,2})', lambda m: datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))),
        (r'(\d{1,2})/(\d{1,2})/(\d{4})', lambda m: datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)))),
        (r'(\d{1,2})-(\d{1,2})-(\d{4})', lambda m: datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)))),
    ]
    
    for pattern, parser in date_patterns:
        match = re.search(pattern, text)
        if match:
            try:
                date = parser(match)
                if date >= today:  # Only future dates
                    if date not in seen_dates:
                        seen_dates.add(date)
                        return date
            except (ValueError, IndexError):
                pass
    
    # Fallback: use index but ensure uniqueness
    fallback_date = today + timedelta(days=index)
    while fallback_date in seen_dates:
        index += 1
        fallback_date = today + timedelta(days=index)
    seen_dates.add(fallback_date)
    return fallback_date


def extract_forecast(html):
    """Extract daily and hourly forecast data with improved date parsing"""
    soup = BeautifulSoup(html, 'html.parser')
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    all_text = soup.get_text()
    
    daily_data = []
    hourly_data = []
    seen_dates = set()  # Track dates to avoid duplicates
    
    # Find all solar radiation totals - look for daily totals specifically
    # Pattern: "Total solar radiation:" followed by value and unit
    total_matches = list(re.finditer(
        r'Total\s+solar\s+radiation\s*:?\s*(\d+(?:\.\d+)?)\s*(wh|kwh|mj)\s*/?\s*m[²2]',
        all_text, re.IGNORECASE
    ))
    
    logger.info(f"Found {len(total_matches)} potential daily totals")
    
    # Also look for date headers in the HTML structure
    date_elements = soup.find_all(['h2', 'h3', 'h4', 'div', 'span'], 
                                  string=re.compile(r'(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|January|February|March|April|May|June|July|August|September|October|November|December|\d{1,2}[/-]\d{1,2})', re.IGNORECASE))
    
    # Create a mapping of positions to dates
    date_map = {}
    temp_seen = set()
    for elem in date_elements:
        text = elem.get_text()
        pos = all_text.find(text)
        if pos >= 0:
            parsed = parse_date(text, today, len(date_map), temp_seen)
            date_map[pos] = parsed
            seen_dates.add(parsed)
    
    # Track the last successfully parsed date for sequential fallback
    last_parsed_date = today - timedelta(days=1)  # Start one day before today
    
    for i, match in enumerate(total_matches):
        value = float(match.group(1))
        unit = match.group(2).lower()
        
        # Convert to kWh/m2
        if unit == 'kwh':
            value_kwh = value
        elif unit == 'mj':
            value_kwh = (value * 277.778) / 1000
        else:  # wh
            value_kwh = value / 1000
        
        # Get context for date parsing - look further back for date information
        context_start = max(0, match.start() - 3000)
        context = all_text[context_start:match.start()]
        
        # Try to find the closest date in the context
        parsed_date = None
        
        # First, check if there's a date element nearby
        match_pos = match.start()
        closest_date_pos = None
        closest_date = None
        for pos, date in date_map.items():
            if pos < match_pos and (closest_date_pos is None or pos > closest_date_pos):
                closest_date_pos = pos
                closest_date = date
        
        if closest_date:
            parsed_date = closest_date
        else:
            # Parse from context text - use last_parsed_date + 1 as fallback base
            fallback_index = max(0, (last_parsed_date - today).days + 1)
            parsed_date = parse_date(context, today, fallback_index, seen_dates)
        
        # Update last parsed date if this date is later
        if parsed_date > last_parsed_date:
            last_parsed_date = parsed_date
        
        # Always calculate day name from the parsed date (not from context)
        # This ensures accuracy - the date is the source of truth
        day_name = parsed_date.strftime('%A')
        
        # Only add if we haven't seen this date yet (or update existing)
        date_str = parsed_date.strftime('%Y-%m-%d')
        existing_idx = None
        for idx, record in enumerate(daily_data):
            if record['Date'] == date_str:
                existing_idx = idx
                break
        
        record = {
            'Date': date_str,
            'DayName': day_name,
            'SolarRadiation_kWh_m2': round(value_kwh, 6),
            'SolarRadiation_Wh_m2': round(value_kwh * 1000, 2),
            'Source': 'tutiempo.net',
            'FetchedAt': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        if existing_idx is not None:
            # Update existing record (keep the one with higher radiation value)
            if value_kwh > daily_data[existing_idx]['SolarRadiation_kWh_m2']:
                daily_data[existing_idx] = record
        else:
            daily_data.append(record)
        
        # Extract hourly data for this date
        hourly_section = context[-2000:] if len(context) > 2000 else context
        hourly_matches = re.finditer(r'(\d{1,2}):(\d{2})\s*(\d+(?:\.\d+)?)\s*w/m[²2]', hourly_section, re.IGNORECASE)
        
        for h_match in hourly_matches:
            hour_value = float(h_match.group(3))
            hourly_data.append({
                'Date': date_str,
                'Time': f"{int(h_match.group(1)):02d}:{h_match.group(2)}",
                'SolarRadiation_W_m2': round(hour_value, 2),
                'SolarRadiation_Wh_m2': round(hour_value, 2),
                'Source': 'tutiempo.net',
                'FetchedAt': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
    
    # Sort by date and remove any duplicates
    daily_data.sort(key=lambda x: x['Date'])
    seen = set()
    unique_daily_data = []
    for record in daily_data:
        if record['Date'] not in seen:
            seen.add(record['Date'])
            unique_daily_data.append(record)
    
    # Verify dates are sequential and fix day names if needed
    if unique_daily_data:
        for i, record in enumerate(unique_daily_data):
            try:
                date_obj = datetime.strptime(record['Date'], '%Y-%m-%d')
                # Recalculate day name from date to ensure accuracy
                record['DayName'] = date_obj.strftime('%A')
                
            except ValueError:
                pass
    
    return unique_daily_data, hourly_data


def calculate_battery_prognosis(daily_data, config):
    """Calculate battery charge prognosis using user-friendly config values."""
    panel_cfg = config.get('solar_panel', {})
    battery_cfg = config.get('battery', {})
    system_eff = config.get('system', {}).get('efficiency', 0.85)
    
    panel_count = panel_cfg.get('count', 1)
    per_panel_area = panel_cfg.get('area_per_panel_m2', panel_cfg.get('area_m2', 1.0))
    # Efficiency should come from the manufacturer's datasheet.
    # Accept either fraction (0.20) or percent-like input (20 -> 0.20).
    panel_eff_raw = panel_cfg.get('efficiency', 0.20)
    try:
        panel_eff = float(panel_eff_raw)
    except (TypeError, ValueError):
        panel_eff = 0.20
    if panel_eff > 1.0 and panel_eff <= 100.0:
        panel_eff = panel_eff / 100.0
    total_panel_area = per_panel_area * panel_count
    per_panel_yield_factor = per_panel_area * panel_eff * system_eff
    
    battery_count = battery_cfg.get('count', 1)
    cap_per_batt = battery_cfg.get('capacity_kwh_per_battery', battery_cfg.get('capacity_kwh', 10.0))
    max_rate_per_batt = battery_cfg.get('max_charge_rate_kw_per_battery', battery_cfg.get('max_charge_rate_kw', 5.0))
    total_battery_capacity = cap_per_batt * battery_count
    total_charge_rate_kw = max_rate_per_batt * battery_count
    
    prognosis = []
    
    for record in daily_data:
        solar_rad = record['SolarRadiation_kWh_m2']
        
        # Per-panel production for the day
        per_panel_prod = solar_rad * per_panel_yield_factor
        # Total production = per-panel * number of panels
        total_production = per_panel_prod * panel_count
        
        # Charge percentage (capped by battery capacity)
        charge_pct = (min(total_production, total_battery_capacity) / total_battery_capacity * 100) if total_battery_capacity > 0 else 0
        
        prognosis.append({
            **record,
            'PanelCount': panel_count,
            'TotalPanelArea_m2': round(total_panel_area, 3),
            'Production_kWh': round(total_production, 2),
            'BatteryCount': battery_count,
            'BatteryCapacity_kWh': round(total_battery_capacity, 1),
            'ChargePercentage': round(charge_pct, 1),
        })
    
    return prognosis


def run_pipeline(config=None):
    """Run complete pipeline: scrape -> calculate -> export"""
    if config is None:
        config = load_config()
    
    location = config['location']
    logger.info(f"")
    logger.info(f"Solar Pipeline - {location}")
    logger.info("=" * 50)
    
    # Find URL
    url = find_url(location, config['base_url'], config['fallback_url'])
    if not url:
        logger.error("Could not find URL for location")
        return False
    
    # Fetch HTML
    html = fetch_html(url, config['max_retries'], config['retry_delay'], config['timeout'])
    if not html:
        logger.error("Could not fetch forecast data")
        return False
    
    # Extract forecast
    daily_data, hourly_data = extract_forecast(html)
    if not daily_data:
        logger.error("No forecast data found")
        return False
    
    # Calculate prognosis
    prognosis_data = calculate_battery_prognosis(daily_data, config)
    cfg_hash = _config_hash(config)
    for rec in prognosis_data:
        rec["ConfigHash"] = cfg_hash
    
    # Write "latest snapshot" files (the GUI reads these).
    write_snapshot_csv(daily_data, EXTRACTED_DIR / "daily_forecast.csv")
    write_snapshot_csv(hourly_data, EXTRACTED_DIR / "hourly_detail.csv")
    write_snapshot_csv(prognosis_data, PROGNOSIS_DIR / "battery_prognosis.csv")

    # Append to history (no redundant duplicates).
    upsert_history_csv(
        daily_data,
        HISTORY_EXTRACTED_DIR / "daily_forecast.csv",
        dedupe_subset=["Date", "SolarRadiation_kWh_m2", "SolarRadiation_Wh_m2", "Source"],
        sort_by=["Date", "FetchedAt"],
    )
    upsert_history_csv(
        hourly_data,
        HISTORY_EXTRACTED_DIR / "hourly_detail.csv",
        dedupe_subset=["Date", "Time", "SolarRadiation_W_m2", "SolarRadiation_Wh_m2", "Source"],
        sort_by=["Date", "Time", "FetchedAt"],
    )
    # For prognosis we dedupe on all computed fields + config hash (excluding FetchedAt so identical runs don't re-add).
    upsert_history_csv(
        prognosis_data,
        HISTORY_PROGNOSIS_DIR / "battery_prognosis.csv",
        dedupe_subset=[
            "Date",
            "DayName",
            "SolarRadiation_kWh_m2",
            "SolarRadiation_Wh_m2",
            "Source",
            "PanelCount",
            "TotalPanelArea_m2",
            "Production_kWh",
            "BatteryCount",
            "BatteryCapacity_kWh",
            "ChargePercentage",
            "ConfigHash",
        ],
        sort_by=["Date", "FetchedAt", "ConfigHash"],
    )
    
    # Show results
    panel_cfg = config.get('solar_panel', {})
    battery_cfg = config.get('battery', {})
    
    logger.info(f"")
    logger.info(f"System: {panel_cfg.get('count', 1)} panels | {battery_cfg.get('count', 1)}x {battery_cfg.get('capacity_kwh_per_battery', 10)} kWh battery")
    logger.info(f"Forecast: {prognosis_data[0]['Date']} to {prognosis_data[-1]['Date']} ({len(prognosis_data)} days)")
    logger.info("-" * 50)
    logger.info(f"{'Date':<12} {'Day':<10} {'Solar':>8} {'Prod':>8} {'Charge':>8}")
    logger.info(f"{'':<12} {'':<10} {'kWh/m²':>8} {'kWh':>8} {'%':>8}")
    logger.info("-" * 50)
    
    total_production = 0
    for record in prognosis_data:
        total_production += record['Production_kWh']
        logger.info(f"{record['Date']:<12} {record['DayName']:<10} {record['SolarRadiation_kWh_m2']:>8.2f} {record['Production_kWh']:>8.2f} {record['ChargePercentage']:>7.1f}%")
    
    logger.info("-" * 50)
    avg_charge = sum(r['ChargePercentage'] for r in prognosis_data) / len(prognosis_data)
    best_day = max(prognosis_data, key=lambda x: x['ChargePercentage'])
    logger.info(f"Total production: {total_production:.1f} kWh | Avg charge: {avg_charge:.1f}%")
    logger.info(f"Best day: {best_day['Date']} ({best_day['DayName']}) - {best_day['ChargePercentage']:.1f}%")
    
    # Generate HTML report
    report_path = generate_html_report(prognosis_data, config, location)
    logger.info(f"Report: {report_path}")
    logger.info("=" * 50)
    
    return True
