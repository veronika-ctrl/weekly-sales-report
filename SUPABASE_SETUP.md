# Supabase Setup Guide

**Viktigt:** Appen använder **endast** data från Supabase. Om det inte finns data för vald vecka i Supabase visas meddelandet "Ingen data för denna vecka laddad än". API används inte som källa – endast för att synka data till Supabase (Settings → Refresh all data) och för perioder.

## Steg 1: Vänta på att Supabase-projektet är klart
När projektet är klart får du:
- **Project URL**: `https://xxxxx.supabase.co`
- **anon/public key**: För frontend
- **service_role key**: För backend

## Steg 2: Kör SQL-schemat
1. Öppna Supabase Dashboard
2. Gå till **SQL Editor**
3. Kopiera innehållet från `supabase_schema.sql`
4. Kör SQL:en för att skapa alla tabeller

## Steg 3: Uppdatera miljövariabler

**Alla fyra nycklar måste vara från samma Supabase-projekt.** Om frontend-URL och backend-URL pekar på olika projekt (eller om anon key är från ett annat projekt) kommer sync och rapporter inte att fungera.

### Nytt Supabase-projekt – var byter man uppgifter?
- **Lokalt:** Uppdatera `frontend/.env.local` (frontend) och `.env` i projektets root (backend) med den nya Project URL och nycklarna från Supabase Dashboard → Settings → API.
- **Vercel:** Project Settings → Environment Variables – uppdatera `NEXT_PUBLIC_SUPABASE_URL` och `NEXT_PUBLIC_SUPABASE_ANON_KEY` till det nya projektet. Sätt `NEXT_PUBLIC_DISABLE_SUPABASE=false` (eller ta bort variabeln). Redeploya efter ändring.
- **Backend (Railway/Render/etc.):** Uppdatera `SUPABASE_URL` och `SUPABASE_SERVICE_ROLE_KEY` till det nya projektet.

### Backend (`.env` i projektets root)
Hämtas från Supabase Dashboard → Settings → API:
```env
SUPABASE_URL=https://DITT_PROJECT_REF.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...  # service_role key (hemlig)
```

### Frontend (`frontend/.env.local` och Vercel Environment Variables)
Samma projekt-URL som backend; anon key från samma sida:
```env
NEXT_PUBLIC_SUPABASE_URL=https://DITT_PROJECT_REF.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...  # anon public key
NEXT_PUBLIC_DISABLE_SUPABASE=false   # false eller utelämna så att Supabase används
```

Kontroll: `NEXT_PUBLIC_SUPABASE_URL` och `SUPABASE_URL` ska ha samma domän (samma PROJECT_REF).

## Steg 4: Verifiera (inga gissningar)
För att vara 100% säker på att backend ser Supabase:

1. **Backend:** Starta om backend (så att `.env` laddas från projektroten).
2. **Settings-sidan:** Gå till **Settings** i appen och klicka på **"Verifiera Supabase (backend)"**.
3. **Resultatet visar exakt:**
   - `env_file_loaded`: om `.env` hittades
   - `SUPABASE_URL`: `set` eller `not_set`
   - `SUPABASE_SERVICE_ROLE_KEY`: `set` eller `not_set` (plus key length)
   - `client_created`: om klienten skapades
   - `client_error`: felmeddelande om klienten inte skapades
   - `query_ok`: om en enkel läsning mot `weekly_report_metrics` lyckades
   - `query_error`: felmeddelande om läsningen misslyckades
   - `table_row_count`: antal rader (om query_ok)

Om något steg är `not_set` eller har ett fel – åtgärda det (t.ex. `.env` i root, rätt variabelnamn). När alla steg är gröna fungerar sync.

Du kan också anropa backend direkt: `GET http://localhost:8000/api/supabase/verify` (samma JSON som ovan).

## Tabeller som skapas:
- `weekly_report_metrics` - Cachade metrics för snabb laddning
- `budget_files` - Budget CSV-filer per år
- `budget_general` - Budget general data
- `budget_general_totals` - Budget general totals
- `budget_markets_detailed` - Budget markets detailed
- `budget_markets_totals` - Budget markets totals
- `weeks` - Tracking av veckor
- `sync_runs` - Tracking av sync operations

## Felsökning:
- Om du får RLS (Row Level Security) fel: Kontrollera att policies är korrekta i SQL:en
- Om tabeller saknas: Kör `supabase_schema.sql` igen
- Om connection errors: Kontrollera att URL och keys är korrekta i `.env`-filerna
