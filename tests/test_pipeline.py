from unittest.mock import patch


@patch("analysis.pipeline.get_player_lines", return_value={})
@patch("analysis.pipeline.get_event_ids", return_value={})
@patch("analysis.pipeline.run_analysis", return_value={"pts": [], "ast": [], "reb": [], "three_pt": []})
@patch("analysis.pipeline.get_team_pace", return_value=({}, 99.0))
@patch("analysis.pipeline.get_team_defense_tracking", return_value=None)
@patch("analysis.pipeline.get_team_defense_vs_position", return_value={})
@patch("analysis.pipeline.get_defense_vs_position", return_value={})
@patch("analysis.pipeline.get_projected_lineups", return_value={})
@patch("analysis.pipeline.filter_games_by_blowout", side_effect=lambda g, m: g)
@patch("analysis.pipeline.filter_games_by_stake", side_effect=lambda g, s: g)
@patch("analysis.pipeline.get_conference_standings", return_value={})
@patch("analysis.pipeline.get_game_moneylines", return_value={})
@patch("analysis.pipeline.get_todays_games", return_value=[{"game_id": "1"}])
def test_pipeline_orchestrates_all_steps(
    mock_games, mock_moneylines, mock_standings, mock_stake,
    mock_blowout, mock_lineups, mock_dvp, mock_team_def,
    mock_tracking, mock_pace, mock_analysis, mock_events, mock_lines
):
    """Bottom-up: first @patch arg = bottom decorator (get_todays_games)."""
    from analysis.pipeline import run_pipeline
    stats, games = run_pipeline()
    assert stats is not None
    assert isinstance(stats, dict)
    mock_moneylines.assert_called_once()
    mock_blowout.assert_called_once()
    mock_analysis.assert_called_once()


@patch("analysis.pipeline.get_todays_games", return_value=[])
def test_pipeline_no_games_returns_none(mock_games):
    from analysis.pipeline import run_pipeline
    stats, games = run_pipeline()
    assert stats is None


@patch("analysis.pipeline.get_game_moneylines", return_value={})
@patch("analysis.pipeline.get_conference_standings", return_value={})
@patch("analysis.pipeline.filter_games_by_stake", side_effect=lambda g, s: g)
@patch("analysis.pipeline.filter_games_by_blowout", return_value=[])
@patch("analysis.pipeline.get_todays_games", return_value=[{"game_id": "1"}])
def test_pipeline_returns_none_when_all_blowout(
    mock_games, mock_blowout, mock_stake, mock_standings, mock_moneylines
):
    from analysis.pipeline import run_pipeline
    stats, games = run_pipeline()
    assert stats is None
