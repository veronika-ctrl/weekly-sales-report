# Diagnosis Report: Top Markets Y/Y GROWTH% shows "-" for 2025-W50/51/52

## 1) Repro Steps

- **Route:** `/top-markets` (frontend), or `/reports/weekly/[week]/top-markets` with `week` e.g. `2026-05`.
- **Filter:** Base week selected = e.g. **2026-05** (so “last 8 weeks” = 2025-W50, 2025-W51, 2025-W52, 2026-W01..W05).
- **Steps:**  
  1. Välj vecka **2026-05** i veckoväljaren.  
  2. Gå till **Top Markets**.  
  3. Observera tabellen: kolumnerna för veckorna 2025-W50, 2025-W51, 2025-W52 under **Y/Y GROWTH%** visar **"-"**.  
  4. Kolumnerna för 2026-W01..W05 under Y/Y GROWTH% visar siffror (t.ex. 12%, (5)%).
- **Exakt vad som visas:**  
  - **"-"** visas i **Y/Y GROWTH%**-kolumnerna **endast** för veckorna **2025-W50, 2025-W51, 2025-W52** (och i deras “Avg”-rad).  
  - **Value**-kolumnerna visar siffror för alla 8 veckor.  
  - Samma "-" för **alla marknader** (alla rader) för just dessa tre veckor.

---

## 2) Data Contract

- **API:** `GET /api/markets/top?base_week=2026-05&num_weeks=8` (eller via batch `GET /api/batch/all-metrics?base_week=2026-05&num_weeks=8`).
- **Payload (relevant del):**  
  `markets[]` med objekt `{ country, weeks: { [isoWeek]: number }, average }`.  
  `weeks` innehåller både “current” veckor (2025-50..2026-05) och **baseline**-veckor för Y/Y: 2024-50, 2024-51, 2024-52, 2025-01..2025-05.
- **Fält som styr Y/Y GROWTH%:**  
  För varje visad vecka `week` (t.ex. `2025-50`) används:
  - **current:** `market.weeks[week]` (t.ex. `market.weeks['2025-50']`)
  - **baseline (last year):** `market.weeks[lastYearWeek]` där `lastYearWeek = (year - 1) + '-' + weekNum` → för 2025-50 blir det `2024-50`.
- **För veckor som visar "-":**  
  För 2025-W50/51/52 är baseline-nycklarna 2024-50, 2024-51, 2024-52.  
  I payloaden är antingen:
  - dessa nycklar **saknas** i `market.weeks`, eller  
  - värdet är **0** (eller i praktiken “ingen data”).  
  Frontend gör `lastYearValue = market.weeks[lastYearWeek] || 0`, så baseline blir **0**.  
  Då returnerar `calculateYoY(current, 0)` **null** (undviker division med noll), och `formatYoY(null)` returnerar **"-"**.  
  Alltså: **"-" kommer av att baseline-värdet (previous year) är 0 eller saknas**, inte av att “Value”-kolumnen är fel.

---

## 3) Var skapas "-"

- **"-" skapas i frontend**, inte i backend.
- **Fil:** `frontend/components/TopMarketsTable.tsx`
  - **Rad 22–25:** `calculateYoY(current, previous)`: om `previous === 0` returneras **null**.
  - **Rad 27–28:** `formatYoY(value)`: om `value === null` returneras **"-"**.
  - **Rad 189–193:** För varje cell i Y/Y-kolumnen:  
    `lastYearValue = market.weeks[lastYearWeek] || 0`  
    `yoY = calculateYoY(currentValue, lastYearValue)`  
    cellen renderas som `formatYoY(yoY)`.
- **Slutsats:**  
  - Backend returnerar **inte** strängen "-".  
  - Backend returnerar **0** (eller nyckel saknas → frontend använder 0) för baseline-veckorna 2024-50/51/52.  
  - Frontend mappar **baseline = 0** → **null** i `calculateYoY` → **"-"** i `formatYoY`.

---

## 4) Root Cause (med evidens)

**Hypotes 1:** “Vi hämtar bara senaste 8 veckor; för YoY för 2025-W50/51/52 behövs också 2024-W50/51/52 (baseline saknas i dataset).”  
**Status:** **Bekräftad.**  
Backend (`weekly_report/src/metrics/markets.py`) bygger explicit `last_year_weeks` (2024-50, 2024-51, 2024-52, 2025-01..05) och fyller `combined_weeks` med både current och last-year. Men värdena för 2024-50/51/52 får bara data om:
- antingen samma Qlik-fil (i `data/raw/{base_week}/`) innehåller 2024-data (filtrerat på `iso_week`), eller  
- det finns mappar `data/raw/2024-50/`, `data/raw/2024-51/`, `data/raw/2024-52/` med laddbar data.  
Om ingen av dem finns blir `weeks_data.get(week, 0)` = **0** för dessa veckor → frontend får baseline 0 → "-".

**Hypotes 2:** Join-key mismatch (calendar year vs ISO week).  
**Status:** **Falsifierad.**  
Veckonycklar är konsekvent ISO `YYYY-WW` (t.ex. `2025-50`, `2024-50`). Frontend: `lastYearWeek = (year - 1) + '-' + weekNum`. Backend: `last_year_weeks` = samma veckonummer föregående år. Inget kalenderår/ISO-vecka-mix.

**Hypotes 3:** Baseline beräknas med date - 365 dagar istället för ISO-week match.  
**Status:** **Falsifierad.**  
Backend använder explicit ISO-vecka-filtrering (`df['iso_week'] == week_str`) och samma veckonummer föregående år. Ingen “date - 365”-logik här.

**Hypotes 4:** Week 50–52 2025 ger baseline-week som inte finns pga fel isoWeekYear eller weekKey-format.  
**Status:** **Delvis.**  
Formatet är korrekt (2024-50, 2024-51, 2024-52). Problemet är inte format utan att **det inte finns data** för dessa veckor i den data backend läser (antingen i base_week-filen eller i last-year-mappar).

**Root cause (sammanfattning):**  
Baseline-data för **2024-W50, 2024-W51, 2024-W52** saknas eller blir 0 i backend eftersom:
1) Qlik-filen i `data/raw/{base_week}/` (t.ex. 2026-05) ofta bara innehåller 2025/2026, inte 2024, och  
2) mappar `data/raw/2024-50/`, `data/raw/2024-51/`, `data/raw/2024-52/` saknas eller innehåller inte laddbar data.  
Därmed skickar backend 0 (eller utelämnar nyckeln) för dessa veckor → frontend visar "-" för Y/Y.

---

## 5) Confirmed Definition

- **Definition:** **Alternativ A (YoY)** – Year-over-Year: jämförelse mot **samma ISO-vecka föregående år**.
- **Var det sätts i koden:**  
  - Label: `frontend/components/TopMarketsTable.tsx` rad 139: `Y/Y GROWTH%`.  
  - Beräkning: samma fil, rad 22–25 (`calculateYoY`), rad 122–124 (`lastYearWeeks` = previous year, same week number).  
  - Backend: `weekly_report/src/metrics/markets.py` rad 60–76 (`last_year_weeks` = samma veckonummer, år - 1).
- **Formel:**  
  `YoY% = (current - previous) / previous * 100`  
  där `current = value för veckan` och `previous = value för samma veckonummer föregående år`.  
  - **Missing baseline:** Om `previous` saknas eller är 0 används idag **null** → visat som "-".  
  - **Baseline = 0:** Samma: `calculateYoY(..., 0)` returnerar null (division med noll undviks).  
  - **Avrundning:** `Math.round(absValue)` för absolutvärdet, procent utan decimaler; negativa inom parentes t.ex. (5)%.

---

## 6) Fix Plan (utan att implementera ännu)

- **Minimal fix:**  
  1) **Backend:** Säkerställ att last-year-veckor (2024-50/51/52) laddas när det finns data: använd redan befintlig logik som läser från `data/raw/{last_year_week}/` och från multi-year-data i base_week-filen. Lägg till tydlig loggning när 2024-data laddas respektive när den saknas.  
  2) **Frontend:** Ingen ändring av "Value"-kolumnerna. För Y/Y: behåll "-" när baseline saknas/är 0; eventuellt visa "n/a" eller tooltip "Baseline (2024-W50) not available" för tydlighet (valfritt, dokumenterat).  
  3) **Regression:** Enhetstest som verifierar weekKey-matchning över årsskiftet (t.ex. 2025-50 → baseline 2024-50) och ett test som simulerar payload med 2024-50/51/52 = 0 och bekräftar att frontend visar "-" för dessa veckor men procent för 2026-01..05 när baseline finns.

- **Var fixen ska ligga:**  
  Primärt **backend** (data tillgänglighet för 2024-W50/51/52). Frontend är redan korrekt: den visar "-" när baseline är 0; problemet är att baseline inte fylls när datan finns men inte laddas.

- **Tester/loggar:**  
  - Backend: Logga när last-year-mappar används och när inga rader hittas för 2024-50/51/52.  
  - Minst ett enhetstest (backend eller frontend) för weekKey → lastYearWeek (2025-50 → 2024-50).  
  - Minst ett test som kontrollerar att när `market.weeks['2024-50']` är 0 så blir Y/Y-cellens visning "-", och när det är > 0 så blir det en procent-siffra.
