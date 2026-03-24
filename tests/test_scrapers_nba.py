from unittest.mock import patch, MagicMock
import pandas as pd
import pytest
try:
    from scrapers.nba import get_player_season_data
except ImportError:
    get_player_season_data = None
from scrapers.nba import get_conference_standings, get_player_recent_stats, get_team_defense_vs_position, get_team_defense_tracking


def _make_standings_df(rows):
    """
    rows: list of dicts with keys:
      TeamID, Conference, PlayoffRank, WINS, LOSSES, ConferenceGamesBack
    """
    return pd.DataFrame(rows)


def test_get_conference_standings_basic_structure():
    """Two teams, one per conference — correct keys and types."""
    df = _make_standings_df([
        {"TeamID": 1, "Conference": "East", "PlayoffRank": 1,
         "WINS": 50, "LOSSES": 20, "ConferenceGamesBack": None},
        {"TeamID": 2, "Conference": "East", "PlayoffRank": 2,
         "WINS": 48, "LOSSES": 22, "ConferenceGamesBack": 2.0},
    ])
    mock_ep = MagicMock()
    mock_ep.get_data_frames.return_value = [df]

    with patch("scrapers.nba.leaguestandingsv3.LeagueStandingsV3", return_value=mock_ep), \
         patch("scrapers.nba.time.sleep"):
        result = get_conference_standings()

    assert 1 in result
    entry = result[1]
    assert entry["team_id"] == 1
    assert entry["conference"] == "East"
    assert entry["seed"] == 1
    assert entry["wins"] == 50
    assert entry["losses"] == 20
    assert entry["games_remaining"] == 12   # 82 - 50 - 20
    assert entry["games_back_from_above"] is None   # seed 1
    assert isinstance(entry["games_ahead_of_below"], float)


def test_get_conference_standings_seed1_games_back_from_above_is_none():
    """Seed-1 team always has games_back_from_above = None."""
    df = _make_standings_df([
        {"TeamID": 10, "Conference": "East", "PlayoffRank": 1,
         "WINS": 58, "LOSSES": 16, "ConferenceGamesBack": None},
        {"TeamID": 11, "Conference": "East", "PlayoffRank": 2,
         "WINS": 54, "LOSSES": 20, "ConferenceGamesBack": 4.0},
    ])
    mock_ep = MagicMock()
    mock_ep.get_data_frames.return_value = [df]

    with patch("scrapers.nba.leaguestandingsv3.LeagueStandingsV3", return_value=mock_ep), \
         patch("scrapers.nba.time.sleep"):
        result = get_conference_standings()

    assert result[10]["games_back_from_above"] is None
    assert result[10]["games_ahead_of_below"] == 4.0


def test_get_conference_standings_seed15_games_ahead_of_below_is_none():
    """Seed-15 team always has games_ahead_of_below = None."""
    rows = [
        {"TeamID": i, "Conference": "East", "PlayoffRank": i,
         "WINS": max(0, 60 - i * 4), "LOSSES": min(82, 22 + i * 4),
         "ConferenceGamesBack": None if i == 1 else float(i - 1) * 2}
        for i in range(1, 16)
    ]
    df = _make_standings_df(rows)
    mock_ep = MagicMock()
    mock_ep.get_data_frames.return_value = [df]

    with patch("scrapers.nba.leaguestandingsv3.LeagueStandingsV3", return_value=mock_ep), \
         patch("scrapers.nba.time.sleep"):
        result = get_conference_standings()

    # team with PlayoffRank 15 = TeamID 15
    assert result[15]["games_ahead_of_below"] is None


def test_get_conference_standings_none_and_dash_gamesback_treated_as_zero():
    """
    ConferenceGamesBack of None or '-' for the leader must be treated as 0.0
    so adjacent gap computation does not crash.
    """
    df = _make_standings_df([
        {"TeamID": 20, "Conference": "West", "PlayoffRank": 1,
         "WINS": 55, "LOSSES": 19, "ConferenceGamesBack": "-"},   # dash string
        {"TeamID": 21, "Conference": "West", "PlayoffRank": 2,
         "WINS": 52, "LOSSES": 22, "ConferenceGamesBack": 3.0},
    ])
    mock_ep = MagicMock()
    mock_ep.get_data_frames.return_value = [df]

    with patch("scrapers.nba.leaguestandingsv3.LeagueStandingsV3", return_value=mock_ep), \
         patch("scrapers.nba.time.sleep"):
        result = get_conference_standings()

    # gap between seed-1 (0.0) and seed-2 (3.0) = 3.0
    assert result[20]["games_ahead_of_below"] == 3.0
    assert result[21]["games_back_from_above"] == 3.0


def test_get_conference_standings_games_remaining_formula():
    """games_remaining = 82 - wins - losses."""
    df = _make_standings_df([
        {"TeamID": 30, "Conference": "East", "PlayoffRank": 1,
         "WINS": 70, "LOSSES": 10, "ConferenceGamesBack": None},
    ])
    mock_ep = MagicMock()
    mock_ep.get_data_frames.return_value = [df]

    with patch("scrapers.nba.leaguestandingsv3.LeagueStandingsV3", return_value=mock_ep), \
         patch("scrapers.nba.time.sleep"):
        result = get_conference_standings()

    assert result[30]["games_remaining"] == 2   # 82 - 70 - 10


def _make_stats_df(rows):
    """rows: list of (player_id, gp, min_avg, pts_avg)"""
    return pd.DataFrame(
        rows,
        columns=["PLAYER_ID", "GP", "MIN", "PTS"],
    )


def test_returns_season_minutes_for_qualifying_players():
    all_df = _make_stats_df([
        (1, 10, 28.5, 18.2),
        (2, 10, 22.0, 9.4),
    ])
    # Starters split: player 1 started 8/10 games (starter), player 2 started 3/10 (bench)
    starters_df = pd.DataFrame([(1, 8, 28.5, 18.2)], columns=["PLAYER_ID", "GP", "MIN", "PTS"])
    call_count = {"n": 0}
    def fake_endpoint(**kwargs):
        mock = MagicMock()
        if call_count["n"] == 0:
            mock.get_data_frames.return_value = [all_df]
        else:
            mock.get_data_frames.return_value = [starters_df]
        call_count["n"] += 1
        return mock

    with patch("scrapers.nba.leaguedashplayerstats.LeagueDashPlayerStats", side_effect=fake_endpoint), \
         patch("scrapers.nba.time.sleep"), \
         patch("scrapers.nba._retry", side_effect=lambda fn: fn()):
        season_minutes, starter_ids = get_player_season_data()

    assert season_minutes[1] == 28.5
    assert season_minutes[2] == 22.0
    assert 1 in starter_ids
    assert 2 not in starter_ids


def test_excludes_players_with_fewer_than_5_games():
    all_df = _make_stats_df([
        (1, 4, 30.0, 20.0),   # GP < 5 → excluded
        (2, 5, 25.0, 12.0),   # GP == 5 → included
    ])
    starters_df = pd.DataFrame(columns=["PLAYER_ID", "GP", "MIN", "PTS"])
    call_count = {"n": 0}
    def fake_endpoint(**kwargs):
        mock = MagicMock()
        if call_count["n"] == 0:
            mock.get_data_frames.return_value = [all_df]
        else:
            mock.get_data_frames.return_value = [starters_df]
        call_count["n"] += 1
        return mock

    with patch("scrapers.nba.leaguedashplayerstats.LeagueDashPlayerStats", side_effect=fake_endpoint), \
         patch("scrapers.nba.time.sleep"), \
         patch("scrapers.nba._retry", side_effect=lambda fn: fn()):
        season_minutes, starter_ids = get_player_season_data()

    assert 1 not in season_minutes
    assert 2 in season_minutes


def test_rounds_minutes_to_one_decimal():
    all_df = _make_stats_df([(1, 10, 28.456, 17.678)])
    starters_df = pd.DataFrame(columns=["PLAYER_ID", "GP", "MIN", "PTS"])
    call_count = {"n": 0}
    def fake_endpoint(**kwargs):
        mock = MagicMock()
        if call_count["n"] == 0:
            mock.get_data_frames.return_value = [all_df]
        else:
            mock.get_data_frames.return_value = [starters_df]
        call_count["n"] += 1
        return mock

    with patch("scrapers.nba.leaguedashplayerstats.LeagueDashPlayerStats", side_effect=fake_endpoint), \
         patch("scrapers.nba.time.sleep"), \
         patch("scrapers.nba._retry", side_effect=lambda fn: fn()):
        season_minutes, starter_ids = get_player_season_data()

    assert season_minutes[1] == 28.5


# --------------- get_player_recent_stats tests ---------------

def _make_gamelog_df(rows):
    """
    rows: list of dicts with keys PTS, REB, AST, MIN, FG3M, FG3A.
    Returns a DataFrame resembling PlayerGameLog output.
    """
    return pd.DataFrame(rows)


def test_get_player_recent_stats_returns_new_season_avg_fields():
    """season_avg_ast, season_avg_reb, season_avg_three_pm, season_avg_three_pa
    are computed from the FULL dataframe."""
    full_games = [
        {"PTS": 20, "REB": 8, "AST": 5, "MIN": 30, "FG3M": 3, "FG3A": 7},
        {"PTS": 22, "REB": 10, "AST": 7, "MIN": 32, "FG3M": 1, "FG3A": 5},
        {"PTS": 18, "REB": 6, "AST": 3, "MIN": 28, "FG3M": 2, "FG3A": 6},
        {"PTS": 24, "REB": 12, "AST": 9, "MIN": 34, "FG3M": 4, "FG3A": 8},
    ]
    df = _make_gamelog_df(full_games)
    mock_ep = MagicMock()
    mock_ep.get_data_frames.return_value = [df]

    with patch("scrapers.nba.playergamelog.PlayerGameLog", return_value=mock_ep), \
         patch("scrapers.nba.time.sleep"), \
         patch("scrapers.nba._retry", side_effect=lambda fn: fn()):
        result = get_player_recent_stats(player_id=123, last_n_games=2)

    # season averages over all 4 games
    assert result["season_avg_pts"] == 21.0      # (20+22+18+24)/4
    assert result["season_avg_ast"] == 6.0        # (5+7+3+9)/4
    assert result["season_avg_reb"] == 9.0        # (8+10+6+12)/4
    assert result["season_avg_three_pm"] == 2.5   # (3+1+2+4)/4
    assert result["season_avg_three_pa"] == 6.5   # (7+5+6+8)/4


def test_get_player_recent_stats_returns_last_n_three_pt_fields():
    """three_pm and three_pa are computed from only the last_n games."""
    full_games = [
        {"PTS": 20, "REB": 8, "AST": 5, "MIN": 30, "FG3M": 3, "FG3A": 7},
        {"PTS": 22, "REB": 10, "AST": 7, "MIN": 32, "FG3M": 1, "FG3A": 5},
        {"PTS": 18, "REB": 6, "AST": 3, "MIN": 28, "FG3M": 2, "FG3A": 6},
        {"PTS": 24, "REB": 12, "AST": 9, "MIN": 34, "FG3M": 4, "FG3A": 8},
    ]
    df = _make_gamelog_df(full_games)
    mock_ep = MagicMock()
    mock_ep.get_data_frames.return_value = [df]

    with patch("scrapers.nba.playergamelog.PlayerGameLog", return_value=mock_ep), \
         patch("scrapers.nba.time.sleep"), \
         patch("scrapers.nba._retry", side_effect=lambda fn: fn()):
        result = get_player_recent_stats(player_id=123, last_n_games=2)

    # last_n=2 → first 2 rows (head(2))
    assert result["three_pm"] == 2.0   # (3+1)/2
    assert result["three_pa"] == 6.0   # (7+5)/2


def test_get_player_recent_stats_empty_df_returns_empty_dict():
    """Empty gamelog should return {}."""
    df = pd.DataFrame()
    mock_ep = MagicMock()
    mock_ep.get_data_frames.return_value = [df]

    with patch("scrapers.nba.playergamelog.PlayerGameLog", return_value=mock_ep), \
         patch("scrapers.nba.time.sleep"), \
         patch("scrapers.nba._retry", side_effect=lambda fn: fn()):
        result = get_player_recent_stats(player_id=999, last_n_games=10)

    assert result == {}


# --------------- get_team_defense_vs_position tests ---------------

def _make_team_opp_df(rows):
    """
    rows: list of dicts with TEAM_ID, OPP_AST, OPP_REB, OPP_FG3M, OPP_FG3A.
    Returns a DataFrame resembling LeagueDashTeamStats Opponent output.
    """
    return pd.DataFrame(rows)


def test_get_team_defense_vs_position_returns_all_positions():
    """Output has all 5 positions for each team."""
    fake_rows = [
        {"TEAM_ID": 1, "OPP_AST": 5.0, "OPP_REB": 10.0, "OPP_FG3M": 2.0, "OPP_FG3A": 6.0},
        {"TEAM_ID": 2, "OPP_AST": 6.0, "OPP_REB": 9.0, "OPP_FG3M": 3.0, "OPP_FG3A": 7.0},
        {"TEAM_ID": 3, "OPP_AST": 7.0, "OPP_REB": 8.0, "OPP_FG3M": 4.0, "OPP_FG3A": 8.0},
    ]
    df = _make_team_opp_df(fake_rows)
    mock_ep = MagicMock()
    mock_ep.get_data_frames.return_value = [df]

    with patch("scrapers.nba.leaguedashteamstats.LeagueDashTeamStats", return_value=mock_ep), \
         patch("scrapers.nba.time.sleep"), \
         patch("scrapers.nba._retry", side_effect=lambda fn: fn()):
        result = get_team_defense_vs_position(last_n_games=15)

    assert 1 in result
    assert 2 in result
    assert 3 in result
    for team_id in [1, 2, 3]:
        for pos in ["PG", "SG", "SF", "PF", "C"]:
            assert pos in result[team_id], f"Missing position {pos} for team {team_id}"


def test_get_team_defense_vs_position_has_stat_and_rank_keys():
    """Each position entry has ast, reb, three_pm, three_pa and their ranks."""
    fake_rows = [
        {"TEAM_ID": 1, "OPP_AST": 5.0, "OPP_REB": 10.0, "OPP_FG3M": 2.0, "OPP_FG3A": 6.0},
        {"TEAM_ID": 2, "OPP_AST": 6.0, "OPP_REB": 9.0, "OPP_FG3M": 3.0, "OPP_FG3A": 7.0},
        {"TEAM_ID": 3, "OPP_AST": 7.0, "OPP_REB": 8.0, "OPP_FG3M": 4.0, "OPP_FG3A": 8.0},
    ]
    df = _make_team_opp_df(fake_rows)
    mock_ep = MagicMock()
    mock_ep.get_data_frames.return_value = [df]

    with patch("scrapers.nba.leaguedashteamstats.LeagueDashTeamStats", return_value=mock_ep), \
         patch("scrapers.nba.time.sleep"), \
         patch("scrapers.nba._retry", side_effect=lambda fn: fn()):
        result = get_team_defense_vs_position(last_n_games=15)

    expected_keys = {"ast", "reb", "three_pm", "three_pa",
                     "rank_ast", "rank_reb", "rank_three_pm", "rank_three_pa"}
    entry = result[1]["PG"]
    assert set(entry.keys()) == expected_keys


def test_get_team_defense_vs_position_ranks_correctly():
    """Rank 1 = highest value (worst defense / best matchup for attacker)."""
    fake_rows = [
        {"TEAM_ID": 1, "OPP_AST": 5.0, "OPP_REB": 10.0, "OPP_FG3M": 2.0, "OPP_FG3A": 6.0},
        {"TEAM_ID": 2, "OPP_AST": 6.0, "OPP_REB": 9.0, "OPP_FG3M": 3.0, "OPP_FG3A": 7.0},
        {"TEAM_ID": 3, "OPP_AST": 7.0, "OPP_REB": 8.0, "OPP_FG3M": 4.0, "OPP_FG3A": 8.0},
    ]
    df = _make_team_opp_df(fake_rows)
    mock_ep = MagicMock()
    mock_ep.get_data_frames.return_value = [df]

    with patch("scrapers.nba.leaguedashteamstats.LeagueDashTeamStats", return_value=mock_ep), \
         patch("scrapers.nba.time.sleep"), \
         patch("scrapers.nba._retry", side_effect=lambda fn: fn()):
        result = get_team_defense_vs_position(last_n_games=15)

    # For AST: team3=7.0 (rank1), team2=6.0 (rank2), team1=5.0 (rank3)
    pg = result[3]["PG"]
    assert pg["rank_ast"] == 1
    assert result[2]["PG"]["rank_ast"] == 2
    assert result[1]["PG"]["rank_ast"] == 3

    # For REB: team1=10.0 (rank1), team2=9.0 (rank2), team3=8.0 (rank3)
    assert result[1]["PG"]["rank_reb"] == 1
    assert result[2]["PG"]["rank_reb"] == 2
    assert result[3]["PG"]["rank_reb"] == 3


# --------------- get_team_defense_tracking tests ---------------

def _make_passing_df(rows):
    """rows: list of dicts with TEAM_ID, POTENTIAL_AST."""
    return pd.DataFrame(rows)


def _make_rebounding_df(rows):
    """rows: list of dicts with TEAM_ID, REB_CHANCES."""
    return pd.DataFrame(rows)


def test_get_team_defense_tracking_happy_path():
    """Valid DataFrames produce correct structure and ranks."""
    passing_rows = [
        {"TEAM_ID": 1, "POTENTIAL_AST": 50.0},
        {"TEAM_ID": 2, "POTENTIAL_AST": 60.0},
        {"TEAM_ID": 3, "POTENTIAL_AST": 55.0},
    ]
    rebounding_rows = [
        {"TEAM_ID": 1, "REB_CHANCES": 40.0},
        {"TEAM_ID": 2, "REB_CHANCES": 35.0},
        {"TEAM_ID": 3, "REB_CHANCES": 45.0},
    ]
    passing_df = _make_passing_df(passing_rows)
    rebounding_df = _make_rebounding_df(rebounding_rows)

    mock_passing_ep = MagicMock()
    mock_passing_ep.get_data_frames.return_value = [passing_df]

    mock_rebounding_ep = MagicMock()
    mock_rebounding_ep.get_data_frames.return_value = [rebounding_df]

    def fake_league_dash(*args, **kwargs):
        if kwargs.get("pt_measure_type") == "Passing":
            return mock_passing_ep
        return mock_rebounding_ep

    with patch("scrapers.nba.leaguedashptstats.LeagueDashPtStats", side_effect=fake_league_dash), \
         patch("scrapers.nba.time.sleep"), \
         patch("scrapers.nba._retry", side_effect=lambda fn: fn()):
        result = get_team_defense_tracking(last_n_games=15)

    assert result is not None
    assert 1 in result and 2 in result and 3 in result

    # Check keys
    expected_keys = {"potential_ast", "reb_chances", "rank_potential_ast", "rank_reb_chances"}
    assert set(result[1].keys()) == expected_keys

    # Check values
    assert result[2]["potential_ast"] == 60.0
    assert result[3]["reb_chances"] == 45.0

    # Ranks: rank 1 = highest value
    # POTENTIAL_AST: team2=60 (rank1), team3=55 (rank2), team1=50 (rank3)
    assert result[2]["rank_potential_ast"] == 1
    assert result[3]["rank_potential_ast"] == 2
    assert result[1]["rank_potential_ast"] == 3

    # REB_CHANCES: team3=45 (rank1), team1=40 (rank2), team2=35 (rank3)
    assert result[3]["rank_reb_chances"] == 1
    assert result[1]["rank_reb_chances"] == 2
    assert result[2]["rank_reb_chances"] == 3


def test_get_team_defense_tracking_error_returns_none():
    """When the tracking endpoint raises an exception, return None."""
    with patch("scrapers.nba.leaguedashptstats.LeagueDashPtStats", side_effect=Exception("API error")), \
         patch("scrapers.nba.time.sleep"), \
         patch("scrapers.nba._retry", side_effect=lambda fn: fn()):
        result = get_team_defense_tracking(last_n_games=15)

    assert result is None
