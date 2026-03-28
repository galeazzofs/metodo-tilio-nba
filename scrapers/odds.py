import os
import statistics
import time
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

STAT_TO_MARKET = {
    "pts": "player_points",
    "ast": "player_assists",
    "reb": "player_rebounds",
    "three_pt": "player_threes",
}

MARKET_TO_STAT = {v: k for k, v in STAT_TO_MARKET.items()}

STAT_KEYS = list(STAT_TO_MARKET.keys())


def _get_api_key():
    return os.getenv("ODDS_API_KEY")


def get_event_ids(games):
    """
    Fetches today's NBA events from The Odds API and maps them to tricodes.

    Only returns event IDs for games present in the input `games` list.
    Returns {(away_tricode, home_tricode): event_id}.
    The /events endpoint is FREE and does not consume usage credits.
    """
    api_key = _get_api_key()
    if not api_key:
        print("  [odds] WARNING: ODDS_API_KEY not set — skipping lines")
        return {}

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


def get_game_moneylines(games):
    """
    Fetches moneyline (h2h) odds for today's NBA games.

    Returns {(away_tricode, home_tricode): lowest_odd} where lowest_odd
    is the minimum decimal price (the favorite) across all bookmakers.
    Keys always use the NBA API's (away, home) ordering regardless of
    how The Odds API labels home/away.
    Returns float values. Empty dict on failure.
    Costs 1 API request credit per call.
    """
    api_key = _get_api_key()
    if not api_key:
        print("  [odds] WARNING: ODDS_API_KEY not set — skipping moneylines")
        return {}

    # Build lookup with BOTH orderings of (team_a, team_b) to handle
    # cases where The Odds API and NBA API disagree on home/away.
    # Maps any ordering → the canonical NBA API (away, home) key.
    canonical_key = {}
    for g in games:
        away = g.get("away_tricode")
        home = g.get("home_tricode")
        if away and home:
            canonical_key[(away, home)] = (away, home)
            canonical_key[(home, away)] = (away, home)

    try:
        resp = requests.get(
            f"{BASE_URL}/sports/basketball_nba/odds",
            params={
                "apiKey": api_key,
                "markets": "h2h",
                "oddsFormat": "decimal",
            },
            timeout=10,
        )
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"  [odds] WARNING: could not fetch moneylines — {e}")
        return {}

    print(f"  [odds] moneylines — requests remaining: {resp.headers.get('x-requests-remaining', 'unknown')}")

    api_events = resp.json()
    name_to_tricode = {v: k for k, v in TRICODE_TO_API_NAME.items()}

    result = {}
    for event in api_events:
        away_api = event.get("away_team", "")
        home_api = event.get("home_team", "")
        away_tc = name_to_tricode.get(away_api)
        home_tc = name_to_tricode.get(home_api)

        if not away_tc or not home_tc:
            continue

        # Look up canonical key — handles home/away order mismatch
        canon = canonical_key.get((away_tc, home_tc))
        if canon is None:
            continue

        all_prices = []
        for bookmaker in event.get("bookmakers", []):
            for market in bookmaker.get("markets", []):
                if market.get("key") != "h2h":
                    continue
                for outcome in market.get("outcomes", []):
                    price = outcome.get("price")
                    if price is not None:
                        all_prices.append(float(price))

        if all_prices:
            result[canon] = min(all_prices)

    return result


def _fetch_odds(api_key, event_id, markets_csv, game_label):
    """Fetch odds for a single event with retry on 429. Returns response JSON or None."""
    for attempt in range(3):
        try:
            resp = requests.get(
                f"{BASE_URL}/sports/basketball_nba/events/{event_id}/odds",
                params={
                    "apiKey": api_key,
                    "regions": "us",
                    "markets": markets_csv,
                    "oddsFormat": "american",
                },
                timeout=10,
            )
            if resp.status_code == 429:
                remaining = resp.headers.get("x-requests-remaining", "?")
                if remaining != "?" and int(remaining) <= 0:
                    print(f"  [odds] quota exceeded — 0 requests remaining")
                    return None
                wait = 2 ** attempt
                print(f"  [odds] rate-limited (429), retrying in {wait}s...")
                time.sleep(wait)
                continue
            resp.raise_for_status()

            remaining = resp.headers.get("x-requests-remaining", "?")
            n_markets = len(markets_csv.split(","))
            print(f"  [odds] {game_label} — {n_markets} market(s), remaining: {remaining}")
            return resp.json()
        except requests.exceptions.RequestException as e:
            print(f"  [odds] WARNING: could not fetch odds for {game_label} — {e}")
            return None

    print(f"  [odds] WARNING: giving up on {game_label} after 3 retries")
    return None


def get_player_lines(stats, event_ids):
    """
    Fetches consensus over/under lines ONLY for candidates found by the engine.

    Cost-optimised: requests only the markets (stat types) that have candidates
    in each game, instead of requesting all 4 markets for every game.

    API cost = number_of_markets × number_of_regions (1) per game request.
    """
    api_key = _get_api_key()
    if not api_key:
        return {}

    # Build per-game mapping: game_str → {stat_keys needed, player_names}
    game_needs = {}  # game_str → {"stats": set(), "players": set()}
    for stat_key, entries in stats.items():
        for entry in entries:
            game_str = entry.get("game", "")
            player_name = entry.get("player_name", "")
            if game_str and player_name:
                bucket = game_needs.setdefault(game_str, {"stats": set(), "players": set()})
                bucket["stats"].add(stat_key)
                bucket["players"].add(player_name)

    if not game_needs:
        print("  [odds] no candidates — skipping odds fetch")
        return {}

    # Estimate cost
    total_cost = sum(len(b["stats"]) for b in game_needs.values())
    print(f"  [odds] fetching lines for {len(game_needs)} game(s), estimated cost: {total_cost} request(s)")

    result = {}

    for game_str, bucket in game_needs.items():
        parts = game_str.split(" @ ")
        if len(parts) != 2:
            continue
        away_tc, home_tc = parts
        event_id = event_ids.get((away_tc, home_tc))
        if not event_id:
            continue

        # Build markets CSV with only the stat types we need for this game
        markets_csv = ",".join(
            STAT_TO_MARKET[s] for s in bucket["stats"] if s in STAT_TO_MARKET
        )
        if not markets_csv:
            continue

        player_names = bucket["players"]

        data = _fetch_odds(api_key, event_id, markets_csv, game_str)
        if data is None:
            continue

        time.sleep(1)  # avoid rate-limiting between games

        bookmakers = data.get("bookmakers", [])

        # Collect lines per player per stat across all bookmakers
        player_values = {name: {s: [] for s in bucket["stats"]} for name in player_names}

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
