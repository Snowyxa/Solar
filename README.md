# Solar Radiation Data Pipeline - Deinze

Data pipeline voor het ophalen en opslaan van zonne-instralingsdata van tutiempo.net voor Deinze.

## Setup

1. **Installeer Python 3.11 of hoger**

2. **Installeer dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

## Versies Overzicht

### V0 - Proof of Concept
**Doel:** Bewijzen dat data automatisch opgehaald kan worden.

**Wat het doet:**
- Downloadt HTML pagina van tutiempo.net
- Zoekt naar solar radiation data in tabellen
- Print structuur naar console voor debugging

**Gebruik:**
```bash
python v0_scraper.py
```

---

### V1 - Daily Scraper + Opslag
**Doel:** Stabiele datacollectie met retries, logging en CSV opslag.

**Wat het doet:**
- ✅ Auto-detectie van URL (zoekt automatisch naar juiste pagina)
- ✅ Downloadt HTML met retry logica (max 3 pogingen)
- ✅ Extract dagelijkse solar radiation waarde
- ✅ Slaat data op in CSV (`data/raw/solar_deinze.csv`)
- ✅ Voorkomt duplicaten (geen dubbele datums)
- ✅ Logging naar console en `solar_scraper.log`

**Gebruik:**
```bash
python v1_scraper.py
```

**Output:**
- CSV: `data/raw/solar_deinze.csv`
- Log: `solar_scraper.log`

**Data structuur:**
```csv
Date,SolarRadiation_kWh_m2,Source,FetchedAt
2026-01-18,1.166,tutiempo.net,2026-01-18 00:07:50
```

---

### V2 - Detailed Forecast Scraper ⭐ (Huidige versie)
**Doel:** Extract 15-day forecast met dagelijkse totalen en uurlijkse breakdowns.

**Wat het doet:**
- ✅ Auto-detectie van URL (zoekt automatisch naar juiste pagina)
- ✅ Downloadt HTML met retry logica
- ✅ Extract **15 dagen** forecast data
- ✅ Extract **dagelijkse totalen** (kWh/m² en Wh/m²)
- ✅ Extract **uurlijkse breakdowns** (W/m² per uur)
- ✅ Extract sunrise/sunset tijden (werk in uitvoering)
- ✅ Slaat data op in **2 CSV bestanden**:
  - `solar_daily_summary.csv` - Dagelijkse totalen
  - `solar_hourly_detail.csv` - Uurlijkse details
- ✅ Voorkomt duplicaten (Date voor daily, Date+Time voor hourly)
- ✅ Logging naar console en `solar_scraper.log`

**Gebruik:**
```bash
python v2_scraper.py
```

**Output:**
- CSV: `data/raw/solar_daily_summary.csv` (dagelijkse totalen)
- CSV: `data/raw/solar_hourly_detail.csv` (uurlijkse details)
- Log: `solar_scraper.log`

**Data structuur:**

**Daily Summary:**
```csv
Date,DayName,SolarRadiation_kWh_m2,SolarRadiation_Wh_m2,Sunrise,Sunset,Source,FetchedAt
2026-01-18,Today,1.166,1166.0,08:42,17:10,tutiempo.net,2026-01-18 00:08:52
```

**Hourly Detail:**
```csv
Date,Time,SolarRadiation_W_m2,SolarRadiation_Wh_m2,Source,FetchedAt
2026-01-18,09:00,4.0,4.0,tutiempo.net,2026-01-18 00:08:52
2026-01-18,10:00,61.0,61.0,tutiempo.net,2026-01-18 00:08:52
```

---

### V3 - Battery Prognosis 🔋 (Huidige versie)
**Doel:** Voorspel batterijprestatie op basis van solar radiation forecast.

**Wat het doet:**
- ✅ Leest solar radiation forecast data (uit V2)
- ✅ Simuleer batterijgedrag (charge/discharge cycles)
- ✅ Genereer 15-day prognosis met batterij state-of-charge
- ✅ Output naar CSV (`data/processed/battery_prognosis.csv`)
- ✅ Configureerbare batterij parameters (capaciteit, efficiëntie, etc.)
- ✅ Logging naar console en `solar_scraper.log`

**Gebruik:**
```bash
python v3_battery_prognosis.py
```

**Output:**
- CSV: `data/processed/battery_prognosis.csv`
- Log: `solar_scraper.log`

**Data structuur:**
```csv
Date,DayName,SolarRadiation_kWh_m2,ChargeEnergy_kWh,DischargeEnergy_kWh,BatterySOC_percent,BatteryEnergy_kWh,Status
2026-01-18,Today,1.166,0.95,0.50,75.0,7.5,Charging
```

---

## Mogelijke Toekomstige Verbeteringen

**Functionaliteit:**
- 📊 Data visualisatie (grafieken, trends)
- 📊 Statistieken en analyses (gemiddelden, pieken, etc.)
- 📊 Export naar andere formaten (JSON, Excel)
- 📊 Database integratie (SQLite, PostgreSQL)

**Automatisatie:**
- ⏰ Scheduled runs (cron jobs, Windows Task Scheduler)
- ⏰ Email notificaties bij errors
- ⏰ API endpoint voor data access

**Robuustheid:**
- 🛡️ Betere error handling
- 🛡️ Rate limiting en respect voor robots.txt
- 🛡️ Data validatie en quality checks

**Code Kwaliteit:**
- 🧹 Unit tests
- 🧹 Type hints en documentatie
- 🧹 Configuration file (YAML/JSON) voor instellingen

---

## Project Structuur

```
Solar/
├── v0_scraper.py                              # V0 proof of concept
├── v1_scraper.py                              # V1 daily scraper
├── v2_scraper.py                              # V2 detailed forecast scraper
├── v3_battery_prognosis.py                    # V3 battery prognosis ⭐
├── requirements.txt                            # Python dependencies
├── README.md                                   # Deze file
├── solar_scraper.log                           # Log bestand
├── data/
│   ├── raw/
│   │   ├── solar_deinze.csv                   # V1 output
│   │   ├── solar_daily_summary.csv            # V2 daily output
│   │   └── solar_hourly_detail.csv            # V2 hourly output
│   └── processed/
│       └── battery_prognosis.csv              # V3 output
└── solar_radiation_data_pipeline_low_resource_plan.md
```

---

## Juridische Nota

- Controleer `robots.txt` van tutiempo.net
- Beperk requests tot 1× per dag
- Gebruik respectvolle scraping praktijken
- Respecteer rate limits en server resources

---

## Dependencies

Zie `requirements.txt` voor volledige lijst. Belangrijkste:
- `requests` - HTTP requests
- `beautifulsoup4` - HTML parsing
- `pandas` - Data manipulatie en CSV opslag
