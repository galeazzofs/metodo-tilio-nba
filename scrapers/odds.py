import os
import statistics
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://api.the-odds-api.com/v4"

TRICODE_TO_API_NAME = {
    "ATL": "Atlanta Hawks",
    "BOS": "Boston Celtics",
    "BKN": "Brooklyn Nets",
    "CHA": "Charlotte Hornets",
    "CHI": "Chicago Bulls",
    "CLE": "Cleveland Cavaliers",
    "DAL": "Dallas Mavericks",
    "DEN": "Denver Nuggets",
    "DET": "Detroit Pistons",
    "GSW": "Golden State Warriors",
    "HOU": "Houston Rockets",
    "IND": "Indiana Pacers",
    "LAC": "Los Angeles Clippers",
    "LAL": "Los Angeles Lakers",
    "MEM": "Memphis Grizzlies",
    "MIA": "Miami Heat",
    "MIL": "Milwaukee Bucks",
    "MIN": "Minnesota Timberwolves",
    "NOP": "New Orleans Pelicans",
    "NYK": "New York Knicks",
    "OKC": "Oklahoma City Thunder",
    "ORL": "Orlando Magic",
    "PHI": "Philadelphia 76ers",
    "PHX": "Phoenix Suns",
    "POR": "Portland Trail Blazers",
    "SAC": "Sacramento Kings",
    "SAS": "San Antonio Spurs",
    "TOR": "Toronto Raptors",
    "UTA": "Utah Jazz",
    "WAS": "Washington Wizards",
}


def _get_api_key():
    key = os.getenv("ODDS_API_KEY")
    if not key:
        raise RuntimeError(
            "ODDS_API_KEY is not set. Add it to your .env file. "
            "Get a free key at https://the-odds-api.com"
        )
    return key


def get_event_ids(games):
    """
    Fetches today's NBA events from The Odds API and maps them to tricodes.

    Only returns event IDs for games present in the input `games` list.
    Returns {(away_tricode, home_tricode): event_id}.
    Returns {} on any HTTP error (all lines will show as N/A).
    """
    api_key = _get_api_key()

    # Build set of today's games we care about, keyed by (away_tc, home_tc)
    wanted = {
        (g["away_tricode"], g["home_tricode"])
        for g in games
        if g.get("away_tricode") and g.get("home_tricode")
    }

    try:
        resp = requests.get(
            f"{BASE_URL}/sports/basketball_nba/events",
            params={"apiKey": api_key},
            timeout=10,
        )
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"  [odds] WARNING: could not fetch events — {e}")
        return {}

    print(f"  [odds] requests remaining: {resp.headers.get('x-requests-remaining', 'unknown')}")

    api_events = resp.json()

    # Build reverse lookup: API name → tricode
    name_to_tricode = {v: k for k, v in TRICODE_TO_API_NAME.items()}

    result = {}
    for event in api_events:
        away_api = event.get("away_team", "")
        home_api = event.get("home_team", "")
        away_tc = name_to_tricode.get(away_api)
        home_tc = name_to_tricode.get(home_api)
        if away_tc and home_tc and (away_tc, home_tc) in wanted:
            result[(away_tc, home_tc)] = event["id"]

    return result


def get_player_lines(candidates, event_ids):
    """
    Fetches the consensus points over/under line for each candidate.

    Returns {player_name: line_value}.
    Players not found in any bookmaker's props are omitted (shown as N/A).
    Returns {} on any HTTP error or quota exhaustion.
    """
    api_key = _get_api_key()

    # Group candidates by game to deduplicate API calls
    games_to_players = {}
    for c in candidates:
        game_str = c["game"]  # e.g. "BOS @ OKC"
        games_to_players.setdefault(game_str, []).append(c["player"])

    result = {}

    for game_str, player_names in games_to_players.items():
        away_tc, home_tc = game_str.split(" @ ")
        event_id = event_ids.get((away_tc, home_tc))
        if not event_id:
            continue

        try:
            resp = requests.get(
                f"{BASE_URL}/sports/basketball_nba/events/{event_id}/odds",
                params={
                    "apiKey": api_key,
                    "regions": "eu",
                    "markets": "player_points",
                },
                timeout=10,
            )
            if resp.status_code == 429:
                print("[odds] quota exceeded — HTTP 429")
                return {}
            resp.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"  [odds] WARNING: could not fetch odds for {game_str} — {e}")
            return {}

        data = resp.json()
        bookmakers = data.get("bookmakers", [])

        # Collect lines per player across all bookmakers
        player_values = {name: [] for name in player_names}

        for bookmaker in bookmakers:
            for market in bookmaker.get("markets", []):
                if market.get("key") != "player_points":
                    continue
                for outcome in market.get("outcomes", []):
                    desc = outcome.get("description", "")
                    point = outcome.get("point")
                    if point is None:
                        continue
                    for name in player_names:
                        if name.lower() in desc.lower():
                            player_values[name].append(float(point))

        for name, values in player_values.items():
            if not values:
                continue
            modes = statistics.multimode(values)
            if len(modes) == 1:
                result[name] = modes[0]
            else:
                result[name] = statistics.median(values)

    return result
