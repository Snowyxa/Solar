# Doel
Dagelijks zonne‑instralingsdata (solar radiation) ophalen van **tutiempo.net** voor Deinze en gebruiken om een **prognose te maken van batterij‑oplaadcapaciteit**, met zo laag mogelijke kosten en systeemvereisten.

---
## Belangrijke terminologie
- **Data scraping**: het automatisch ophalen van data van een website.
- **Data cleaning / scrubbing**: het opschonen, normaliseren en valideren van ruwe data.
- **ETL‑pipeline**: Extract → Transform → Load.
- **Forecasting**: voorspellen van toekomstige waarden op basis van historische data.

---
## Juridische en praktische noot (kort)
Voor je technisch start:
- Controleer de *terms of service* en `robots.txt` van tutiempo.net.
- Beperk requests (1× per dag is prima).
- Gebruik caching en user‑agent identificatie.

---
# Architectuur (low‑resource)

**Aanbevolen stack**
- Taal: **Python 3.11+**
- Scheduler: **cron** (Linux) of Windows Task Scheduler
- Storage (keuze):
  - *Start*: **CSV / Parquet files**
  - *Later*: **PostgreSQL** (alleen indien nodig)
- Libraries:
  - `requests`
  - `beautifulsoup4`
  - `pandas`
  - `pydantic` (optioneel, voor validatie)
  - `statsmodels` of `prophet` (later)

---
# Datastroom (hoog niveau)
1. Daily fetch HTML pagina
2. Extract relevante tabel (solar radiation per dag)
3. Normalize units (kWh/m², Wh/m², etc.)
4. Opslaan als tijdreeks
5. Bereken potentiële batterij‑oplaadenergie
6. Forecast 1–7 dagen vooruit

---
# Datamodel (minimum)

```text
Date (YYYY‑MM‑DD)
SolarRadiation_kWh_m2
Source
FetchedAt
```

---
# Batterij‑model (vereenvoudigd)

```text
Opbrengst (kWh) =
SolarRadiation_kWh_m2
× PaneelOppervlak_m2
× PaneelEfficiëntie
× SysteemEfficiëntie
```

Beperkingen:
- Geen bewolking‑nuance
- Geen temperatuur‑derating
- Goed genoeg voor MVP

---
# Versie‑per‑versie plan

## V0 – Proof of concept (1–2 dagen)
**Doel:** bewijzen dat data automatisch opgehaald kan worden.

- Handmatig HTML downloaden
- Inspecteer tabelstructuur
- Schrijf script dat:
  - pagina downloadt
  - één dagwaarde extraheert
  - print naar console

**Output:** ruwe waarde

---
## V1 – Daily scraper + opslag
**Doel:** stabiele datacollectie

- Python script met:
  - retries
  - timeout
  - logging
- Parse alle dagwaarden van huidige maand
- Opslaan in CSV (`data/raw/solar_deinze.csv`)
- Cron job 1× per dag

**Test:**
- Script 5× runnen zonder duplicaten

---
## V2 – Data cleaning & validatie
**Doel:** betrouwbare tijdreeks

- Duplicaten verwijderen
- Missing days detecteren
- Units normaliseren
- Waarden buiten plausibel bereik flaggen

**Output:** `data/clean/solar_deinze.parquet`

---
## V3 – Batterij‑oplaadberekening
**Doel:** bruikbare energie‑inschatting

- Config file (`config.yaml`):
  - paneeloppervlak
  - efficiëntie
  - batterijcapaciteit
- Bereken daily charge potential
- Clamp op max batterijcapaciteit

**Output:** extra kolom `PotentialCharge_kWh`

---
## V4 – Simpele forecasting
**Doel:** korte termijn voorspelling

- Rolling average (7d)
- Alternatief: ARIMA
- Forecast 1–3 dagen

**Meetpunt:** MAE vs echte waarden

---
## V5 – PostgreSQL (optioneel)
**Alleen doen indien:**
- meerdere locaties
- meerdere bronnen
- dashboard nodig

Schema:
- `solar_raw`
- `solar_clean`
- `battery_projection`

---
# Kosteninschatting

| Component | Kost |
|--------|------|
| Python | €0 |
| Cron | €0 |
| CSV/Parquet | €0 |
| PostgreSQL (local) | €0 |
| Cloud VPS (optioneel) | €5–10 / maand |

---
# Risico’s
- HTML structuur kan wijzigen
- Geen officiële API
- Forecast accuracy beperkt zonder weersvoorspelling

---
# Volgende stap (concreet)
1. HTML structuur analyseren
2. Exacte kolomnamen bevestigen
3. V0 script schrijven

---
*Dit document is bedoeld als iteratief werkdocument.*

