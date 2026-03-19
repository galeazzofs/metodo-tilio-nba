import requests
from bs4 import BeautifulSoup

FANTASYPROS_URL = (
    "https://www.fantasypros.com/daily-fantasy/nba/fanduel-defense-vs-position.php"
)

POSITIONS = ["PG", "SG", "SF", "PF", "C"]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def get_defense_vs_position():
    """
    Scrapes FantasyPros DvP table for all positions.

    Returns a nested dict:
    {
        'PG': {
            'Indiana Pacers': {'pts': 28.44, 'rank': 1},   # rank 1 = easiest to score on
            'Boston Celtics':  {'pts': 19.12, 'rank': 30},
            ...
        },
        'SG': { ... },
        'SF': { ... },
        'PF': { ... },
        'C':  { ... },
    }
    """
    resp = requests.get(FANTASYPROS_URL, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    result = {}

    for pos in POSITIONS:
        # GC-15 = last 15 days, consistent with our player stats window
        rows = [
            r for r in soup.select("#data-table tbody tr")
            if "GC-15" in r.get("class", []) and pos in r.get("class", [])
        ]
        # Sort by pts descending to assign rank (1 = most pts allowed = easiest matchup)
        team_pts = []
        for row in rows:
            cells = row.select("td")
            if len(cells) < 3:
                continue

            # Team name (strip the logo span text)
            team_cell = cells[0]
            logo = team_cell.select_one("span")
            if logo:
                logo.decompose()
            team_name = team_cell.get_text(strip=True)

            # PTS allowed (3rd column, index 2)
            pts_text = cells[2].get_text(strip=True)
            try:
                pts = float(pts_text)
            except ValueError:
                continue

            team_pts.append((team_name, pts))

        # Rank: highest pts allowed = rank 1 (worst defense = best matchup)
        team_pts.sort(key=lambda x: x[1], reverse=True)
        result[pos] = {}
        for rank, (team_name, pts) in enumerate(team_pts, start=1):
            result[pos][team_name] = {"pts": pts, "rank": rank}

    return result
