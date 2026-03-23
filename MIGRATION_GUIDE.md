# Guide för att ändra GitHub och Supabase-konfiguration

## 1. Ändra Git Remote till nytt GitHub-konto

### Steg 1: Ta bort nuvarande remote
```bash
git remote remove origin
```

### Steg 2: Lägg till ny remote
```bash
git remote add origin <NY_GITHUB_REPO_URL>
```

### Steg 3: Verifiera
```bash
git remote -v
```

### Steg 4: Pusha till nytt repo (om det redan finns)
```bash
git push -u origin main
```

Eller om du vill skapa ett nytt repo:
1. Skapa ett nytt repository på GitHub
2. Följ instruktionerna ovan med den nya URL:en

---

## 2. Uppdatera Supabase-konfiguration

### Steg 1: Hämta nya Supabase-uppgifter
Från ditt nya Supabase-projekt behöver du:
- **Project URL** (t.ex. `https://xxxxx.supabase.co`)
- **anon/public key** (för frontend)
- **service_role key** (för backend)

### Steg 2: Uppdatera backend `.env`
Redigera `/Users/axelsamuelson/Documents/CDLP_CODE/weekly_report_v2.0/.env`:

```env
SUPABASE_URL=https://wsxnuduzjpukcsfotvlt.supabase.co
SUPABASE_SERVICE_ROLE_KEY=ny_service_role_key_här
```

### Steg 3: Uppdatera frontend `.env.local`
Redigera `/Users/axelsamuelson/Documents/CDLP_CODE/weekly_report_v2.0/frontend/.env.local`:

```env
NEXT_PUBLIC_SUPABASE_URL=https://NYTT_PROJECT_ID.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=ny_anon_key_här
```

### Steg 4: Starta om servrarna
Efter ändringarna måste du starta om både backend och frontend. **Backend måste alltid startas från projektroten** (mappen där `weekly_report/` ligger), annars blir felet `No module named 'weekly_report.src.compute'`.

```bash
# Stoppa servrarna
pkill -f "uvicorn.*weekly_report"
pkill -f "next dev"

# Starta om från projektroten (rekommenderat: använd Make eller start_dev.sh)
cd /Users/axelsamuelson/Documents/CDLP_CODE/weekly_report_v2.0

# Alternativ 1: Make (startar från projektroten)
make run-backend &    # Terminal 1
make run-frontend     # Terminal 2

# Alternativ 2: Skriptet start_dev.sh (cd:ar till projektroten åt dig)
./scripts/start_dev.sh

# Alternativ 3: Manuellt
python3 -m uvicorn weekly_report.api.routes:app --host 0.0.0.0 --port 8000 --reload &
cd frontend && npm run dev &
```

---

## 3. Verifiera ändringarna

### Verifiera Git:
```bash
git remote -v
git status
```

### Verifiera Supabase:
1. Öppna frontend i webbläsaren
2. Öppna Developer Console (F12)
3. Sök efter "Supabase client initialized successfully"
4. Om du ser detta medan du laddar data, fungerar Supabase

---

## Viktiga filer som behöver uppdateras:

1. **Backend**: `.env` (i root)
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_ROLE_KEY`

2. **Frontend**: `frontend/.env.local`
   - `NEXT_PUBLIC_SUPABASE_URL`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY`

3. **Git**: Remote URL (via `git remote set-url`)

---

## Noteringar:

- `.env` och `.env.local` är vanligtvis i `.gitignore` och committas inte
- Se till att det nya Supabase-projektet har samma tabellstruktur som det gamla
- Om tabellerna saknas, kan du behöva köra migrations eller skapa dem manuellt
