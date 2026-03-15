from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

ROTOWIRE_URL = "https://www.rotowire.com/basketball/nba-lineups.php"


def get_projected_lineups():
    """
    Scrapes RotoWire for tonight's projected lineups.

    Returns a dict keyed by team tricode:
    {
        'CLE': {
            'team_name': 'Cavaliers',
            'starters': [
                {'name': 'James Harden', 'position': 'PG'},
                ...
            ],
            'questionable': [
                {'name': 'Sam Merrill', 'position': 'G', 'status': 'Ques'},
                ...
            ],
            'out': [
                {'name': 'Jarrett Allen', 'position': 'C', 'status': 'Out'},
                ...
            ],
        },
        ...
    }
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()
        page.goto(ROTOWIRE_URL, wait_until="domcontentloaded", timeout=60000)
        try:
            page.wait_for_selector(".lineup.is-nba", timeout=15000)
        except Exception:
            pass
        html = page.content()
        browser.close()

    return _parse_lineups(html)


def _parse_player(li):
    """Extract name, position, and status from a lineup player <li>."""
    name_el = li.select_one("a")
    pos_el = li.select_one(".lineup__pos")
    status_el = li.select_one(".lineup__inj")

    name = name_el["title"] if name_el and name_el.get("title") else (name_el.get_text(strip=True) if name_el else "Unknown")
    position = pos_el.get_text(strip=True) if pos_el else ""
    status = status_el.get_text(strip=True) if status_el else "Active"

    return {"name": name, "position": position, "status": status}


def _parse_team_list(block, side):
    """Parse one side ('is-visit' or 'is-home') of a game block."""
    # Tricode
    team_el = block.select_one(f".lineup__team.{side}")
    tricode = team_el.select_one(".lineup__abbr").get_text(strip=True) if team_el else "???"

    # Full team name (strip the win-loss span)
    mteam_el = block.select_one(f".lineup__mteam.{side}")
    if mteam_el:
        wl = mteam_el.select_one(".lineup__wl")
        if wl:
            wl.decompose()
        team_name = mteam_el.get_text(strip=True)
    else:
        team_name = tricode

    # Player list
    player_list = block.select_one(f".lineup__list.{side}")
    starters, questionable, out = [], [], []

    if player_list:
        for li in player_list.select("li.lineup__player"):
            classes = li.get("class", [])
            player = _parse_player(li)

            if "is-pct-play-100" in classes:
                starters.append(player)
            elif "is-pct-play-50" in classes:
                questionable.append(player)
            elif "is-pct-play-0" in classes:
                out.append(player)

    return tricode, {
        "team_name": team_name,
        "starters": starters,
        "questionable": questionable,
        "out": out,
    }


def _parse_lineups(html):
    soup = BeautifulSoup(html, "html.parser")
    lineups = {}

    for block in soup.select(".lineup.is-nba"):
        for side in ["is-visit", "is-home"]:
            tricode, data = _parse_team_list(block, side)
            if tricode != "???":
                lineups[tricode] = data

    return lineups
