from unittest.mock import patch, MagicMock
import pandas as pd
from scrapers.nba import get_player_season_stats


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
