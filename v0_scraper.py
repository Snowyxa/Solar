"""
V0 - Proof of Concept: Solar Radiation Data Scraper voor Deinze
Doel: Bewijzen dat data automatisch opgehaald kan worden van tutiempo.net
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re

# Configuratie
DEINZE_STATION_ID = None  # TODO: te bepalen na HTML inspectie
BASE_URL = "https://en.tutiempo.net/solar-radiation/deinze.html"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

def fetch_html(url):
    """
    Download HTML pagina van tutiempo.net
    """
    try:
        print(f"Downloaden van: {url}")
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        print(f"Fout bij ophalen van data: {e}")
        return None

def extract_solar_radiation_value(html):
    """
    Extract één dagwaarde voor solar radiation uit de HTML
    """
    soup = BeautifulSoup(html, 'html.parser')
    
    # Zoek naar tabellen met data
    tables = soup.find_all('table')
    print(f"\nGevonden tabellen: {len(tables)}")
    
    # Zoek naar solar radiation in verschillende formaten
    # 1. Zoek naar tekst met "wh/m2", "kwh/m2", "mj/m2" etc.
    all_text = soup.get_text()
    
    # Zoek naar patronen zoals "579wh/m2" of "579 wh/m2"
    patterns = [
        r'(\d+(?:\.\d+)?)\s*(?:wh|kwh|mj)\s*/?\s*m[²2]',
        r'(\d+(?:\.\d+)?)\s*(?:wh|kwh|mj)\s*/?\s*m\^?2',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, all_text, re.IGNORECASE)
        if matches:
            print(f"\n[Gevonden] Solar radiation waarde(n): {matches}")
            # Neem de eerste match als dagwaarde
            return matches[0]
    
    # 2. Zoek in tabellen naar headers met "solar" of "radiation"
    for i, table in enumerate(tables):
        headers = table.find_all(['th', 'td'])
        for header in headers:
            text = header.get_text().strip().lower()
            if 'solar' in text or 'radiation' in text or 'radiación' in text:
                print(f"\n[Gevonden] Solar radiation kolom in tabel {i+1}:")
                print(f"  Header tekst: {header.get_text().strip()}")
                
                # Zoek bijbehorende waarde
                row = header.find_parent('tr')
                if row:
                    cells = row.find_all(['td', 'th'])
                    cell_texts = [c.get_text().strip() for c in cells]
                    print(f"  Rij cellen: {cell_texts}")
                    
                    # Zoek naar numerieke waarde in de cellen
                    for cell_text in cell_texts:
                        match = re.search(r'(\d+(?:\.\d+)?)', cell_text)
                        if match:
                            return match.group(1)
    
    # 3. Zoek naar links of spans met solar radiation
    solar_elements = soup.find_all(text=re.compile(r'solar|radiation', re.IGNORECASE))
    for elem in solar_elements[:5]:  # Check eerste 5 matches
        parent = elem.parent
        if parent:
            parent_text = parent.get_text()
            match = re.search(r'(\d+(?:\.\d+)?)\s*(?:wh|kwh|mj)\s*/?\s*m[²2]', parent_text, re.IGNORECASE)
            if match:
                print(f"\n[Gevonden] Solar radiation in element: {parent_text[:100]}")
                return match.group(1)
    
    # Fallback: print eerste tabel structuur voor debugging
    if tables:
        print("\n[DEBUG] Eerste tabel structuur:")
        first_table = tables[0]
        rows = first_table.find_all('tr', limit=5)
        for row in rows:
            cells = row.find_all(['td', 'th'])
            print(f"  {[c.get_text().strip()[:30] for c in cells]}")
    
    return None

def main():
    """
    Main functie voor V0 proof of concept
    """
    print("=" * 60)
    print("V0 - Solar Radiation Data Scraper voor Deinze")
    print("=" * 60)
    print(f"Tijdstip: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Gebruik de correcte URL voor Deinze
    html = fetch_html(BASE_URL)
    
    if not html:
        print("\n[ERROR] Kon geen HTML ophalen. Controleer:")
        print("  1. Internet connectie")
        print("  2. URL structuur van tutiempo.net")
        print("  3. Handmatig de juiste URL bepalen via browser")
        return
    
    print(f"[OK] Successvol gedownload van: {BASE_URL}")
    
    # Extract solar radiation waarde
    print("\n" + "-" * 60)
    print("Zoeken naar solar radiation data...")
    print("-" * 60)
    
    result = extract_solar_radiation_value(html)
    
    if result:
        print("\n[OK] Ruwe waarde gevonden (details hierboven)")
    else:
        print("\n[WARNING] Geen solar radiation waarde gevonden")
        print("   Controleer HTML structuur handmatig:")
        print("   1. Open URL in browser")
        print("   2. Inspecteer tabel met solar radiation data")
        print("   3. Pas extract_solar_radiation_value() aan")
    
    print("\n" + "=" * 60)
    print("V0 Proof of Concept voltooid")
    print("=" * 60)

if __name__ == "__main__":
    main()
