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
    return os.getenv("ODDS_API_KEY")


def get_event_ids(games):
    """
    Fetches today's NBA events from The Odds API and maps them to tricodes.

    Only returns event IDs for games present in the input `games` list.
    Returns {(away_tricode, home_tricode): event_id}.
    Returns {} on any HTTP error (all lines will show as N/A).
    """
    api_key = _get_api_key()
    if not api_key:
        print("  [odds] WARNING: ODDS_API_KEY not set — skipping lines")
        return {}

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


MARKET_TO_STAT = {
    "player_points": "pts",
    "player_assists": "ast",
    "player_rebounds": "reb",
    "player_threes": "three_pt",
}

ALL_MARKETS = ",".join(MARKET_TO_STAT.keys())

STAT_KEYS = list(MARKET_TO_STAT.values())


def get_player_lines(stats, event_ids):
    """
    Fetches consensus over/under lines for points, assists, rebounds, and threes.

    Parameters
    ----------
    stats : dict
        {"pts": [...], "ast": [...], "reb": [...], "three_pt": [...]}
        Each entry has "player_name" and "game" keys.
    event_ids : dict
        {(away_tricode, home_tricode): event_id}

    Returns
    -------
    dict
        {player_name: {"pts": val, "pts_odds": price, "ast": val, "ast_odds": price,
                        "reb": val, "reb_odds": price, "three_pt": val, "three_pt_odds": price}}
        val/price is None when the market is unavailable for that player.
    """
    api_key = _get_api_key()
    if not api_key:
        return {}

    # Build game-to-players mapping from all stat arrays
    games_to_players = {}
    for stat_key, entries in stats.items():
        for entry in entries:
            game_str = entry.get("game", "")
            player_name = entry.get("player_name", "")
            if game_str and player_name:
                games_to_players.setdefault(game_str, set()).add(player_name)

    result = {}

    for game_str, player_names in games_to_players.items():
        parts = game_str.split(" @ ")
        if len(parts) != 2:
            continue
        away_tc, home_tc = parts
        event_id = event_ids.get((away_tc, home_tc))
        if not event_id:
            continue

        try:
            resp = requests.get(
                f"{BASE_URL}/sports/basketball_nba/events/{event_id}/odds",
                params={
                    "apiKey": api_key,
                    "regions": "eu",
                    "markets": ALL_MARKETS,
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

        # Collect lines per player per stat across all bookmakers
        # {player: {stat_key: [(point, price), ...]}}
        player_values = {name: {s: [] for s in STAT_KEYS} for name in player_names}

        for bookmaker in bookmakers:
            for market in bookmaker.get("markets", []):
                market_key = market.get("key", "")
                stat_key = MARKET_TO_STAT.get(market_key)
                if stat_key is None:
                    continue
                for outcome in market.get("outcomes", []):
                    desc = outcome.get("description", "")
                    point = outcome.get("point")
                    if point is None:
                        continue
                    # Only consider "Over" outcomes to avoid duplicating lines
                    if outcome.get("name", "").lower() != "over":
                        continue
                    price = outcome.get("price")
                    for name in player_names:
                        if name.lower() in desc.lower():
                            player_values[name][stat_key].append(
                                (float(point), price)
                            )

        for name, stat_map in player_values.items():
            if name not in result:
                result[name] = {s: None for s in STAT_KEYS}
                for s in STAT_KEYS:
                    result[name][f"{s}_odds"] = None

            for stat_key, pairs in stat_map.items():
                if not pairs:
                    continue
                points = [p for p, _ in pairs]
                prices = [pr for _, pr in pairs if pr is not None]

                modes = statistics.multimode(points)
                consensus_line = modes[0] if len(modes) == 1 else statistics.median(points)
                result[name][stat_key] = consensus_line

                if prices:
                    result[name][f"{stat_key}_odds"] = round(
                        statistics.median(prices), 2
                    )

    return result
