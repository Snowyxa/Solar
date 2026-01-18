"""Solar Pipeline - Solar Radiation Scraper & Battery Prognosis Calculator"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import re
import logging
import pandas as pd
from pathlib import Path
import time
from .config import load_config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('solar_pipeline.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

DATA_DIR = Path("data")
EXPORT_DIR = DATA_DIR / "exports"


def fetch_html(url, max_retries, retry_delay, timeout):
    """Fetch HTML with retry logic"""
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Fetching: {url} (attempt {attempt}/{max_retries})")
            response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=timeout)
            response.raise_for_status()
            logger.info(f"Success ({len(response.text)} bytes)")
            return response.text
        except requests.RequestException as e:
            logger.warning(f"Attempt {attempt} failed: {e}")
            if attempt < max_retries:
                time.sleep(retry_delay * attempt)
    
    logger.error(f"All {max_retries} attempts failed")
    return None


def find_url(location, base_url, fallback_url):
    """Find solar radiation URL for location"""
    logger.info(f"Finding URL for {location}")
    
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


def parse_date(text, today, index):
    """Parse date from text"""
    text = text.lower()
    
    if 'today' in text:
        return today
    if 'tomorrow' in text:
        return today + timedelta(days=1)
    
    months = {'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
              'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12}
    
    for month_name, month_num in months.items():
        if month_name in text:
            match = re.search(r'(\d{1,2})', text)
            if match:
                day = int(match.group(1))
                year = today.year if month_num >= today.month else today.year + 1
                try:
                    return datetime(year, month_num, day)
                except ValueError:
                    pass
    
    return today + timedelta(days=index)


def extract_forecast(html):
    """Extract daily and hourly forecast data"""
    soup = BeautifulSoup(html, 'html.parser')
    today = datetime.now()
    all_text = soup.get_text()
    
    daily_data = []
    hourly_data = []
    
    # Find all solar radiation totals
    total_matches = list(re.finditer(
        r'Total solar radiation:\s*(\d+(?:\.\d+)?)\s*(wh|kwh|mj)\s*/?\s*m[²2]',
        all_text, re.IGNORECASE
    ))
    
    logger.info(f"Found {len(total_matches)} daily totals")
    
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
        
        # Get context for date parsing
        context_start = max(0, match.start() - 2500)
        context = all_text[context_start:match.start()]
        
        parsed_date = parse_date(context, today, i)
        
        # Get day name
        day_match = re.search(r'\b(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b', context, re.IGNORECASE)
        day_name = day_match.group(1) if day_match else parsed_date.strftime('%A')
        
        daily_data.append({
            'Date': parsed_date.strftime('%Y-%m-%d'),
            'DayName': day_name,
            'SolarRadiation_kWh_m2': round(value_kwh, 6),
            'SolarRadiation_Wh_m2': round(value_kwh * 1000, 2),
            'Source': 'tutiempo.net',
            'FetchedAt': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        
        # Extract hourly data
        hourly_section = context[-1500:] if len(context) > 1500 else context
        hourly_matches = re.finditer(r'(\d{1,2}):(\d{2})\s*(\d+(?:\.\d+)?)\s*w/m[²2]', hourly_section, re.IGNORECASE)
        
        for h_match in hourly_matches:
            hour_value = float(h_match.group(3))
            hourly_data.append({
                'Date': parsed_date.strftime('%Y-%m-%d'),
                'Time': f"{int(h_match.group(1)):02d}:{h_match.group(2)}",
                'SolarRadiation_W_m2': round(hour_value, 2),
                'SolarRadiation_Wh_m2': round(hour_value, 2),
                'Source': 'tutiempo.net',
                'FetchedAt': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
    
    logger.info(f"Extracted {len(daily_data)} daily and {len(hourly_data)} hourly records")
    return daily_data, hourly_data


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
        
        # Per-panel yield for the day
        per_panel_yield = solar_rad * per_panel_yield_factor
        # Fleet-wide yield = per-panel yield * number of panels
        total_yield = per_panel_yield * panel_count
        
        # Battery chargeable energy capped by capacity and charge rate (assume ~8h effective charging)
        chargeable = min(total_battery_capacity, total_charge_rate_kw * 8, total_yield)
        charge_pct = (chargeable / total_battery_capacity * 100) if total_battery_capacity > 0 else 0
        
        prognosis.append({
            **record,
            'PanelCount': panel_count,
            'TotalPanelArea_m2': round(total_panel_area, 3),
            'PerPanelYield_kWh': round(per_panel_yield, 6),
            'TotalYield_kWh': round(total_yield, 6),
            'BatteryCount': battery_count,
            'BatteryCapacityTotal_kWh': round(total_battery_capacity, 6),
            'TotalChargeRate_kW': round(total_charge_rate_kw, 3),
            'Chargeable_kWh': round(chargeable, 6),
            'ChargePercentage': round(charge_pct, 2),
        })
    
    return prognosis


def save_csv(data, filename, overwrite=False):
    """Save data to CSV"""
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    filepath = EXPORT_DIR / filename
    
    if not data:
        logger.warning(f"No data to save for {filename}")
        return False
    
    df = pd.DataFrame(data)
    
    if filepath.exists() and not overwrite:
        # Append without duplicates
        existing = pd.read_csv(filepath)
        df = pd.concat([existing, df]).drop_duplicates(subset=['Date'], keep='last')
    
    df.to_csv(filepath, index=False)
    logger.info(f"Saved {len(df)} records to {filepath.name}")
    return True


def run_pipeline(config=None):
    """Run complete pipeline: scrape -> calculate -> export"""
    if config is None:
        config = load_config()
    
    logger.info("=" * 60)
    logger.info("SOLAR PIPELINE - COMPLETE WORKFLOW")
    logger.info("=" * 60)
    
    # Find URL
    url = find_url(config['location'], config['base_url'], config['fallback_url'])
    if not url:
        logger.error("Could not find URL")
        return False
    
    # Fetch HTML
    html = fetch_html(url, config['max_retries'], config['retry_delay'], config['timeout'])
    if not html:
        logger.error("Could not fetch HTML")
        return False
    
    # Extract forecast
    daily_data, hourly_data = extract_forecast(html)
    if not daily_data:
        logger.warning("No data extracted")
        return False
    
    # Calculate prognosis
    prognosis_data = calculate_battery_prognosis(daily_data, config)
    
    # Export CSVs
    save_csv(daily_data, 'daily_forecast.csv', overwrite=True)
    save_csv(hourly_data, 'hourly_detail.csv', overwrite=True)
    save_csv(prognosis_data, 'battery_prognosis.csv', overwrite=True)
    
    # Show results
    logger.info("\nBattery Charge Prognosis (first 7 days):")
    logger.info("-" * 60)
    for record in prognosis_data[:7]:
        logger.info(f"{record['Date']}: {record['SolarRadiation_kWh_m2']:.3f} kWh/m2 -> "
                   f"{record['ChargePercentage']:.1f}% charge")
    
    logger.info("=" * 60)
    logger.info("PIPELINE COMPLETED")
    logger.info("=" * 60)
    
    return True
