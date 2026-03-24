from unittest.mock import patch, MagicMock
from scrapers.nba import get_team_pace

def test_get_team_pace_returns_dict_with_pace_and_median():
    fake_rows = [
        [1610612737, "Atlanta Hawks", 100.5],
        [1610612738, "Boston Celtics", 98.2],
        [1610612739, "Cleveland Cavaliers", 97.0],
    ]
    fake_headers = ["TEAM_ID", "TEAM_NAME", "PACE"]
    mock_result = MagicMock()
    mock_result.get_dict.return_value = {
        "resultSets": [{"headers": fake_headers, "rowSet": fake_rows}]
    }
    with patch("scrapers.nba.leaguedashteamstats.LeagueDashTeamStats", return_value=mock_result):
        pace_map, median_pace = get_team_pace()
    assert pace_map[1610612737] == 100.5
    assert pace_map[1610612738] == 98.2
    assert pace_map[1610612739] == 97.0
    assert median_pace == 98.2
