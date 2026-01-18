"""
V1 - Daily Scraper + Opslag: Solar Radiation Data Scraper voor Deinze
Doel: Stabiele datacollectie met retries, logging en CSV opslag
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import re
import logging
import os
import pandas as pd
from pathlib import Path
import time

# Configuratie
LOCATION = "Deinze"  # Locatie naam voor auto-detectie
BASE_URL_FALLBACK = "https://en.tutiempo.net/solar-radiation/deinze.html"  # Fallback URL
TUTIEMPO_BASE = "https://en.tutiempo.net"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconden
TIMEOUT = 10
DATA_DIR = Path("data/raw")
CSV_FILE = DATA_DIR / "solar_deinze.csv"

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


def fetch_html_with_retry(url, max_retries=MAX_RETRIES):
    """
    Download HTML pagina met retry logica
    """
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
                time.sleep(RETRY_DELAY * attempt)  # Exponential backoff
        except requests.RequestException as e:
            logger.error(f"Fout bij ophalen (poging {attempt}/{max_retries}): {e}")
            if attempt < max_retries:
                time.sleep(RETRY_DELAY * attempt)
            else:
                logger.error(f"Alle {max_retries} pogingen mislukt")
    
    return None


def find_solar_radiation_url(location_name, fallback_url=None):
    """
    Zoek automatisch naar de solar radiation URL voor een locatie.
    Probeert verschillende strategieën om de juiste URL te vinden.
    """
    logger.info(f"Zoeken naar solar radiation URL voor: {location_name}")
    
    # Strategie 1: Probeer directe URL constructie (meest voorkomende formaten)
    location_lower = location_name.lower().replace(' ', '-')
    possible_urls = [
        f"{TUTIEMPO_BASE}/solar-radiation/{location_lower}.html",
        f"{TUTIEMPO_BASE}/solar-radiation/{location_lower.replace('-', '_')}.html",
        f"{TUTIEMPO_BASE}/solar-radiation/{location_lower.replace('-', '')}.html",
    ]
    
    for url in possible_urls:
        logger.info(f"  Proberen: {url}")
        html = fetch_html_with_retry(url, max_retries=1)  # Snelle check
        if html:
            # Verifieer dat het een solar radiation pagina is
            if 'solar' in html.lower() or 'radiation' in html.lower():
                logger.info(f"  ✓ URL gevonden: {url}")
                return url
            else:
                logger.debug(f"  ✗ Geen solar radiation data op deze pagina")
    
    # Strategie 2: Zoek via zoekpagina of index
    logger.info("  Zoeken via tutiempo.net zoekfunctie...")
    search_urls = [
        f"{TUTIEMPO_BASE}/climate/{location_lower}.html",
        f"{TUTIEMPO_BASE}/weather/{location_lower}.html",
    ]
    
    for search_url in search_urls:
        html = fetch_html_with_retry(search_url, max_retries=1)
        if html:
            soup = BeautifulSoup(html, 'html.parser')
            # Zoek naar links met "solar" en "radiation"
            links = soup.find_all('a', href=True)
            for link in links:
                href = link.get('href', '')
                text = link.get_text().lower()
                if 'solar' in text or 'radiation' in text or '/solar-radiation/' in href:
                    # Maak absolute URL
                    if href.startswith('http'):
                        found_url = href
                    elif href.startswith('/'):
                        found_url = f"{TUTIEMPO_BASE}{href}"
                    else:
                        found_url = f"{search_url.rsplit('/', 1)[0]}/{href}"
                    
                    logger.info(f"  ✓ Link gevonden: {found_url}")
                    # Verifieer de gevonden URL
                    verify_html = fetch_html_with_retry(found_url, max_retries=1)
                    if verify_html and ('solar' in verify_html.lower() or 'radiation' in verify_html.lower()):
                        return found_url
    
    # Strategie 3: Zoek in alle links op de hoofdpagina
    logger.info("  Zoeken op tutiempo.net hoofdpagina...")
    main_page = fetch_html_with_retry(f"{TUTIEMPO_BASE}", max_retries=1)
    if main_page:
        soup = BeautifulSoup(main_page, 'html.parser')
        links = soup.find_all('a', href=True)
        for link in links:
            href = link.get('href', '')
            text = link.get_text().lower()
            # Zoek naar links die zowel de locatie als solar radiation bevatten
            if location_name.lower() in text and ('solar' in text or '/solar-radiation/' in href):
                if href.startswith('http'):
                    found_url = href
                elif href.startswith('/'):
                    found_url = f"{TUTIEMPO_BASE}{href}"
                else:
                    continue
                
                logger.info(f"  ✓ Mogelijke URL gevonden: {found_url}")
                verify_html = fetch_html_with_retry(found_url, max_retries=1)
                if verify_html:
                    return found_url
    
    # Fallback: gebruik de opgegeven fallback URL
    if fallback_url:
        logger.warning(f"  Auto-detectie mislukt, gebruik fallback URL: {fallback_url}")
        return fallback_url
    
    logger.error(f"  Kon geen solar radiation URL vinden voor {location_name}")
    return None


def extract_solar_radiation_daily_values(html):
    """
    Extract alle dagwaarden voor solar radiation uit de HTML
    Retourneert lijst van dicts met Date en SolarRadiation_kWh_m2
    """
    soup = BeautifulSoup(html, 'html.parser')
    results = []
    today = datetime.now()
    
    # Zoek naar alle solar radiation waarden in de tekst
    all_text = soup.get_text()
    
    # Patroon voor solar radiation: "579wh/m2" of "579 wh/m2" etc.
    patterns = [
        r'(\d+(?:\.\d+)?)\s*(?:wh|kwh|mj)\s*/?\s*m[²2]',
        r'(\d+(?:\.\d+)?)\s*(?:wh|kwh|mj)\s*/?\s*m\^?2',
    ]
    
    # Zoek naar unieke matches (voorkom duplicaten)
    seen_values = set()
    all_matches = []
    
    for pattern in patterns:
        matches = re.finditer(pattern, all_text, re.IGNORECASE)
        for match in matches:
            # Gebruik positie in tekst om duplicaten te voorkomen
            match_key = (match.start(), match.end())
            if match_key in seen_values:
                continue
            seen_values.add(match_key)
            
            value = float(match.group(1))
            # Check of het wh/m2 of kwh/m2 is (standaard wh/m2)
            unit_text = match.group(0).lower()
            if 'kwh' in unit_text:
                # Convert kWh/m2 to Wh/m2
                value = value * 1000
            elif 'mj' in unit_text:
                # Convert MJ/m2 to Wh/m2 (1 MJ = 277.778 Wh)
                value = value * 277.778
            
            # Convert to kWh/m2 voor opslag
            value_kwh = value / 1000
            
            all_matches.append({
                'value': value_kwh,
                'raw_text': match.group(0),
                'position': match.start()
            })
    
    # Sorteer op positie in tekst (eerste match = eerste dag)
    all_matches.sort(key=lambda x: x['position'])
    
    logger.info(f"Gevonden {len(all_matches)} unieke solar radiation waarde(n)")
    
    # Als we waarden hebben, koppel ze aan datums
    # Neem de eerste waarde als vandaag
    if all_matches:
        # Neem alleen de eerste unieke waarde voor vandaag
        # (De pagina toont meestal de huidige dagwaarde)
        results.append({
            'Date': today.strftime('%Y-%m-%d'),
            'SolarRadiation_kWh_m2': all_matches[0]['value'],
            'Source': 'tutiempo.net',
            'FetchedAt': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        
        logger.info(f"  {today.strftime('%Y-%m-%d')}: {all_matches[0]['value']:.3f} kWh/m²")
    else:
        # Fallback: zoek in tabellen
        tables = soup.find_all('table')
        for i, table in enumerate(tables):
            headers = table.find_all(['th', 'td'])
            for header in headers:
                text = header.get_text().strip().lower()
                if 'solar' in text or 'radiation' in text or 'radiación' in text:
                    row = header.find_parent('tr')
                    if row:
                        cells = row.find_all(['td', 'th'])
                        for cell_text in [c.get_text().strip() for c in cells]:
                            match = re.search(r'(\d+(?:\.\d+)?)', cell_text)
                            if match:
                                value = float(match.group(1))
                                # Assume Wh/m2, convert to kWh/m2
                                value_kwh = value / 1000
                                results.append({
                                    'Date': today.strftime('%Y-%m-%d'),
                                    'SolarRadiation_kWh_m2': value_kwh,
                                    'Source': 'tutiempo.net',
                                    'FetchedAt': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                })
                                logger.info(f"  {today.strftime('%Y-%m-%d')}: {value_kwh:.3f} kWh/m² (uit tabel)")
                                break
    
    return results


def load_existing_data():
    """
    Laad bestaande CSV data om duplicaten te voorkomen
    """
    if CSV_FILE.exists():
        try:
            df = pd.read_csv(CSV_FILE)
            logger.info(f"Bestaande data geladen: {len(df)} records")
            return df
        except Exception as e:
            logger.warning(f"Fout bij laden bestaande data: {e}")
            return pd.DataFrame()
    else:
        logger.info("Geen bestaande data gevonden")
        return pd.DataFrame()


def save_to_csv(new_data, existing_df=None):
    """
    Sla nieuwe data op in CSV, voorkom duplicaten
    """
    # Maak directory aan als die niet bestaat
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    # Converteer nieuwe data naar DataFrame
    if not new_data:
        logger.warning("Geen nieuwe data om op te slaan")
        return
    
    new_df = pd.DataFrame(new_data)
    
    # Combineer met bestaande data
    if existing_df is not None and not existing_df.empty:
        # Voeg alleen nieuwe records toe (geen duplicaten op basis van Date)
        existing_dates = set(existing_df['Date'].astype(str))
        new_df_filtered = new_df[~new_df['Date'].isin(existing_dates)]
        
        if new_df_filtered.empty:
            logger.info("Geen nieuwe records om toe te voegen (alle datums bestaan al)")
            return
        
        logger.info(f"Toevoegen van {len(new_df_filtered)} nieuwe record(s)")
        combined_df = pd.concat([existing_df, new_df_filtered], ignore_index=True)
    else:
        logger.info(f"Opslaan van {len(new_df)} nieuwe record(s)")
        combined_df = new_df
    
    # Sorteer op datum
    combined_df = combined_df.sort_values('Date')
    
    # Sla op
    combined_df.to_csv(CSV_FILE, index=False)
    logger.info(f"Data opgeslagen in {CSV_FILE} ({len(combined_df)} totaal records)")


def main():
    """
    Main functie voor V1 daily scraper
    """
    logger.info("=" * 60)
    logger.info("V1 - Solar Radiation Data Scraper voor Deinze")
    logger.info("=" * 60)
    
    # Laad bestaande data
    existing_df = load_existing_data()
    
    # Zoek automatisch de juiste URL
    target_url = find_solar_radiation_url(LOCATION, BASE_URL_FALLBACK)
    
    if not target_url:
        logger.error("Kon geen geldige URL vinden. Script gestopt.")
        return
    
    # Download HTML
    html = fetch_html_with_retry(target_url)
    
    if not html:
        logger.error("Kon geen HTML ophalen. Script gestopt.")
        return
    
    # Extract solar radiation waarden
    logger.info("Zoeken naar solar radiation data...")
    daily_values = extract_solar_radiation_daily_values(html)
    
    if not daily_values:
        logger.warning("Geen solar radiation waarden gevonden")
        return
    
    logger.info(f"Gevonden {len(daily_values)} dagwaarde(n)")
    for value in daily_values:
        logger.info(f"  {value['Date']}: {value['SolarRadiation_kWh_m2']:.3f} kWh/m²")
    
    # Sla op in CSV
    save_to_csv(daily_values, existing_df)
    
    logger.info("=" * 60)
    logger.info("V1 Scraper voltooid")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
