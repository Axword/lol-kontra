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

## Następne kroki
- [ ] Import worlds_titles z TournamentResults Cargo
- [ ] Import coaches z PlayerLeagueHistory
- [ ] gol.gg – top 3 champions per season + games count
- [ ] Incremental weekly cron (Celery Beat)
- [ ] Walidacja: sprawdź czy każdy gracz ma primary_role, country_code, residency
