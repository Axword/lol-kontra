# Scraper – LoL Esports Roster Challenge

## Źródła
- **Leaguepedia Cargo API** – primary
  - `ScoreboardPlayers` – 1.3M rows – ekstrakcja Worlds players
  - `Players` – 20,605 rows – metadane: Country, Residency, Role, Birthdate, FavChamps, IsRetired
- **gol.gg** – secondary (champion stats) – stub gotowy, rate limit 1 req/2s

## Wynik ostatniego uruchomienia

```
Date: 2026-07-06
Source: lol.fandom.com – CargoExport
Filter: OverviewPage LIKE '%World%Championship%' AND DateTime_UTC BETWEEN 2011-01-01 AND 2025-12-31

ScoreboardPlayers rows scanned: ~18,720
Unique players extracted: 876
Enriched via Players table: 687 / 876 (78.4%)
Output: scraper/data/worlds_players_2011_2025.json (578 KB, 29,276 lines)
```

### Przykładowy rekord
```json
{
  "slug": "faker",
  "nickname": "Faker",
  "real_name": "Lee Sang-hyeok",
  "country_code": "KR",
  "residency": "LCK",
  "continent": "Asia",
  "primary_role": "mid",
  "birth_year": 1996,
  "is_active": 1,
  "worlds_count": 7,
  "worlds_titles_count": 0,
  "attributes": {
    "worlds_appearances": [2013,2015,2016,2017,2019,2022,2023],
    "worlds_titles": [],
    "teams": ["T1"],
    "leagues": ["LCK"],
    "coaches": [],
    "top_champions_career": ["Zed","LeBlanc","Ahri","Azir","Ryze","Orianna","Yasuo"],
    "country": "KR"
  }
}
```

## Użycie

```bash
# pełny ETL
docker compose exec api python -m scraper.main --full

# lub lokalnie
cd backend
python ../scraper/main.py --years 2011-2025 --full

# załaduj do DB
docker compose exec api python manage.py seed_players --full
# -> Loaded 876 players from JSON – created 876, updated 0
```

## Struktura plików
- `scraper/leaguepedia/cargo_api_client.py` – HTTP client z rate limiting
- `scraper/leaguepedia/worlds_players.py` – extract Worlds S1-S15
- `scraper/etl/normalize.py` – mapowanie ról, krajów, slugify
- `scraper/etl/upsert.py` – bulk UPSERT do Postgres
- `scraper/golgg/player_stats.py` – champion stats (TODO rozbudowa)
- `scraper/data/worlds_players_2011_2025.json` – gotowy seed 876 graczy

## Jakość danych
- 687 graczy z pełnymi metadanymi z tabeli Players
- 189 graczy – fallback (tylko ScoreboardPlayers: nick, team, role, worlds years)
- Brakujące: worlds_titles – do uzupełnienia ręcznie / z TournamentResults
- Coaches – do uzupełnienia (obecnie puste, poza seed sample)
- Top champions – z FavChamps (Players.FavChamps) – OK dla ~687 graczy

## Nowe scrapery (v2)

### `scraper/leaguepedia/career_stats.py`
Pobiera statystyki karierowe per-champion z lol.fandom.com.

```bash
# Pobierz statystyki dla konkretnego gracza
python -c "from scraper.leaguepedia.career_stats import fetch_player_career_stats; print(fetch_player_career_stats('Faker'))"

# Pobierz statystyki dla wielu graczy i zapisz do JSON
python -c "from scraper.leaguepedia.career_stats import fetch_all_players_stats; fetch_all_players_stats(['Faker', 'Caps'], 'output.json')"
```

URL źródłowy:
`https://lol.fandom.com/wiki/Special:RunQuery/TournamentStatistics?TS%5Bpreload%5D=PlayerByChampion&TS%5Blink%5D=Faker&_run=`

### `scraper/leaguepedia/teams.py`
Pobiera dane drużyn Worlds z Cargo API:
- Nazwa drużyny i slug
- Region (LCK/LPL/LEC/LCS/...)
- Czy drużyna wygrała Worlds (i w jakich latach)
- Czy drużyna jest aktywna

```bash
python -c "from scraper.leaguepedia.teams import fetch_worlds_teams; print(len(fetch_worlds_teams()))"
```

## Management commands

### `import_career_stats`
Importuje statystyki per-champion z lol.fandom.com do bazy.
```bash
python manage.py import_career_stats --player Faker
python manage.py import_career_stats --all-worlds-players --limit 50
python manage.py import_career_stats --from-json career_stats.json
```

### `import_team_history`
Importuje historyczne dane drużyn i relacji gracz-drużyna z JSON fixture.
```bash
python manage.py import_team_history
python manage.py import_team_history --from-json scraper/data/worlds_teams.json
python manage.py import_team_history --teams-only
python manage.py import_team_history --dry-run
```

## Następne kroki
- [ ] Import worlds_titles z TournamentResults Cargo
- [ ] Import coaches z PlayerLeagueHistory
- [ ] gol.gg – top 3 champions per season + games count
- [ ] Incremental weekly cron (Celery Beat)
- [ ] Walidacja: sprawdź czy każdy gracz ma primary_role, country_code, residency
- [x] Statystyki per-champion z lol.fandom.com
- [x] Historyczne drużyny (region, mistrzostwa, aktywność)
- [x] Relacje gracz-drużyna (rola, okres czasu)
- [x] Warunek "grał na innej roli" w generatorze
