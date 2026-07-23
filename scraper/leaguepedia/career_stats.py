"""
Scraper dla statystyk karierowych graczy z lol.fandom.com.

Pobiera statystyki per-champion z:
https://lol.fandom.com/wiki/Special:RunQuery/TournamentStatistics?TS%5Bpreload%5D=PlayerByChampion&TS%5Blink%5D=Faker&_run=

Zwraca listę słowników ze statystykami dla każdego championa.
"""
import re
import time
import httpx
from bs4 import BeautifulSoup
from typing import Optional


BASE_URL = "https://lol.fandom.com"
PLAYER_STATS_URL = (
    f"{BASE_URL}/wiki/Special:RunQuery/TournamentStatistics"
    "?TS%5Bpreload%5D=PlayerByChampion&TS%5Blink%5D={player_name}&_run="
)

# Rate limiting – fandom wiki ma dość agresywny rate limit
REQUEST_DELAY = 1.5  # sekundy między requestami


def safe_request(url: str, timeout: float = 30.0) -> Optional[httpx.Response]:
    """Bezpieczny request z retry i rate limiting."""
    time.sleep(REQUEST_DELAY)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) LolKontra/1.0'
    }
    for attempt in range(3):
        try:
            r = httpx.get(url, headers=headers, timeout=timeout, follow_redirects=True)
            if r.status_code == 200:
                return r
            if r.status_code == 429:
                wait = min(60, 5 * (attempt + 1))
                print(f"  [rate-limited] waiting {wait}s...")
                time.sleep(wait)
                continue
            print(f"  [HTTP {r.status_code}] {url}")
            return None
        except httpx.RequestError as e:
            print(f"  [request error] {e}")
            if attempt < 2:
                time.sleep(3)
    return None


def parse_float(val: str) -> Optional[float]:
    """Parsuje float z tekstu, obsługuje '-' i puste."""
    val = val.strip().replace('%', '').replace(',', '')
    return float(val) if val and val != "-" else None


def parse_int(val: str) -> int:
    """Parsuje int z tekstu, obsługuje '-' i puste."""
    val = val.strip().replace(',', '')
    return int(val) if val and val != "-" else 0


def fetch_player_career_stats(player_lolpedia_name: str) -> list[dict]:
    """
    Pobiera statystyki karierowe gracza per-champion z lol.fandom.com.

    Args:
        player_lolpedia_name: Nazwa gracza na Leaguepedia (np. "Faker", "Caps")

    Returns:
        Lista słowników ze statystykami:
        [
            {
                'champion_name': 'Azir',
                'games_played': 45,
                'games_won': 30,
                'games_lost': 15,
                'win_ratio': 66.7,
                'kills': 3.2,
                'deaths': 1.8,
                'assists': 5.4,
                'kda': 4.78,
                'cs_per_min': 8.5,
                'dmg_per_min': 520.3,
            },
            ...
        ]
    """
    url = PLAYER_STATS_URL.format(player_name=player_lolpedia_name)
    print(f"  Fetching career stats for {player_lolpedia_name}...")

    response = safe_request(url)
    if not response:
        print(f"  [failed] Could not fetch data for {player_lolpedia_name}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')

    # Tabela statystyk ma klasę "spstats"
    table = soup.find("table", class_="spstats")
    if not table:
        print(f"  [no table] No stats table found for {player_lolpedia_name}")
        return []

    tbody = table.find("tbody")
    if not tbody:
        return []

    rows = tbody.find_all("tr")
    stats = []

    for row in rows:
        cols = row.find_all("td")
        if len(cols) < 9:
            continue

        champion_name = cols[0].text.strip()
        if not champion_name or champion_name == "Total":
            continue

        # Parsowanie kolumn (kolejność może się różnić, ale standardowo):
        # 0: Champion, 1: G, 2: W, 3: L, 4: WR%, 5: K, 6: D, 7: A, 8: KDA
        # 10: CS/min (czasem inna kolumna), 14: DMG/min
        try:
            stat = {
                'champion_name': champion_name,
                'games_played': parse_int(cols[1].text),
                'games_won': parse_int(cols[2].text),
                'games_lost': parse_int(cols[3].text),
                'win_ratio': parse_float(cols[4].text) or 0.0,
                'kills': parse_float(cols[5].text) or 0.0,
                'deaths': parse_float(cols[6].text) or 0.0,
                'assists': parse_float(cols[7].text) or 0.0,
                'kda': parse_float(cols[8].text) or 0.0,
            }

            # CS/min – zazwyczaj kolumna 10
            if len(cols) > 10:
                stat['cs_per_min'] = parse_float(cols[10].text)

            # DMG/min – zazwyczaj kolumna 14
            if len(cols) > 14:
                stat['dmg_per_min'] = parse_float(cols[14].text)

            # Pomiń championy z 0 gier (błędy parsowania)
            if stat['games_played'] > 0:
                stats.append(stat)

        except (IndexError, ValueError) as e:
            print(f"  [parse error] row for {champion_name}: {e}")
            continue

    print(f"  ✓ Fetched {len(stats)} champions for {player_lolpedia_name}")
    return stats


def fetch_all_players_stats(player_names: list[str], output_path: str = None) -> dict:
    """
    Pobiera statystyki karierowe dla listy graczy.

    Args:
        player_names: Lista nazw graczy z Leaguepedia
        output_path: Opcjonalna ścieżka do zapisu JSON

    Returns:
        Słownik {player_name: [stats_list]}
    """
    import json

    all_stats = {}
    total = len(player_names)

    for i, name in enumerate(player_names, 1):
        print(f"[{i}/{total}] Processing {name}...")
        stats = fetch_player_career_stats(name)
        if stats:
            all_stats[name] = stats

        # Progress co 10 graczy
        if i % 10 == 0:
            print(f"  Progress: {i}/{total} ({len(all_stats)} players with stats)")

    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(all_stats, f, ensure_ascii=False, indent=2)
        print(f"✓ Saved to {output_path}")

    return all_stats


if __name__ == "__main__":
    # Test dla kilku znanych graczy
    test_players = ["Faker", "Caps", "Chovy"]
    results = fetch_all_players_stats(test_players, "career_stats_sample.json")
    print(f"\nSummary: {len(results)} players processed")
