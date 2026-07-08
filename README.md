# League of Legends Esports Roster Challenge – Worlds XI

Codzienna gra LoL Esports inspirowana Kontra.games „Mundialowa Jedenastka”.

**Stack:** Next.js 14 + TypeScript + Tailwind / Django 5 + DRF + PostgreSQL 16 + Redis 7

Dokumentacja techniczna: [`docs/TECHNICAL_SPEC.md`](docs/TECHNICAL_SPEC.md)

## Szybki start

```bash
cp .env.example .env
docker compose up --build
# ⏳ pierwszy start ~60-90s:
#   - PostgreSQL init
#   - Django makemigrations + migrate
#   - AUTO-SEED: 876 graczy Worlds (via entrypoint.sh)
#   - AUTO-DAILY: create_daily --publish
# -> http://localhost   (frontend + mapa Rift)
# -> http://localhost/api/docs/  (Swagger)
# -> http://localhost/admin/  (admin / admin)
```

**Entrypoint** (`backend/entrypoint.sh`) robi automatycznie przy każdym starcie kontenera:
1. czeka na PostgreSQL + Redis
2. `makemigrations && migrate`
3. **sprawdza `Player.objects.count()`**
   - `< 100` → `loaddata worlds_players_django` → **876 graczy**
   - `> 700` → skip (2s)
4. tworzy `ScoringConfig` jeśli brak
5. `create_daily --publish` – dzisiejszy Daily z 5 slotami
6. wyświetla podsumowanie:
```
====================================================
  PLAYERS: 876
  ACTIVE : 612
  TODAY  : Daily #1 – 2026-07-07 – published – slots:5
====================================================
```
7. `exec "$@"` → uruchamia `runserver` / `gunicorn` / `celery`


## Komendy

```
make up          # docker compose up --build
make down
make logs
make migrate     # python manage.py migrate
make createsuperuser
make seed        # seed 50 top graczy
make scrape      # scraper full Worlds S1-S15
make test
make shell
```

## Struktura

- `frontend/` – Next.js 14 App Router, PL/EN
- `backend/` – Django 5 + DRF
- `scraper/` – Leaguepedia + gol.gg ETL
- `worker/` – Celery

## Etapy

- [x] Etap 0 – Dokumentacja techniczna
- [x] Etap 0.5 – Monorepo + Docker scaffold
- [x] Etap 1 – Modele DB + Admin + seed (36 graczy)
- [x] Etap 2 – Scraper MVP (Leaguepedia Cargo + gol.gg stub)
- [x] Etap 3 – API Daily + Submissions + Condition Evaluator + Diamond Pick
- [x] Etap 4 – Scoring Engine + Rarity + Celery
- [x] Etap 5 – Frontend core (RosterBoard, PlayerSearch, Results)
- [x] Etap 6 – Auth scaffolding + UserStats + Leaderboard API
- [x] Etap 7 – Admin API + Daily Generator
- [ ] Etap 8 – OAuth Google/Discord keys, Admin SPA, E2E, deploy produkcyjny

Szczegóły: [`docs/IMPLEMENTATION_STATUS.md`](docs/IMPLEMENTATION_STATUS.md)

## Uruchomienie – krok po kroku

```bash
cp .env.example .env
make up
# pierwsze uruchomienie:
# - automatycznie: makemigrations + migrate
# - automatycznie: seed_players --full  → 876 graczy Worlds
# - automatycznie: create_daily --publish
# poczekaj ~30-60s na pierwszy seed (jednorazowo)
# Otwórz http://localhost
```

**Dane w bazie po starcie:**
- **876 zawodników Worlds S1–S15** – auto-ładowane z `backend/apps/players/fixtures/worlds_players_full.json`
- 1 Daily wygenerowany automatycznie
- ScoringConfig, UserStats – gotowe

Ręczne komendy:
```bash
make seed              # seed_players --full  (876 graczy, idempotentny)
make seed-sample       # tylko 36 top graczy
make seed-clear        # wyczyść + załaduj pełną bazę
# lub Django fixtures:
docker compose exec api python manage.py loaddata worlds_players_django
# -> Installed 876 object(s)

# stwórz nowy Daily:
docker compose exec api python manage.py create_daily --publish
```

Test API:
- http://localhost/api/docs/ – Swagger
- http://localhost/api/v1/dailies/today/
- http://localhost/api/v1/players/?search=faker
- http://localhost/admin/ – Django Admin

Licencja: MIT (do ustalenia)
