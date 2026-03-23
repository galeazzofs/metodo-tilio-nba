import math
import time
from datetime import datetime, timedelta, timezone
from nba_api.live.nba.endpoints import scoreboard
from nba_api.stats.endpoints import (
    scoreboardv2,
    shotchartdetail,
    commonteamroster,
    playergamelog,
    leaguedashteamshotlocations,
    leaguedashplayerstats,
    leaguestandingsv3,
)

# UTC-3 (Brasília — sem DST)
BRT = timezone(timedelta(hours=-3))

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

    Uses scoreboardv2 with an explicit date (today in BRT) so that late-night
    NBA games from the previous day are never pulled after midnight BRT.
    The NBA Live ScoreBoard (without date param) keeps showing the previous
    "game day" until ~6 AM ET, which caused stale results in BRT mornings.

    [
        {
            'game_id': ...,
            'home_team': 'Lakers', 'home_team_id': ..., 'home_tricode': 'LAL',
            'away_team': 'Celtics', 'away_team_id': ..., 'away_tricode': 'BOS',
        },
        ...
    ]
    """
    today_brt = datetime.now(BRT).strftime("%m/%d/%Y")
    print(f"  [date] Buscando jogos para {today_brt} (BRT)")

    time.sleep(DELAY)
    board = _retry(lambda: scoreboardv2.ScoreboardV2(game_date=today_brt))
    header = board.game_header.get_data_frame()

    if header.empty:
        return []

    result = []
    for _, row in header.iterrows():
        result.append({
            "game_id": str(row["GAME_ID"]),
            "home_team_id": int(row["HOME_TEAM_ID"]),
            "away_team_id": int(row["VISITOR_TEAM_ID"]),
        })

    # Enrich with team names and tricodes from the static list
    from nba_api.stats.static import teams as nba_teams_static
    team_map = {t["id"]: t for t in nba_teams_static.get_teams()}

    for game in result:
        home = team_map.get(game["home_team_id"], {})
        away = team_map.get(game["away_team_id"], {})
        game["home_team"] = home.get("nickname", "Unknown")
        game["home_tricode"] = home.get("abbreviation", "???")
        game["away_team"] = away.get("nickname", "Unknown")
        game["away_tricode"] = away.get("abbreviation", "???")

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


def get_player_season_data():
    """
    Returns (season_minutes, starter_ids):
      - season_minutes: {player_id: avg_min_per_game} for players with >= 5 GP
      - starter_ids:    set of player_ids who start > 50% of their games

    Uses two LeagueDashPlayerStats calls:
      1. All games → total GP and minutes per player
      2. starter_bench_nullable="Starters" → GP in that split = games started

    A player is classified as a starter if they started more than half their
    games this season (GS / GP > 0.5). This is more accurate than a minutes
    threshold because 6th-man / high-usage bench players (e.g. 28+ min/g off
    the bench) are correctly identified as bench players.
    """
    time.sleep(DELAY)
    all_df = _retry(lambda: leaguedashplayerstats.LeagueDashPlayerStats(
        season=SEASON,
        season_type_all_star="Regular Season",
        per_mode_detailed="PerGame",
    ).get_data_frames()[0])

    time.sleep(DELAY)
    starters_df = _retry(lambda: leaguedashplayerstats.LeagueDashPlayerStats(
        season=SEASON,
        season_type_all_star="Regular Season",
        per_mode_detailed="PerGame",
        starter_bench_nullable="Starters",
    ).get_data_frames()[0])

    # Total GP and minutes per player
    season_minutes = {}
    total_gp = {}
    for _, row in all_df.iterrows():
        gp = int(row["GP"])
        if gp < 5:
            continue
        pid = int(row["PLAYER_ID"])
        season_minutes[pid] = round(float(row["MIN"]), 1)
        total_gp[pid] = gp

    # Games started per player (GP in the "Starters" split = number of starts)
    games_started = {int(row["PLAYER_ID"]): int(row["GP"]) for _, row in starters_df.iterrows()}

    # Starter = started > 50% of games
    starter_ids = set()
    for pid, gp in total_gp.items():
        gs = games_started.get(pid, 0)
        if gs > gp * 0.5:
            starter_ids.add(pid)

    return season_minutes, starter_ids


def get_team_defense_vs_position(last_n_games=15):
    """
    Fetches how much each team concedes per position (PG, SG, SF, PF, C)
    in AST, REB, 3PM, and 3PA over the last N games.

    Returns nested dict:
    {
        team_id: {
            "PG": {"ast": X, "reb": Y, "three_pm": Z, "three_pa": W,
                   "rank_ast": N, "rank_reb": N, "rank_three_pm": N, "rank_three_pa": N},
            "SG": {...}, "SF": {...}, "PF": {...}, "C": {...},
        },
        ...
    }

    Rank 1 = highest value = worst defense = best matchup for the attacker.
    """
    positions = ["PG", "SG", "SF", "PF", "C"]
    stat_cols = {"AST": "ast", "REB": "reb", "FG3M": "three_pm", "FG3A": "three_pa"}

    # Collect per-position, per-team averages
    # pos_data[position] = {team_id: {"ast": X, "reb": Y, ...}}
    pos_data = {}

    for position in positions:
        time.sleep(DELAY)
        df = _retry(lambda pos=position: leaguedashplayerstats.LeagueDashPlayerStats(
            per_mode_detailed="PerGame",
            season=SEASON,
            last_n_games=last_n_games,
            player_position_nullable=pos,
            measure_type_detailed_defense="Opponent",
        ).get_data_frames()[0])

        # Group by TEAM_ID and average in case of player-level rows
        grouped = df.groupby("TEAM_ID")[list(stat_cols.keys())].mean().reset_index()

        team_stats = {}
        for _, row in grouped.iterrows():
            team_id = int(row["TEAM_ID"])
            team_stats[team_id] = {
                mapped: round(float(row[col]), 1) for col, mapped in stat_cols.items()
            }
        pos_data[position] = team_stats

    # Compute ranks per position per stat (rank 1 = highest value)
    result = {}
    for position in positions:
        team_stats = pos_data[position]
        team_ids = sorted(team_stats.keys())

        for stat_key in stat_cols.values():
            sorted_teams = sorted(team_ids, key=lambda tid: team_stats[tid][stat_key], reverse=True)
            for rank, tid in enumerate(sorted_teams, start=1):
                team_stats[tid][f"rank_{stat_key}"] = rank

        for tid in team_ids:
            if tid not in result:
                result[tid] = {}
            result[tid][position] = team_stats[tid]

    return result


def get_player_recent_stats(player_id, last_n_games=15):
    """
    Returns a player's average stats over their last N games plus the season avg pts.
    {'pts': 14.2, 'reb': 5.1, 'ast': 3.0, 'min': 28.4, 'games': 15, 'season_avg_pts': 12.8}
    """
    time.sleep(DELAY)
    full_df = _retry(lambda: playergamelog.PlayerGameLog(
        player_id=player_id,
        season=SEASON,
        season_type_all_star="Regular Season",
    ).get_data_frames()[0])

    if full_df.empty:
        return {}

    season_avg_pts = round(float(full_df["PTS"].mean()), 1)
    season_avg_ast = round(float(full_df["AST"].mean()), 1)
    season_avg_reb = round(float(full_df["REB"].mean()), 1)
    season_avg_three_pm = round(float(full_df["FG3M"].mean()), 1)
    season_avg_three_pa = round(float(full_df["FG3A"].mean()), 1)
    df = full_df.head(last_n_games)

    return {
        "pts": round(float(df["PTS"].mean()), 1),
        "reb": round(float(df["REB"].mean()), 1),
        "ast": round(float(df["AST"].mean()), 1),
        "min": round(float(df["MIN"].astype(float).mean()), 1),
        "three_pm": round(float(df["FG3M"].mean()), 1),
        "three_pa": round(float(df["FG3A"].mean()), 1),
        "games": len(df),
        "season_avg_pts": season_avg_pts,
        "season_avg_ast": season_avg_ast,
        "season_avg_reb": season_avg_reb,
        "season_avg_three_pm": season_avg_three_pm,
        "season_avg_three_pa": season_avg_three_pa,
    }


def get_conference_standings():
    """
    Returns per-team standing data keyed by team_id, for use by the stake filter.

    {
        team_id: {
            "team_id": int,
            "conference": "East" | "West",
            "seed": int,                       # 1–15 within conference
            "wins": int,
            "losses": int,
            "games_remaining": int,            # 82 - wins - losses
            "games_back_from_above": float | None,   # None for seed 1
            "games_ahead_of_below": float | None,    # None for seed 15
        },
        ...
    }

    ConferenceGamesBack for the conference leader is returned by the API as
    None or "-" — both are treated as 0.0 for gap computation.
    """
    time.sleep(DELAY)
    df = _retry(lambda: leaguestandingsv3.LeagueStandingsV3(
        season=SEASON,
        season_type="Regular Season",
    ).get_data_frames()[0])

    def _to_float(val):
        """Convert API ConferenceGamesBack to float; treat None, NaN and '-' as 0.0."""
        if val is None:
            return 0.0
        try:
            if math.isnan(float(val)):
                return 0.0
        except (TypeError, ValueError):
            pass
        if str(val).strip() == "-":
            return 0.0
        return float(val)

    # Group by conference, sort by seed, compute adjacent gaps
    result = {}
    for conf in ("East", "West"):
        conf_rows = df[df["Conference"] == conf].copy()
        conf_rows = conf_rows.sort_values("PlayoffRank").reset_index(drop=True)
        gb_values = [_to_float(row["ConferenceGamesBack"]) for _, row in conf_rows.iterrows()]

        for i, (_, row) in enumerate(conf_rows.iterrows()):
            team_id = int(row["TeamID"])
            seed = int(row["PlayoffRank"])
            wins = int(row["WINS"])
            losses = int(row["LOSSES"])

            games_back_from_above = (gb_values[i] - gb_values[i - 1]) if i > 0 else None
            games_ahead_of_below = (gb_values[i + 1] - gb_values[i]) if i < len(gb_values) - 1 else None

            result[team_id] = {
                "team_id": team_id,
                "conference": conf,
                "seed": seed,
                "wins": wins,
                "losses": losses,
                "games_remaining": max(0, 82 - wins - losses),
                "games_back_from_above": games_back_from_above,
                "games_ahead_of_below": games_ahead_of_below,
            }

    return result
