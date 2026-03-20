# tests/test_main.py
"""
Wiring smoke tests for main.py.

These tests verify that when filter_games_by_stake returns an empty list,
the expensive downstream functions (lineups, DvP, analysis, odds) are never
called.
"""
from unittest.mock import patch, MagicMock
import main


def test_stake_filter_zero_games_skips_downstream():
    """
    When filter_games_by_stake returns [] (no games with stake),
    main() must return early without calling any downstream scrapers.
    """
    fake_game = {
        "game_id": "0022500001",
        "home_team": "TeamA", "home_team_id": 1, "home_tricode": "HME",
        "away_team": "TeamB", "away_team_id": 2, "away_tricode": "AWY",
    }

    with patch("main.get_todays_games", return_value=[fake_game]), \
         patch("main.get_conference_standings", return_value={}), \
         patch("main.filter_games_by_stake", return_value=[]) as mock_filter, \
         patch("main.get_projected_lineups") as mock_lineups, \
         patch("main.get_defense_vs_position") as mock_dvp, \
         patch("main.run_analysis") as mock_analysis, \
         patch("main.get_event_ids") as mock_event_ids, \
         patch("main.get_player_lines") as mock_player_lines:

        main.main()

        # Filter was called with the game and the standings
        mock_filter.assert_called_once()

        # No downstream calls must have been made
        assert mock_lineups.call_count == 0, "get_projected_lineups should not be called when no games pass the stake filter"
        assert mock_dvp.call_count == 0, "get_defense_vs_position should not be called when no games pass the stake filter"
        assert mock_analysis.call_count == 0, "run_analysis should not be called when no games pass the stake filter"
        assert mock_event_ids.call_count == 0, "get_event_ids should not be called when no games pass the stake filter"
        assert mock_player_lines.call_count == 0, "get_player_lines should not be called when no games pass the stake filter"


def test_stake_filter_with_games_proceeds_to_downstream():
    """
    When filter_games_by_stake returns a non-empty list,
    main() must proceed and call downstream scrapers.
    """
    fake_game = {
        "game_id": "0022500001",
        "home_team": "TeamA", "home_team_id": 1, "home_tricode": "HME",
        "away_team": "TeamB", "away_team_id": 2, "away_tricode": "AWY",
    }

    with patch("main.get_todays_games", return_value=[fake_game]), \
         patch("main.get_conference_standings", return_value={}), \
         patch("main.filter_games_by_stake", return_value=[fake_game]), \
         patch("main.get_projected_lineups", return_value={}) as mock_lineups, \
         patch("main.get_defense_vs_position", return_value={}) as mock_dvp, \
         patch("main.run_analysis", return_value=[]) as mock_analysis, \
         patch("main.get_event_ids", return_value={}) as mock_event_ids, \
         patch("main.get_player_lines", return_value={}) as mock_player_lines, \
         patch("main.format_results", return_value=""):

        main.main()

        assert mock_lineups.call_count == 1
        assert mock_dvp.call_count == 1
        assert mock_analysis.call_count == 1
        assert mock_event_ids.call_count == 1
        assert mock_player_lines.call_count == 1


def test_imports_work():
    """Verify that the new imports resolve at module load time."""
    from main import main as main_fn
    from scrapers.nba import get_conference_standings
    from analysis.engine import filter_games_by_stake
    assert callable(main_fn)
    assert callable(get_conference_standings)
    assert callable(filter_games_by_stake)
