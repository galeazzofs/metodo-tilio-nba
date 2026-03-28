# tests/test_odds.py
import requests
from unittest.mock import patch, MagicMock
from scrapers.odds import get_game_moneylines

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

GAMES = [
    {"away_tricode": "BOS", "home_tricode": "LAL"},
    {"away_tricode": "MIA", "home_tricode": "NYK"},
]

ODDS_API_RESPONSE = [
    {
        "away_team": "Boston Celtics",
        "home_team": "Los Angeles Lakers",
        "bookmakers": [
            {
                "key": "fanduel",
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "Boston Celtics", "price": 1.08},
                            {"name": "Los Angeles Lakers", "price": 9.50},
                        ],
                    }
                ],
            },
            {
                "key": "draftkings",
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "Boston Celtics", "price": 1.10},
                            {"name": "Los Angeles Lakers", "price": 8.00},
                        ],
                    }
                ],
            },
        ],
    },
    {
        "away_team": "Miami Heat",
        "home_team": "New York Knicks",
        "bookmakers": [
            {
                "key": "fanduel",
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "Miami Heat", "price": 2.10},
                            {"name": "New York Knicks", "price": 1.75},
                        ],
                    }
                ],
            },
        ],
    },
]


def _mock_response(json_data, status_code=200):
    mock = MagicMock()
    mock.json.return_value = json_data
    mock.status_code = status_code
    mock.headers = {"x-requests-remaining": "450"}
    mock.raise_for_status = MagicMock()
    return mock


@patch("scrapers.odds._get_api_key", return_value="test-key")
@patch("scrapers.odds.requests.get")
def test_get_game_moneylines_returns_lowest_odds(mock_get, mock_key):
    mock_get.return_value = _mock_response(ODDS_API_RESPONSE)
    result = get_game_moneylines(GAMES)
    assert result[("BOS", "LAL")] == 1.08
    assert result[("MIA", "NYK")] == 1.75


@patch("scrapers.odds._get_api_key", return_value=None)
def test_get_game_moneylines_no_api_key(mock_key):
    result = get_game_moneylines(GAMES)
    assert result == {}


@patch("scrapers.odds._get_api_key", return_value="test-key")
@patch("scrapers.odds.requests.get", side_effect=requests.exceptions.ConnectionError("Network error"))
def test_get_game_moneylines_request_failure(mock_get, mock_key):
    result = get_game_moneylines(GAMES)
    assert result == {}


@patch("scrapers.odds._get_api_key", return_value="test-key")
@patch("scrapers.odds.requests.get")
def test_get_game_moneylines_filters_to_wanted_games(mock_get, mock_key):
    mock_get.return_value = _mock_response(ODDS_API_RESPONSE)
    single_game = [{"away_tricode": "BOS", "home_tricode": "LAL"}]
    result = get_game_moneylines(single_game)
    assert ("BOS", "LAL") in result
    assert ("MIA", "NYK") not in result


@patch("scrapers.odds._get_api_key", return_value="test-key")
@patch("scrapers.odds.requests.get")
def test_get_game_moneylines_calls_correct_endpoint(mock_get, mock_key):
    mock_get.return_value = _mock_response([])
    get_game_moneylines(GAMES)
    call_args = mock_get.call_args
    assert "basketball_nba/odds" in call_args[0][0]
    assert call_args[1]["params"]["regions"] == "us"
    assert call_args[1]["params"]["markets"] == "h2h"
    assert call_args[1]["params"]["oddsFormat"] == "decimal"
