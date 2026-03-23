"""Tests for scrapers/telegram.py — 4-section format."""
from unittest.mock import patch, MagicMock
from scrapers.telegram import (
    _format_message,
    _format_section,
    _format_player,
    send_analysis,
    STAT_SECTIONS,
)


# --------------- helpers ---------------

def _make_candidate(**overrides):
    """Return a new-format candidate dict with sensible defaults."""
    base = {
        "player_name": "LeBron James",
        "position": "SF",
        "team": "LAL",
        "game": "LAL vs GSW",
        "rating": "FAVORABLE",
        "line": {"value": 25.5},
        "context": {
            "signal_descriptions": ["Averages 28.3 pts last 10", "Home game boost"],
        },
    }
    base.update(overrides)
    return base


def _make_old_candidate():
    """Return an old-format candidate (plain signals list, line as number)."""
    return {
        "player": "Stephen Curry",
        "position": "PG",
        "team": "GSW",
        "game": "GSW vs LAL",
        "rating": "VERY FAVORABLE",
        "line": 30,
        "signals": ["Hot shooting streak", "Opponent weak perimeter D"],
    }


# --------------- _format_message tests ---------------

class TestFormatMessage:
    def test_section_title_shown_for_nonempty_stat(self):
        stats = {
            "pts": [_make_candidate()],
            "ast": [],
            "reb": [],
            "three_pt": [],
        }
        msg = _format_message(stats, "2026-03-23", 5)
        assert "PONTOS (PTS)" in msg

    def test_empty_sections_omitted(self):
        stats = {
            "pts": [_make_candidate()],
            "ast": [],
            "reb": [],
            "three_pt": [],
        }
        msg = _format_message(stats, "2026-03-23", 5)
        assert "ASSIST" not in msg
        assert "REBOTES" not in msg
        assert "CESTAS DE 3" not in msg

    def test_all_sections_empty_shows_fallback(self):
        stats = {"pts": [], "ast": [], "reb": [], "three_pt": []}
        msg = _format_message(stats, "2026-03-23", 3)
        assert "Nenhuma jogada favoravel" in msg

    def test_multiple_sections_shown(self):
        stats = {
            "pts": [_make_candidate()],
            "ast": [_make_candidate(player_name="Trae Young")],
            "reb": [],
            "three_pt": [],
        }
        msg = _format_message(stats, "2026-03-23", 8)
        assert "PONTOS (PTS)" in msg
        assert "ASSIST" in msg
        assert "LeBron James" in msg
        assert "Trae Young" in msg

    def test_header_format(self):
        stats = {"pts": [_make_candidate()], "ast": [], "reb": [], "three_pt": []}
        msg = _format_message(stats, "2026-03-23", 7)
        assert "SCOUT" in msg
        assert "23/03/2026" in msg
        assert "7 jogos" in msg


# --------------- old-format backward compat ---------------

class TestOldFormatCompat:
    def test_old_candidate_line_as_number(self):
        stats = {"pts": [_make_old_candidate()], "ast": [], "reb": [], "three_pt": []}
        msg = _format_message(stats, "2026-03-23", 4)
        assert "30" in msg
        assert "Stephen Curry" in msg

    def test_old_candidate_signals_shown(self):
        stats = {"pts": [_make_old_candidate()], "ast": [], "reb": [], "three_pt": []}
        msg = _format_message(stats, "2026-03-23", 4)
        assert "Hot shooting streak" in msg
        assert "Opponent weak perimeter D" in msg


# --------------- _format_player ---------------

class TestFormatPlayer:
    def test_new_format_line_dict(self):
        c = _make_candidate()
        text = _format_player(1, c)
        assert "25.5" in text

    def test_old_format_line_number(self):
        c = _make_old_candidate()
        text = _format_player(1, c)
        assert "30" in text

    def test_signals_limited_to_two(self):
        c = _make_candidate()
        c["context"]["signal_descriptions"] = ["sig1", "sig2", "sig3"]
        text = _format_player(1, c)
        assert "sig1" in text
        assert "sig2" in text
        assert "sig3" not in text


# --------------- send_analysis + splitting ---------------

class TestSendAnalysis:
    @patch("scrapers.telegram._get_config", return_value=("tok", "123"))
    @patch("scrapers.telegram._send_message")
    def test_short_message_single_send(self, mock_send, mock_cfg):
        stats = {"pts": [_make_candidate()], "ast": [], "reb": [], "three_pt": []}
        result = send_analysis(stats, "2026-03-23", 5)
        assert result is True
        assert mock_send.call_count == 1

    @patch("scrapers.telegram._get_config", return_value=("tok", "123"))
    @patch("scrapers.telegram._send_message")
    @patch("scrapers.telegram._format_message")
    def test_long_message_splits(self, mock_fmt, mock_send, mock_cfg):
        # Simulate a message that exceeds 4000 chars
        mock_fmt.return_value = "x" * 4500
        stats = {
            "pts": [_make_candidate()],
            "ast": [_make_candidate()],
            "reb": [],
            "three_pt": [],
        }
        result = send_analysis(stats, "2026-03-23", 5)
        assert result is True
        # header + 2 non-empty sections = 3 calls
        assert mock_send.call_count == 3

    @patch("scrapers.telegram._get_config", side_effect=RuntimeError("no config"))
    def test_missing_config_returns_false(self, mock_cfg):
        stats = {"pts": [], "ast": [], "reb": [], "three_pt": []}
        assert send_analysis(stats, "2026-03-23", 0) is False
