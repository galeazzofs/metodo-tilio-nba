from unittest.mock import patch, MagicMock
import pandas as pd
import pytest
try:
    from scrapers.nba import get_player_season_stats
except ImportError:
    get_player_season_stats = None
from scrapers.nba import get_conference_standings


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
        {"TeamID": 2, "Conference": "West", "PlayoffRank": 1,
         "WINS": 48, "LOSSES": 22, "ConferenceGamesBack": None},
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
    assert isinstance(entry["games_ahead_of_below"], (float, type(None)))


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


def test_returns_min_and_pts_for_qualifying_players():
    df = _make_stats_df([
        (1, 10, 28.5, 18.2),
        (2, 10, 22.0, 9.4),
    ])
    mock_endpoint = MagicMock()
    mock_endpoint.get_data_frames.return_value = [df]

    with patch("scrapers.nba.leaguedashplayerstats.LeagueDashPlayerStats", return_value=mock_endpoint):
        result = get_player_season_stats()

    assert result == {
        1: {"min": 28.5, "pts": 18.2},
        2: {"min": 22.0, "pts": 9.4},
    }


def test_excludes_players_with_fewer_than_5_games():
    df = _make_stats_df([
        (1, 4, 30.0, 20.0),   # GP < 5 → excluded
        (2, 5, 25.0, 12.0),   # GP == 5 → included
    ])
    mock_endpoint = MagicMock()
    mock_endpoint.get_data_frames.return_value = [df]

    with patch("scrapers.nba.leaguedashplayerstats.LeagueDashPlayerStats", return_value=mock_endpoint):
        result = get_player_season_stats()

    assert 1 not in result
    assert 2 in result


def test_rounds_values_to_one_decimal():
    df = _make_stats_df([(1, 10, 28.456, 17.678)])
    mock_endpoint = MagicMock()
    mock_endpoint.get_data_frames.return_value = [df]

    with patch("scrapers.nba.leaguedashplayerstats.LeagueDashPlayerStats", return_value=mock_endpoint):
        result = get_player_season_stats()

    assert result[1]["min"] == 28.5
    assert result[1]["pts"] == 17.7
