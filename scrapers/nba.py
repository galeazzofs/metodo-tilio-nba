import time
from nba_api.live.nba.endpoints import scoreboard
from nba_api.stats.endpoints import (
    shotchartdetail,
    commonteamroster,
    playergamelog,
    leaguedashteamshotlocations,
    leaguedashplayerstats,
)

SEASON = "2025-26"
DELAY = 1.0  # seconds between API calls to avoid rate limiting


def _retry(fn, retries=3, backoff=5):
    """Call fn(), retrying up to `retries` times on exception."""
    for attempt in range(retries):
        try:
            return fn()
        except Exception as e:
            if attempt < retries - 1:
                wait = backoff * (attempt + 1)
                print(f"    [retry {attempt + 1}/{retries}] {e} — waiting {wait}s...")
                time.sleep(wait)
            else:
                raise


def get_todays_games():
    """
    Returns a list of today's games with team info.
    [
        {
            'game_id': ...,
            'home_team': 'Lakers', 'home_team_id': ..., 'home_tricode': 'LAL',
            'away_team': 'Celtics', 'away_team_id': ..., 'away_tricode': 'BOS',
        },
        ...
    ]
    """
    board = scoreboard.ScoreBoard()
    games = board.games.get_dict()

    result = []
    for game in games:
        result.append({
            "game_id": game["gameId"],
            "home_team": game["homeTeam"]["teamName"],
            "home_team_id": game["homeTeam"]["teamId"],
            "home_tricode": game["homeTeam"]["teamTricode"],
            "away_team": game["awayTeam"]["teamName"],
            "away_team_id": game["awayTeam"]["teamId"],
            "away_tricode": game["awayTeam"]["teamTricode"],
        })
    return result



def get_team_roster(team_id):
    """
    Returns a team's current roster.
    [
        {'player_id': ..., 'player_name': ..., 'position': ..., 'num': ...},
        ...
    ]
    """
    time.sleep(DELAY)
    roster = commonteamroster.CommonTeamRoster(team_id=team_id, season=SEASON)
    df = roster.get_data_frames()[0]

    result = []
    for _, row in df.iterrows():
        result.append({
            "player_id": row["PLAYER_ID"],
            "player_name": row["PLAYER"],
            "position": row["POSITION"],
            "num": row["NUM"],
        })
    return result


def get_player_shot_zones(player_id, last_n_games=15):
    """
    Returns a player's shot zone breakdown for their last N games.
    {
        'Restricted Area':     {'attempts': 40, 'made': 28, 'pct': 70.0, 'frequency': 35.0},
        'In The Paint (Non-RA)': {...},
        'Mid-Range':           {...},
        'Left Corner 3':       {...},
        'Right Corner 3':      {...},
        'Above the Break 3':   {...},
    }
    """
    time.sleep(DELAY)
    df = _retry(lambda: shotchartdetail.ShotChartDetail(
        player_id=player_id,
        team_id=0,
        season_type_all_star="Regular Season",
        season_nullable=SEASON,
        last_n_games=last_n_games,
        context_measure_simple="FGA",
    ).get_data_frames()[0])

    if df.empty:
        return {}

    total_attempts = len(df)
    zone_stats = (
        df.groupby("SHOT_ZONE_BASIC")
        .agg(attempts=("SHOT_ATTEMPTED_FLAG", "sum"), made=("SHOT_MADE_FLAG", "sum"))
        .reset_index()
    )

    result = {}
    for _, row in zone_stats.iterrows():
        pct = round(row["made"] / row["attempts"] * 100, 1) if row["attempts"] > 0 else 0.0
        freq = round(row["attempts"] / total_attempts * 100, 1)
        result[row["SHOT_ZONE_BASIC"]] = {
            "attempts": int(row["attempts"]),
            "made": int(row["made"]),
            "pct": pct,
            "frequency": freq,
        }
    return result


def get_all_teams_defense_zones(last_n_games=15):
    """
    Fetches zone-level defensive data for all 30 teams in one call.
    Returns a dict keyed by team_id:
    {
        1610612737: {
            'Restricted Area':     {'fga': 29.9, 'fgm': 19.1, 'pct': 0.641},
            'Mid-Range':           {...},
            'Above the Break 3':   {...},
            ...
        },
        ...
    }
    """
    time.sleep(DELAY)
    df = _retry(lambda: leaguedashteamshotlocations.LeagueDashTeamShotLocations(
        distance_range="By Zone",
        measure_type_simple="Opponent",
        season=SEASON,
        last_n_games=last_n_games,
        per_mode_detailed="PerGame",
    ).get_data_frames()[0])

    zones_of_interest = [
        "Restricted Area",
        "In The Paint (Non-RA)",
        "Mid-Range",
        "Left Corner 3",
        "Right Corner 3",
        "Above the Break 3",
    ]

    result = {}
    for _, row in df.iterrows():
        team_id = int(row[("", "TEAM_ID")])
        team_zones = {}
        for zone in zones_of_interest:
            try:
                fgm = float(row[(zone, "OPP_FGM")])
                fga = float(row[(zone, "OPP_FGA")])
                pct = float(row[(zone, "OPP_FG_PCT")])
                team_zones[zone] = {"fgm": fgm, "fga": fga, "pct": pct}
            except (KeyError, TypeError):
                pass
        result[team_id] = team_zones

    return result


STARTER_MIN_THRESHOLD = 27.0  # season avg min/game above which = regular starter

def get_player_season_stats():
    """
    Returns {player_id: {"min": avg_min, "pts": avg_pts}} for all players
    with >= 5 games played.

    LeagueDashPlayerStats does not expose GS (games started), so we use
    season-long minutes per game as a reliable proxy for starter status:
      >= 27 min/game  →  regular starter (skip in engine)
      <  27 min/game  →  bench player   (eligible if team has injuries)
    """
    time.sleep(DELAY)
    df = _retry(lambda: leaguedashplayerstats.LeagueDashPlayerStats(
        season=SEASON,
        season_type_all_star="Regular Season",
        per_mode_detailed="PerGame",
    ).get_data_frames()[0])

    result = {}
    for _, row in df.iterrows():
        gp = int(row["GP"])
        if gp < 5:
            continue  # too few games for a reliable reading
        result[int(row["PLAYER_ID"])] = {
            "min": round(float(row["MIN"]), 1),
            "pts": round(float(row["PTS"]), 1),
        }
    return result


def get_player_recent_stats(player_id, last_n_games=15):
    """
    Returns a player's average stats over their last N games.
    {'pts': 14.2, 'reb': 5.1, 'ast': 3.0, 'min': 28.4, 'games': 15}
    """
    time.sleep(DELAY)
    df = _retry(lambda: playergamelog.PlayerGameLog(
        player_id=player_id,
        season=SEASON,
        season_type_all_star="Regular Season",
    ).get_data_frames()[0].head(last_n_games))

    if df.empty:
        return {}

    return {
        "pts": round(float(df["PTS"].mean()), 1),
        "reb": round(float(df["REB"].mean()), 1),
        "ast": round(float(df["AST"].mean()), 1),
        "min": round(float(df["MIN"].astype(float).mean()), 1),
        "games": len(df),
    }
