# Deployment Checklist

## Pre-Deployment

### Git & Repository
- [x] Git remote uppdaterad till nytt repository
- [ ] Alla ändringar committade
- [ ] Koden pushad till GitHub

### Supabase
- [ ] Supabase-projekt skapat och klart
- [ ] SQL-schema (`supabase_schema.sql`) kört i Supabase
- [ ] Supabase URL och keys dokumenterade
- [ ] `.env`-filer uppdaterade med nya Supabase-uppgifter

### Vercel (Frontend)
- [ ] Vercel-konto skapat
- [ ] Projekt importerat från GitHub
- [ ] Root Directory satt till `frontend`
- [ ] Miljövariabler satta i Vercel:
  - [ ] `NEXT_PUBLIC_API_URL`
  - [ ] `NEXT_PUBLIC_SUPABASE_URL`
  - [ ] `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- [ ] Första deployment lyckad

### Backend Deployment
- [ ] Backend deployad (Railway/Render/etc.)
- [ ] Backend URL dokumenterad
- [ ] Backend miljövariabler satta:
  - [ ] `SUPABASE_URL`
  - [ ] `SUPABASE_SERVICE_ROLE_KEY`
  - [ ] `FRONTEND_URL` (för CORS)
- [ ] CORS uppdaterad för Vercel-domän

### Testing
- [ ] Frontend laddar korrekt på Vercel
- [ ] API-anrop fungerar från Vercel till backend
- [ ] Supabase-anslutning fungerar
- [ ] Filuppladdning fungerar
- [ ] Data visas korrekt

## Post-Deployment

### Verifiering
- [ ] Alla sidor laddar utan fel
- [ ] Inga CORS-fel i konsolen
- [ ] Inga 404-fel för API-endpoints
- [ ] Supabase-data laddas korrekt

### Dokumentation
- [ ] Deployment-guide uppdaterad
- [ ] Miljövariabler dokumenterade
- [ ] Teammedlemmar informerade om nya URLs

## Miljövariabler Reference

### Frontend (Vercel)
```
NEXT_PUBLIC_API_URL=https://din-backend-url.com
NEXT_PUBLIC_SUPABASE_URL=https://ditt-supabase-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=ditt_anon_key
```

### Backend (Railway/Render/etc.)
```
SUPABASE_URL=https://ditt-supabase-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=ditt_service_role_key
FRONTEND_URL=https://din-vercel-app.vercel.app
```

## Nästa Steg

1. **Supabase**: Vänta på att projektet är klart, kör SQL-schema
2. **Vercel**: Importera projekt, sätt miljövariabler, deploya
3. **Backend**: Deploya backend separat, uppdatera CORS
4. **Testing**: Verifiera att allt fungerar
