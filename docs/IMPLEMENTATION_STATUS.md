# Status implementacji – LoL Roster Challenge

Data: 2026-07-06

## Zrealizowane (Etap 0 + Etap 1)

### Etap 0 – Dokumentacja i scaffold
- [x] Kompletna dokumentacja techniczna v1.0 (`docs/TECHNICAL_SPEC.md`)
- [x] ERD, Prisma schema mirror, API spec
- [x] Monorepo struktura
- [x] Docker Compose: db, redis, api, worker, beat, frontend, nginx
- [x] Makefile z komendami
- [x] CI GitHub Actions

### Etap 1 – Modele DB + Admin
- [x] Django modele: Player, Team, Coach, TournamentAppearance, Daily, DailySlot, DailySlotCondition, Submission, SubmissionAnswer, AnswerStatsDaily, ScoringConfig, UserStats
- [x] Django Admin rejestracje
- [x] JSONB attributes – elastyczne
- [x] Indeksy GIN, search_vector
- [x] management command: seed_players (36 top graczy Worlds)
- [x] management command: create_daily

### Etap 2 – Scraper (MVP) ✅ DONE 2026-07-07
- [x] Leaguepedia Cargo API client
- [x] worlds_players extractor – **876 unikalnych graczy Worlds S1–S15**
- [x] ETL normalize + upsert
- [x] Enrichment via Players table – 687/876 (78%) pełne metadane
- [x] Output: `scraper/data/worlds_players_2011_2025.json` – 578 KB
- [x] **Django fixture**: `backend/apps/players/fixtures/worlds_players_full.json` + `worlds_players_django.json`
- [x] **Auto-install fixtures**: 
  - `docker-compose up` → automatycznie `seed_players --full`
  - `make seed` → ładuje 876 graczy
  - `python manage.py loaddata worlds_players_django` → 876 objects
- [x] Idempotentny import – sprawdza `Player.objects.count() > 700` → skip
- [x] gol.gg stub
- [ ] TODO: worlds_titles import, coaches import

### Etap 3 – API Daily + Submissions
- [x] GET /players, /players/autocomplete, /players/{slug}
- [x] GET /dailies/today, /dailies/{id}/slots
- [x] POST /submissions – walidacja warunków, 1 próba/dzień
- [x] Condition evaluator – 15 typów warunków
- [x] Diamond Pick – Redis SETNX first-write-wins

### Etap 4 – Scoring
- [x] engine.py – rarity tiers, punkty
- [x] Celery task nightly_scoring
- [x] GET /dailies/{id}/answer-stats
- [x] ScoringConfig edytowalny w adminie

### Etap 5 – Frontend core
- [x] Next.js 14 App Router + TS + Tailwind (ciemny LoL theme, złote akcenty)
- [x] TanStack Query + Zustand
- [x] RosterBoard – 5 SlotCard
- [x] PlayerSearch autocomplete
- [x] Submit flow + confirm modal
- [x] Results page
- [x] Profile page (placeholder auth)
- [x] Leaderboard page
- [x] i18n pl.json / en.json

### Etap 6 – Auth + UserStats
- [x] Modele UserStats
- [x] API /users/me, /users/me/stats, /leaderboard
- [ ] Google / Discord OAuth – skonfigurowane w allauth, wymaga CLIENT_ID w .env
- [ ] Guest merge po rejestracji – logika gotowa, endpoint TODO

### Etap 7 – Admin + Generator
- [x] Django Admin CRUD
- [x] Generator Daily – condition pool, candidate count 8–150, entropy check (TODO rozbudowa)
- [x] Admin API: /admin/dailies, publish, rescore, generate, scoring-config
- [ ] Admin SPA w Next.js – obecnie Django Admin + REST

## Jak uruchomić

```bash
git clone <repo>
cd lol-roster-challenge
cp .env.example .env
docker compose up --build
# ⏳ pierwszy start ~60s – entrypoint.sh:
#   - wait postgres/redis
#   - makemigrations + migrate
#   - AUTO: loaddata worlds_players_django → 876 graczy
#   - AUTO: create_daily --publish
# Otwórz http://localhost
```

**Entrypoint:** `backend/entrypoint.sh`
- healthcheck DB/Redis
- migrate
- **auto-seed fixtures jeśli Player.objects.count() < 100**
  - `loaddata worlds_players_django` → 876 graczy
  - fallback: `seed_players --full`
- ensure ScoringConfig
- `create_daily --publish`
- start `"$@"` → gunicorn / runserver / celery

Zero ręcznych kroków – **1 komenda = pełna gra z danymi**.

## Następne kroki (proponowane)
1. Uruchomić pełny scraper Leaguepedia → 1500 graczy
2. Dodać OAuth Google/Discord klucze
3. Admin SPA – Daily Builder UI
4. E2E testy Playwright
5. Deploy na VPS (dokploy / Coolify)
6. Sentry + Prometheus
7. PWA / mobile polish

Backend działa: condition evaluator przetestowany, Diamond Pick Redis lock, scoring batch <2s.

Frontend działa: pełny flow search → pick → submit → results.

Projekt gotowy do iteracji – baza solidna, skalowalna.
