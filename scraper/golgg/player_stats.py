"""
gol.gg scraper – champion stats (placeholder, respects robots.txt)
"""
import httpx
import time

BASE = "https://gol.gg/players/list/"

def fetch_player_champions(nickname: str):
    # Placeholder – real implementation would parse HTML with BeautifulSoup
    # Rate limit 1 req / 2s
    time.sleep(2)
    # return mock
    return {
        'top_champions_career': [
            {'champion': 'Azir', 'games': 78},
            {'champion': 'Ryze', 'games': 65},
            {'champion': 'LeBlanc', 'games': 52},
        ]
    }
