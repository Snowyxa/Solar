"""
V3 - Battery Charge Prognosis: Solar Radiation Data Scraper + Battery Charge Calculation
Doel: Extract forecast data en bereken hoeveel batterijen kunnen opladen
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import re
import logging
import pandas as pd
from pathlib import Path
import time
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

# Configuratie
LOCATION = "Deinze"
BASE_URL_FALLBACK = "https://en.tutiempo.net/solar-radiation/deinze.html"
TUTIEMPO_BASE = "https://en.tutiempo.net"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}
MAX_RETRIES = 3
RETRY_DELAY = 2
TIMEOUT = 10
DATA_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")
CONFIG_FILE = Path("config.yaml")

# Default configuratie (wordt overschreven door config.yaml indien aanwezig)
DEFAULT_CONFIG = {
    'solar_panel': {
        'surface_area_m2': 10.0,  # m² paneel oppervlak
        'efficiency': 0.20,  # 20% efficiëntie
    },
    'system': {
        'system_efficiency': 0.85,  # 85% systeem efficiëntie (inverter, etc.)
    },
    'battery': {
        'capacity_kwh': 10.0,  # kWh batterij capaciteit
        'max_charge_rate_kw': 5.0,  # kW max laadsnelheid
    }
}

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('solar_scraper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def load_config():
    """Laad configuratie uit YAML bestand of gebruik defaults"""
    if CONFIG_FILE.exists() and HAS_YAML:
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = yaml.safe_load(f)
                logger.info(f"Configuratie geladen uit {CONFIG_FILE}")
                return {**DEFAULT_CONFIG, **config}  # Merge met defaults
        except Exception as e:
            logger.warning(f"Fout bij laden config: {e}, gebruik defaults")
    elif CONFIG_FILE.exists() and not HAS_YAML:
        logger.warning("config.yaml gevonden maar PyYAML niet geïnstalleerd. Gebruik defaults.")
        logger.info("Installeer PyYAML met: pip install pyyaml")
    else:
        logger.info("Geen config.yaml gevonden, gebruik default configuratie")
        if HAS_YAML:
            create_example_config()
        else:
            logger.info("Installeer PyYAML om config.yaml te kunnen gebruiken: pip install pyyaml")
    
    return DEFAULT_CONFIG


def create_example_config():
    """Maak een voorbeeld config.yaml bestand"""
    if not HAS_YAML:
        return
    
    example_config = """# Solar Panel & Battery Configuration
solar_panel:
  surface_area_m2: 10.0      # Oppervlak zonnepanelen in m²
  efficiency: 0.20            # Paneel efficiëntie (20% = 0.20)

system:
  system_efficiency: 0.85    # Totale systeem efficiëntie (inverter, verliezen, etc.)

battery:
  capacity_kwh: 10.0          # Batterij capaciteit in kWh
  max_charge_rate_kw: 5.0     # Maximale laadsnelheid in kW
"""
    try:
        with open(CONFIG_FILE, 'w') as f:
            f.write(example_config)
        logger.info(f"Voorbeeld configuratie aangemaakt: {CONFIG_FILE}")
        logger.info("Pas deze aan met jouw eigen waarden!")
    except Exception as e:
        logger.warning(f"Kon voorbeeld config niet aanmaken: {e}")


def fetch_html_with_retry(url, max_retries=MAX_RETRIES):
    """Download HTML pagina met retry logica"""
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Downloaden van: {url} (poging {attempt}/{max_retries})")
            response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            response.raise_for_status()
            logger.info(f"Successvol gedownload ({len(response.text)} bytes)")
            return response.text
        except requests.Timeout:
            logger.warning(f"Timeout bij poging {attempt}/{max_retries}")
            if attempt < max_retries:
                time.sleep(RETRY_DELAY * attempt)
        except requests.RequestException as e:
            logger.error(f"Fout bij ophalen (poging {attempt}/{max_retries}): {e}")
            if attempt < max_retries:
                time.sleep(RETRY_DELAY * attempt)
            else:
                logger.error(f"Alle {max_retries} pogingen mislukt")
    
    return None


def find_solar_radiation_url(location_name, fallback_url=None):
    """Zoek automatisch naar de solar radiation URL"""
    logger.info(f"Zoeken naar solar radiation URL voor: {location_name}")
    
    location_lower = location_name.lower().replace(' ', '-')
    possible_urls = [
        f"{TUTIEMPO_BASE}/solar-radiation/{location_lower}.html",
        f"{TUTIEMPO_BASE}/solar-radiation/{location_lower.replace('-', '_')}.html",
        f"{TUTIEMPO_BASE}/solar-radiation/{location_lower.replace('-', '')}.html",
    ]
    
    for url in possible_urls:
        logger.info(f"  Proberen: {url}")
        html = fetch_html_with_retry(url, max_retries=1)
        if html:
            if 'solar' in html.lower() or 'radiation' in html.lower():
                logger.info(f"  [OK] URL gevonden: {url}")
                return url
    
    if fallback_url:
        logger.warning(f"  Auto-detectie mislukt, gebruik fallback URL: {fallback_url}")
        return fallback_url
    
    logger.error(f"  Kon geen solar radiation URL vinden voor {location_name}")
    return None


def extract_daily_forecast(html):
    """Extract dagelijkse forecast data (vereenvoudigde versie van V2)"""
    soup = BeautifulSoup(html, 'html.parser')
    today = datetime.now()
    all_text = soup.get_text()
    
    daily_data = []
    all_total_matches = list(re.finditer(r'Total solar radiation:\s*(\d+(?:\.\d+)?)\s*(wh|kwh|mj)\s*/?\s*m[²2]', 
                                        all_text, re.IGNORECASE))
    
    logger.info(f"Gevonden {len(all_total_matches)} dagelijkse totalen")
    
    for i, total_match in enumerate(all_total_matches):
        value = float(total_match.group(1))
        unit = total_match.group(2).lower()
        
        # Convert naar kWh/m2
        if unit == 'kwh':
            value_kwh = value
        elif unit == 'mj':
            value_kwh = (value * 277.778) / 1000
        else:  # wh
            value_kwh = value / 1000
        
        # Bepaal datum (vereenvoudigd)
        parsed_date = today + timedelta(days=i)
        
        daily_data.append({
            'Date': parsed_date.strftime('%Y-%m-%d'),
            'SolarRadiation_kWh_m2': value_kwh,
            'SolarRadiation_Wh_m2': value_kwh * 1000,
            'Source': 'tutiempo.net',
            'FetchedAt': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
    
    return daily_data


def calculate_battery_charge(solar_radiation_kwh_m2, config):
    """
    Bereken hoeveel energie de batterij kan opladen op basis van solar radiation.
    
    Formule:
    Opbrengst (kWh) = SolarRadiation_kWh_m2 × PaneelOppervlak_m2 × PaneelEfficiëntie × SysteemEfficiëntie
    Batterij Oplaad = min(Opbrengst, BatterijCapaciteit, MaxChargeRate × Uren)
    """
    panel_area = config['solar_panel']['surface_area_m2']
    panel_eff = config['solar_panel']['efficiency']
    system_eff = config['system']['system_efficiency']
    battery_capacity = config['battery']['capacity_kwh']
    max_charge_rate = config['battery']['max_charge_rate_kw']
    
    # Bereken totale opbrengst
    total_yield_kwh = solar_radiation_kwh_m2 * panel_area * panel_eff * system_eff
    
    # Batterij kan maximaal de capaciteit opladen
    # En is beperkt door max charge rate (aanname: 8 uur laadtijd per dag)
    max_chargeable = min(
        battery_capacity,  # Max batterij capaciteit
        max_charge_rate * 8,  # Max laadsnelheid × uren (vereenvoudigd)
        total_yield_kwh  # Totale opbrengst
    )
    
    # Percentage van batterij dat opgeladen kan worden
    charge_percentage = (max_chargeable / battery_capacity) * 100 if battery_capacity > 0 else 0
    
    return {
        'TotalYield_kWh': round(total_yield_kwh, 3),
        'Chargeable_kWh': round(max_chargeable, 3),
        'ChargePercentage': round(charge_percentage, 1),
        'BatteryCapacity_kWh': battery_capacity,
        'MaxChargeRate_kW': max_charge_rate
    }


def process_forecast_data(daily_data, config):
    """Process forecast data en bereken batterij oplaad prognose"""
    processed_data = []
    
    for record in daily_data:
        solar_rad = record['SolarRadiation_kWh_m2']
        charge_calc = calculate_battery_charge(solar_rad, config)
        
        processed_record = {
            **record,  # Originele data
            **charge_calc  # Batterij berekeningen
        }
        processed_data.append(processed_record)
    
    return processed_data


def save_processed_data(processed_data, output_file):
    """Sla processed data op in CSV"""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    
    df = pd.DataFrame(processed_data)
    df.to_csv(output_file, index=False)
    logger.info(f"Processed data opgeslagen in {output_file} ({len(df)} records)")


def main():
    """Main functie voor V3 battery prognosis scraper"""
    logger.info("=" * 60)
    logger.info("V3 - Battery Charge Prognosis Scraper voor Deinze")
    logger.info("=" * 60)
    
    # Laad configuratie
    config = load_config()
    logger.info(f"Configuratie:")
    logger.info(f"  Paneel oppervlak: {config['solar_panel']['surface_area_m2']} m²")
    logger.info(f"  Paneel efficiëntie: {config['solar_panel']['efficiency']*100:.1f}%")
    logger.info(f"  Systeem efficiëntie: {config['system']['system_efficiency']*100:.1f}%")
    logger.info(f"  Batterij capaciteit: {config['battery']['capacity_kwh']} kWh")
    logger.info(f"  Max laadsnelheid: {config['battery']['max_charge_rate_kw']} kW")
    
    # Zoek URL
    target_url = find_solar_radiation_url(LOCATION, BASE_URL_FALLBACK)
    if not target_url:
        logger.error("Kon geen geldige URL vinden. Script gestopt.")
        return
    
    # Download HTML
    html = fetch_html_with_retry(target_url)
    if not html:
        logger.error("Kon geen HTML ophalen. Script gestopt.")
        return
    
    # Extract forecast data
    logger.info("Zoeken naar solar radiation forecast data...")
    daily_data = extract_daily_forecast(html)
    
    if not daily_data:
        logger.warning("Geen solar radiation waarden gevonden")
        return
    
    logger.info(f"Gevonden {len(daily_data)} dagelijkse record(s)")
    
    # Process data en bereken batterij oplaad
    logger.info("Berekenen batterij oplaad prognose...")
    processed_data = process_forecast_data(daily_data, config)
    
    # Toon resultaten
    logger.info("\n" + "=" * 60)
    logger.info("BATTERIJ OPLAAD PROGNOSE")
    logger.info("=" * 60)
    for record in processed_data[:7]:  # Toon eerste 7 dagen
        logger.info(f"{record['Date']}: "
                   f"{record['SolarRadiation_kWh_m2']:.3f} kWh/m2 -> "
                   f"{record['TotalYield_kWh']:.2f} kWh opbrengst -> "
                   f"{record['Chargeable_kWh']:.2f} kWh oplaadbaar "
                   f"({record['ChargePercentage']:.1f}% van {record['BatteryCapacity_kWh']:.1f} kWh)")
    
    # Sla op
    output_file = PROCESSED_DIR / "battery_prognosis.csv"
    save_processed_data(processed_data, output_file)
    
    logger.info("=" * 60)
    logger.info("V3 Scraper voltooid")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
