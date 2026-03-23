from unittest.mock import patch


@patch("analysis.pipeline.get_player_lines", return_value={})
@patch("analysis.pipeline.get_event_ids", return_value={})
@patch("analysis.pipeline.run_analysis", return_value={"pts": [], "ast": [], "reb": [], "three_pt": []})
@patch("analysis.pipeline.get_team_defense_tracking", return_value=None)
@patch("analysis.pipeline.get_team_defense_vs_position", return_value={})
@patch("analysis.pipeline.get_defense_vs_position", return_value={})
@patch("analysis.pipeline.get_projected_lineups", return_value={})
@patch("analysis.pipeline.get_todays_games", return_value=[{"game_id": "1"}])
def test_pipeline_orchestrates_all_steps(m8, m7, m6, m5, m4, m3, m2, m1):
    from analysis.pipeline import run_pipeline
    stats, games = run_pipeline()
    assert stats is not None
    assert isinstance(stats, dict)
    m8.assert_called_once()  # get_todays_games
    m3.assert_called_once()  # run_analysis


@patch("analysis.pipeline.get_todays_games", return_value=[])
def test_pipeline_no_games_returns_none(mock_games):
    from analysis.pipeline import run_pipeline
    stats, games = run_pipeline()
    assert stats is None
