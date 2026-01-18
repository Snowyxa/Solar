"""
V2 - Detailed Forecast Scraper: Solar Radiation Data Scraper voor Deinze
Doel: Extract 15-day forecast met dagelijkse totalen en uurlijkse breakdowns
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import re
import logging
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
DAILY_CSV = DATA_DIR / "solar_daily_summary.csv"
HOURLY_CSV = DATA_DIR / "solar_hourly_detail.csv"

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
                logger.info(f"  [OK] URL gevonden: {url}")
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
                    
                    logger.info(f"  [OK] Link gevonden: {found_url}")
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
                
                logger.info(f"  [OK] Mogelijke URL gevonden: {found_url}")
                verify_html = fetch_html_with_retry(found_url, max_retries=1)
                if verify_html:
                    return found_url
    
    # Fallback: gebruik de opgegeven fallback URL
    if fallback_url:
        logger.warning(f"  Auto-detectie mislukt, gebruik fallback URL: {fallback_url}")
        return fallback_url
    
    logger.error(f"  Kon geen solar radiation URL vinden voor {location_name}")
    return None


def parse_date_from_text(day_text, base_date):
    """
    Parse datum uit tekst zoals "Today", "Tomorrow", "Monday, January 19", etc.
    """
    day_text = day_text.strip()
    today = base_date
    
    # Check voor "Today"
    if 'today' in day_text.lower():
        return today
    
    # Check voor "Tomorrow"
    if 'tomorrow' in day_text.lower():
        return today + timedelta(days=1)
    
    # Probeer datum te parsen uit tekst zoals "Monday, January 19" of "January 17"
    # Zoek naar maand en dag
    month_names = {
        'january': 1, 'february': 2, 'march': 3, 'april': 4,
        'may': 5, 'june': 6, 'july': 7, 'august': 8,
        'september': 9, 'october': 10, 'november': 11, 'december': 12
    }
    
    for month_name, month_num in month_names.items():
        if month_name in day_text.lower():
            # Zoek naar dag nummer
            day_match = re.search(r'(\d{1,2})', day_text)
            if day_match:
                day = int(day_match.group(1))
                # Probeer jaar te bepalen (gebruik huidige jaar, of volgend jaar als maand al voorbij is)
                year = today.year
                if month_num < today.month or (month_num == today.month and day < today.day):
                    year = today.year + 1
                try:
                    return datetime(year, month_num, day)
                except ValueError:
                    pass
    
    # Fallback: als we niets kunnen parsen, gebruik vandaag + offset gebaseerd op positie
    return None


def extract_detailed_forecast(html):
    """
    Extract gedetailleerde 15-day forecast met dagelijkse totalen en uurlijkse breakdowns.
    Retourneert tuple: (daily_data, hourly_data)
    
    Structuur op pagina:
    - Day name (Today/Tomorrow/Monday, etc.)
    - Date (January 17)
    - Sunrise/Sunset (8:43 17:08)
    - Daily total (579 wh/m2)
    - "Hourly forecast"
    - Hourly values (09:00 1 w/m2, 10:00 24 w/m2, etc.)
    - "Total solar radiation: 579 wh/m2."
    """
    soup = BeautifulSoup(html, 'html.parser')
    today = datetime.now()
    
    daily_data = []
    hourly_data = []
    
    all_text = soup.get_text()
    
    # Zoek alle "Total solar radiation:" matches met hun posities
    all_total_matches = list(re.finditer(r'Total solar radiation:\s*(\d+(?:\.\d+)?)\s*(wh|kwh|mj)\s*/?\s*m[²2]', 
                                        all_text, re.IGNORECASE))
    
    logger.info(f"Gevonden {len(all_total_matches)} dagelijkse totalen")
    
    for i, total_match in enumerate(all_total_matches):
        # Extract waarde
        value = float(total_match.group(1))
        unit = total_match.group(2).lower()
        
        # Convert naar kWh/m2
        if unit == 'kwh':
            value_kwh = value
        elif unit == 'mj':
            value_kwh = (value * 277.778) / 1000
        else:  # wh
            value_kwh = value / 1000
        
        # Zoek context voor deze "Total" match (2000 karakters terug)
        match_start = total_match.start()
        context_start = max(0, match_start - 2500)
        context_text = all_text[context_start:match_start]
        
        # Zoek naar dag naam (Today, Tomorrow, Monday, etc.) - zoek de MEEST RECENTE
        day_matches = list(re.finditer(r'\b(Today|Tomorrow|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b', 
                                      context_text, re.IGNORECASE))
        day_name = None
        if day_matches:
            # Neem de laatste (meest recente) match
            day_name = day_matches[-1].group(1)
        
        # Zoek naar datum (January 17, etc.) - zoek de MEEST RECENTE
        date_matches = list(re.finditer(r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})\b', 
                                        context_text, re.IGNORECASE))
        
        parsed_date = None
        if day_name:
            # Parse datum op basis van dag naam
            if day_name.lower() == 'today':
                parsed_date = today
            elif day_name.lower() == 'tomorrow':
                parsed_date = today + timedelta(days=1)
            else:
                # Zoek welke dag van de week het is
                day_offset = i  # Gebruik index als fallback
                parsed_date = today + timedelta(days=day_offset)
        elif date_matches:
            # Parse datum op basis van maand en dag
            month_name = date_matches[-1].group(1)
            day_num = int(date_matches[-1].group(2))
            month_names = {
                'january': 1, 'february': 2, 'march': 3, 'april': 4,
                'may': 5, 'june': 6, 'july': 7, 'august': 8,
                'september': 9, 'october': 10, 'november': 11, 'december': 12
            }
            if month_name.lower() in month_names:
                month_num = month_names[month_name.lower()]
                year = today.year
                try:
                    test_date = datetime(year, month_num, day_num)
                    if test_date < today:
                        year = today.year + 1
                    parsed_date = datetime(year, month_num, day_num)
                except ValueError:
                    pass
        
        # Fallback: gebruik index
        if not parsed_date:
            parsed_date = today + timedelta(days=i)
        
        # Zoek naar sunrise/sunset tijden
        # Format op pagina: "January 188:4217:10" waar "18" de dag is, "8:42" sunrise, "17:10" sunset
        # Probleem: "188:42" wordt gematcht, maar we willen alleen "8:42" en "17:10"
        # Oplossing: zoek naar alle tijd patronen en filter op geldige uren (0-23)
        sunrise = None
        sunset = None
        
        # Zoek alle tijd patronen HH:MM in de context
        all_time_matches = list(re.finditer(r'(\d{1,2}):(\d{2})', context_text))
        valid_times = []
        for match in all_time_matches:
            hour = int(match.group(1))
            minute = int(match.group(2))
            # Alleen geldige tijden (0-23 uur, 0-59 minuten)
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                valid_times.append((match.start(), f"{hour:02d}:{match.group(2)}"))
        
        # Neem de laatste twee geldige tijden (meest waarschijnlijk sunrise/sunset)
        if len(valid_times) >= 2:
            # Check of ze dicht bij elkaar staan (binnen 50 karakters)
            last_two = valid_times[-2:]
            if last_two[1][0] - last_two[0][0] < 50:  # Binnen 50 karakters van elkaar
                sunrise = last_two[0][1]
                sunset = last_two[1][1]
        elif len(valid_times) >= 1:
            # Alleen één tijd gevonden, gebruik die als sunrise (sunset komt later)
            sunrise = valid_times[-1][1]
        
        daily_data.append({
            'Date': parsed_date.strftime('%Y-%m-%d'),
            'DayName': day_name or parsed_date.strftime('%A'),
            'SolarRadiation_kWh_m2': value_kwh,
            'SolarRadiation_Wh_m2': value_kwh * 1000,
            'Sunrise': sunrise,
            'Sunset': sunset,
            'Source': 'tutiempo.net',
            'FetchedAt': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        
        # Zoek naar hourly data - kijk in de tekst VOOR deze "Total" match
        # Format: "Hourly forecast09:004 w/m210:0061 w/m2..." (geen spaties)
        hourly_section = ""
        if 'Hourly forecast' in context_text:
            # Vind "Hourly forecast" en neem tekst erna tot aan "Total solar radiation:"
            hourly_start_idx = context_text.rfind('Hourly forecast')
            if hourly_start_idx != -1:
                hourly_start = hourly_start_idx + len('Hourly forecast')
                # Neem tekst tot aan "Total solar radiation:" of 2000 karakters
                hourly_end = context_text.find('Total solar radiation:', hourly_start)
                if hourly_end == -1:
                    hourly_section = context_text[hourly_start:hourly_start + 2000]
                else:
                    hourly_section = context_text[hourly_start:hourly_end]
        else:
            # Fallback: zoek direct naar hourly patterns in context (laatste 1500 karakters)
            hourly_section = context_text[-1500:] if len(context_text) > 1500 else context_text
        
        # Extract alle hourly waarden - format kan zijn "09:004 w/m2" (geen spatie) of "09:00 4 w/m2"
        hourly_matches = re.finditer(r'(\d{1,2}):(\d{2})\s*(\d+(?:\.\d+)?)\s*w/m[²2]', hourly_section, re.IGNORECASE)
        
        for hour_match in hourly_matches:
            hour = int(hour_match.group(1))
            minute = int(hour_match.group(2))
            hour_value = float(hour_match.group(3))  # w/m2
            
            hourly_data.append({
                'Date': parsed_date.strftime('%Y-%m-%d'),
                'Time': f"{hour:02d}:{minute:02d}",
                'SolarRadiation_W_m2': hour_value,
                'SolarRadiation_Wh_m2': hour_value,  # w/m2 = wh/m2 per uur
                'Source': 'tutiempo.net',
                'FetchedAt': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
    
    logger.info(f"Gevonden {len(daily_data)} dagelijkse records en {len(hourly_data)} uurlijkse records")
    
    return daily_data, hourly_data


def load_existing_data(csv_file):
    """
    Laad bestaande CSV data om duplicaten te voorkomen
    """
    if csv_file.exists():
        try:
            df = pd.read_csv(csv_file)
            logger.info(f"Bestaande data geladen: {len(df)} records uit {csv_file.name}")
            return df
        except Exception as e:
            logger.warning(f"Fout bij laden bestaande data: {e}")
            return pd.DataFrame()
    else:
        logger.info(f"Geen bestaande data gevonden voor {csv_file.name}")
        return pd.DataFrame()


def save_to_csv(new_data, csv_file, existing_df=None, date_key='Date'):
    """
    Sla nieuwe data op in CSV, voorkom duplicaten
    """
    # Maak directory aan als die niet bestaat
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    # Converteer nieuwe data naar DataFrame
    if not new_data:
        logger.warning(f"Geen nieuwe data om op te slaan in {csv_file.name}")
        return
    
    new_df = pd.DataFrame(new_data)
    
    # Combineer met bestaande data
    if existing_df is not None and not existing_df.empty:
        # Voor hourly data, gebruik Date+Time als unieke key
        if 'Time' in new_df.columns:
            existing_df['Date_Time'] = existing_df[date_key].astype(str) + ' ' + existing_df['Time'].astype(str)
            new_df['Date_Time'] = new_df[date_key].astype(str) + ' ' + new_df['Time'].astype(str)
            existing_times = set(existing_df['Date_Time'].astype(str))
            new_df_filtered = new_df[~new_df['Date_Time'].isin(existing_times)]
            new_df_filtered = new_df_filtered.drop('Date_Time', axis=1)
        else:
            # Voor daily data, gebruik alleen Date
            existing_dates = set(existing_df[date_key].astype(str))
            new_df_filtered = new_df[~new_df[date_key].isin(existing_dates)]
        
        if new_df_filtered.empty:
            logger.info(f"Geen nieuwe records om toe te voegen aan {csv_file.name}")
            return
        
        logger.info(f"Toevoegen van {len(new_df_filtered)} nieuwe record(s) aan {csv_file.name}")
        combined_df = pd.concat([existing_df.drop('Date_Time', axis=1) if 'Date_Time' in existing_df.columns else existing_df, 
                                 new_df_filtered], ignore_index=True)
    else:
        logger.info(f"Opslaan van {len(new_df)} nieuwe record(s) in {csv_file.name}")
        combined_df = new_df
    
    # Sorteer op datum (en tijd voor hourly)
    if 'Time' in combined_df.columns:
        combined_df = combined_df.sort_values([date_key, 'Time'])
    else:
        combined_df = combined_df.sort_values(date_key)
    
    # Sla op
    combined_df.to_csv(csv_file, index=False)
    logger.info(f"Data opgeslagen in {csv_file} ({len(combined_df)} totaal records)")


def main():
    """
    Main functie voor V2 detailed forecast scraper
    """
    logger.info("=" * 60)
    logger.info("V2 - Detailed Solar Radiation Forecast Scraper voor Deinze")
    logger.info("=" * 60)
    
    # Laad bestaande data
    existing_daily_df = load_existing_data(DAILY_CSV)
    existing_hourly_df = load_existing_data(HOURLY_CSV)
    
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
    
    # Extract gedetailleerde forecast data
    logger.info("Zoeken naar gedetailleerde solar radiation forecast data...")
    daily_data, hourly_data = extract_detailed_forecast(html)
    
    if not daily_data and not hourly_data:
        logger.warning("Geen solar radiation waarden gevonden")
        return
    
    if daily_data:
        logger.info(f"Gevonden {len(daily_data)} dagelijkse record(s):")
        for record in daily_data:
            logger.info(f"  {record['Date']} ({record.get('DayName', 'N/A')}): "
                       f"{record['SolarRadiation_kWh_m2']:.3f} kWh/m² "
                       f"({record.get('Sunrise', 'N/A')} - {record.get('Sunset', 'N/A')})")
    
    if hourly_data:
        logger.info(f"Gevonden {len(hourly_data)} uurlijkse record(s)")
        # Toon eerste paar voor voorbeeld
        for record in hourly_data[:5]:
            logger.info(f"  {record['Date']} {record['Time']}: {record['SolarRadiation_W_m2']:.1f} W/m²")
        if len(hourly_data) > 5:
            logger.info(f"  ... en {len(hourly_data) - 5} meer")
    
    # Sla op in CSV
    if daily_data:
        save_to_csv(daily_data, DAILY_CSV, existing_daily_df)
    
    if hourly_data:
        save_to_csv(hourly_data, HOURLY_CSV, existing_hourly_df)
    
    logger.info("=" * 60)
    logger.info("V2 Scraper voltooid")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
