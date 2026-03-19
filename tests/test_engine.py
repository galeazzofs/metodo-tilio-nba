# tests/test_engine.py
from unittest.mock import patch
from analysis.engine import _score_player, run_analysis, _position_compatible

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

DVP_ELITE = {"PG": {"TeamA": {"rank": 2, "pts": 28.4}}}   # rank ≤ 3  → +3
DVP_GOOD  = {"PG": {"TeamA": {"rank": 5, "pts": 24.1}}}   # rank 4-6  → +2
DVP_POOR  = {"PG": {"TeamA": {"rank": 7, "pts": 20.0}}}   # rank > 6  → discard

RECENT_HOT    = {"pts": 19.0, "min": 28.0, "games": 15}   # ≥ 18 → +3
RECENT_SOLID  = {"pts": 13.0, "min": 24.0, "games": 15}   # ≥ 12 → +2
RECENT_MOD    = {"pts": 8.0,  "min": 20.0, "games": 15}   # ≥ 7  → +1
RECENT_LOW    = {"pts": 5.0,  "min": 18.0, "games": 15}   # < 7  → +0

SEASON_AVG_10 = 10.0   # baseline for above-average checks

ZONES_PAINT = {"Restricted Area": {"attempts": 20, "made": 14, "pct": 70.0, "frequency": 50.0}}
OPP_DEFENSE_PAINT = {"Restricted Area": {"fgm": 18.0, "fga": 28.0, "pct": 0.64}}

# ---------------------------------------------------------------------------
# Gate 0: is_stepping_up
# ---------------------------------------------------------------------------

def test_gate0_not_stepping_up_returns_none():
    score, rating, signals = _score_player(
        position="PG", opponent_name="TeamA", dvp=DVP_ELITE,
        recent_stats=RECENT_HOT, season_avg_pts=SEASON_AVG_10,
        player_zones=ZONES_PAINT, opponent_defense_zones=OPP_DEFENSE_PAINT,
        is_stepping_up=False,
    )
    assert rating is None
    assert score == 0
    assert signals == []


# ---------------------------------------------------------------------------
# Gate 1: DvP
# ---------------------------------------------------------------------------

def test_gate1_poor_dvp_rank_returns_none():
    score, rating, signals = _score_player(
        position="PG", opponent_name="TeamA", dvp=DVP_POOR,
        recent_stats=RECENT_HOT, season_avg_pts=SEASON_AVG_10,
        player_zones=ZONES_PAINT, opponent_defense_zones=OPP_DEFENSE_PAINT,
        is_stepping_up=True,
    )
    assert score == 0
    assert rating is None
    assert signals == []


def test_gate1_elite_dvp_adds_3():
    score, rating, signals = _score_player(
        position="PG", opponent_name="TeamA", dvp=DVP_ELITE,
        recent_stats={}, season_avg_pts=SEASON_AVG_10,
        player_zones=None, opponent_defense_zones=None,
        is_stepping_up=True,
    )
    # DvP +3, no Signal 2 (empty recent_stats), no zone data → no zone discard
    assert score == 3


def test_gate1_good_dvp_adds_2():
    score, rating, signals = _score_player(
        position="PG", opponent_name="TeamA", dvp=DVP_GOOD,
        recent_stats={}, season_avg_pts=SEASON_AVG_10,
        player_zones=None, opponent_defense_zones=None,
        is_stepping_up=True,
    )
    assert score == 2


# ---------------------------------------------------------------------------
# Signal 2: Recent form above-average gate
# ---------------------------------------------------------------------------

def test_signal2_below_season_avg_does_not_score():
    # recent pts (8.0) is below season avg (10.0) → Signal 2 scores 0
    score, rating, signals = _score_player(
        position="PG", opponent_name="TeamA", dvp=DVP_ELITE,
        recent_stats=RECENT_MOD, season_avg_pts=SEASON_AVG_10,
        player_zones=None, opponent_defense_zones=None,
        is_stepping_up=True,
    )
    # DvP +3 only
    assert score == 3
    assert not any("scorer" in s.lower() for s in signals)


def test_signal2_equal_to_season_avg_does_not_score():
    # pts == season_avg_pts: strict greater-than, equal does not qualify
    recent = {"pts": 10.0, "min": 20.0, "games": 15}
    score, rating, signals = _score_player(
        position="PG", opponent_name="TeamA", dvp=DVP_ELITE,
        recent_stats=recent, season_avg_pts=10.0,
        player_zones=None, opponent_defense_zones=None,
        is_stepping_up=True,
    )
    assert score == 3  # DvP only
    assert not any("scorer" in s.lower() for s in signals)


def test_signal2_above_avg_hot_scorer_adds_3():
    # recent pts 19.0 > season avg 10.0 and ≥ 18 → +3
    score, rating, signals = _score_player(
        position="PG", opponent_name="TeamA", dvp=DVP_ELITE,
        recent_stats=RECENT_HOT, season_avg_pts=SEASON_AVG_10,
        player_zones=None, opponent_defense_zones=None,
        is_stepping_up=True,
    )
    assert score == 6
    assert any("Hot scorer" in s for s in signals)


def test_signal2_above_avg_solid_scorer_adds_2():
    score, rating, signals = _score_player(
        position="PG", opponent_name="TeamA", dvp=DVP_ELITE,
        recent_stats=RECENT_SOLID, season_avg_pts=SEASON_AVG_10,
        player_zones=None, opponent_defense_zones=None,
        is_stepping_up=True,
    )
    assert score == 5
    assert any("Solid scorer" in s for s in signals)


def test_signal2_above_avg_moderate_scorer_adds_1():
    # recent pts 8.0 > season avg 5.0 and ≥ 7 → moderate scorer, +1
    score, rating, signals = _score_player(
        position="PG", opponent_name="TeamA", dvp=DVP_ELITE,
        recent_stats=RECENT_MOD, season_avg_pts=5.0,
        player_zones=None, opponent_defense_zones=None,
        is_stepping_up=True,
    )
    assert score == 4
    assert any("Moderate scorer" in s for s in signals)


def test_signal2_above_avg_but_below_7pts_no_message():
    # recent pts 6.0 > season avg 4.0, but < 7 → no points, no message
    recent = {"pts": 6.0, "min": 18.0, "games": 15}
    score, rating, signals = _score_player(
        position="PG", opponent_name="TeamA", dvp=DVP_ELITE,
        recent_stats=recent, season_avg_pts=4.0,
        player_zones=None, opponent_defense_zones=None,
        is_stepping_up=True,
    )
    assert score == 3  # DvP only
    assert not any("scorer" in s.lower() for s in signals)


def test_signal2_empty_recent_stats_skips_block():
    score, _, _ = _score_player(
        position="PG", opponent_name="TeamA", dvp=DVP_ELITE,
        recent_stats={}, season_avg_pts=SEASON_AVG_10,
        player_zones=None, opponent_defense_zones=None,
        is_stepping_up=True,
    )
    assert score == 3  # DvP only, no crash


# ---------------------------------------------------------------------------
# Signal 3: Zone match
# ---------------------------------------------------------------------------

def test_signal3_zone_mismatch_discards_player():
    # Player scores in paint, opponent concedes from 3-point zone → mismatch → discard
    zones_paint = {"Restricted Area": {"attempts": 20, "made": 14, "pct": 70.0, "frequency": 50.0}}
    opp_defense_three = {"Above the Break 3": {"fgm": 18.0, "fga": 28.0, "pct": 0.64}}
    score, rating, signals = _score_player(
        position="PG", opponent_name="TeamA", dvp=DVP_ELITE,
        recent_stats=RECENT_HOT, season_avg_pts=SEASON_AVG_10,
        player_zones=zones_paint, opponent_defense_zones=opp_defense_three,
        is_stepping_up=True,
    )
    assert score == 0
    assert rating is None
    assert signals == []


# ---------------------------------------------------------------------------
# Rating thresholds
# ---------------------------------------------------------------------------

def test_rating_best_of_night_at_7():
    # DvP +3, form +3, zone +1 = 7
    score, rating, _ = _score_player(
        position="PG", opponent_name="TeamA", dvp=DVP_ELITE,
        recent_stats=RECENT_HOT, season_avg_pts=SEASON_AVG_10,
        player_zones=ZONES_PAINT, opponent_defense_zones=OPP_DEFENSE_PAINT,
        is_stepping_up=True,
    )
    assert score == 7
    assert rating == "BEST OF THE NIGHT"


def test_rating_very_favorable_at_5():
    # DvP +2, form +3, zone +0 (no zone data) = 5
    score, rating, _ = _score_player(
        position="PG", opponent_name="TeamA", dvp=DVP_GOOD,
        recent_stats=RECENT_HOT, season_avg_pts=SEASON_AVG_10,
        player_zones=None, opponent_defense_zones=None,
        is_stepping_up=True,
    )
    assert score == 5
    assert rating == "VERY FAVORABLE"


def test_rating_none_below_5():
    # DvP +2, form +2 (solid but not hot), no zone = 4 → None
    score, rating, _ = _score_player(
        position="PG", opponent_name="TeamA", dvp=DVP_GOOD,
        recent_stats=RECENT_SOLID, season_avg_pts=SEASON_AVG_10,
        player_zones=None, opponent_defense_zones=None,
        is_stepping_up=True,
    )
    assert score == 4
    assert rating is None


def test_no_favorable_tier():
    # Score of 4 must not return FAVORABLE
    _, rating, _ = _score_player(
        position="PG", opponent_name="TeamA", dvp=DVP_GOOD,
        recent_stats=RECENT_SOLID, season_avg_pts=SEASON_AVG_10,
        player_zones=None, opponent_defense_zones=None,
        is_stepping_up=True,
    )
    assert rating != "FAVORABLE"


# ---------------------------------------------------------------------------
# run_analysis wiring smoke test
# ---------------------------------------------------------------------------

def test_run_analysis_wiring_no_type_error():
    """
    Verifies that run_analysis correctly wires season_avg_pts into _score_player.
    All scrapers are patched — this test only checks the call is wired correctly,
    not that real data is returned.
    """
    games = [{
        "game_id": "001",
        "home_team": "TeamA", "home_team_id": 1, "home_tricode": "HME",
        "away_team": "TeamB", "away_team_id": 2, "away_tricode": "AWY",
    }]
    lineups = {
        "HME": {
            "team_name": "TeamA",
            "starters": [{"name": "John Doe", "position": "PG"}],
            "out": ["Injured Player"],
        },
        "AWY": {"team_name": "TeamB", "starters": [], "out": []},
    }
    dvp = {}

    with patch("analysis.engine.get_all_teams_defense_zones", return_value={}), \
         patch("analysis.engine.get_player_season_stats", return_value={
             9999: {"min": 20.0, "pts": 10.0}
         }), \
         patch("analysis.engine._find_player_id", return_value=9999), \
         patch("analysis.engine.get_player_recent_stats", return_value={"pts": 15.0, "min": 22.0, "games": 15}), \
         patch("analysis.engine.get_player_shot_zones", return_value={}):
        result = run_analysis(games, lineups, dvp)

    # No TypeError = wiring is correct. Result may be empty (dvp={} means no DvP match).
    assert isinstance(result, list)


# ---------------------------------------------------------------------------
# _position_compatible
# ---------------------------------------------------------------------------

OUT_PG = {"name": "Star PG", "position": "PG"}
OUT_C  = {"name": "Star C",  "position": "C"}
OUT_SF = {"name": "Star SF", "position": "SF"}
OUT_G  = {"name": "Star G",  "position": "G"}   # composite label from RotoWire
OUT_F  = {"name": "Star F",  "position": "F"}   # composite label from RotoWire

def test_position_compat_pg_candidate_matches_pg_out():
    result = _position_compatible("PG", [OUT_PG])
    assert result == [OUT_PG]

def test_position_compat_pg_candidate_matches_g_out():
    # G (composite guard) out — PG candidate qualifies
    result = _position_compatible("PG", [OUT_G])
    assert result == [OUT_G]

def test_position_compat_pg_candidate_no_match_for_c_out():
    result = _position_compatible("PG", [OUT_C])
    assert result == []

def test_position_compat_c_candidate_matches_pf_out():
    out_pf = {"name": "Star PF", "position": "PF"}
    result = _position_compatible("C", [out_pf])
    assert result == [out_pf]

def test_position_compat_c_candidate_no_match_for_sf_out():
    result = _position_compatible("C", [OUT_SF])
    assert result == []

def test_position_compat_f_candidate_no_match_for_c_out():
    # F (wing/stretch-four) does NOT cover a C out — intentional asymmetry
    result = _position_compatible("F", [OUT_C])
    assert result == []

def test_position_compat_pf_candidate_matches_c_out():
    # PF covers a C out (true bigs overlap)
    result = _position_compatible("PF", [OUT_C])
    assert result == [OUT_C]

def test_position_compat_multiple_out_returns_only_matches():
    # PG out and C out — SG candidate matches PG but not C
    out_c  = {"name": "Star C",  "position": "C"}
    out_pg = {"name": "Star PG", "position": "PG"}
    result = _position_compatible("SG", [out_c, out_pg])
    assert result == [out_pg]

def test_position_compat_unknown_candidate_position_returns_empty():
    result = _position_compatible("UNKNOWN", [OUT_PG])
    assert result == []

def test_position_compat_missing_position_key_returns_empty():
    # out player dict with no "position" key — must not raise
    out_no_pos = {"name": "Mystery Player"}
    result = _position_compatible("PG", [out_no_pos])
    assert result == []

def test_position_compat_composite_f_out_matches_sf_candidate():
    # "F" as an out-starter label — SF candidate should qualify
    result = _position_compatible("SF", [OUT_F])
    assert result == [OUT_F]

def test_position_compat_composite_f_out_no_match_for_c_candidate():
    result = _position_compatible("C", [OUT_F])
    assert result == []

def test_position_compat_g_candidate_matches_sg_out():
    # G (composite guard candidate) covers SG out
    out_sg = {"name": "Star SG", "position": "SG"}
    result = _position_compatible("G", [out_sg])
    assert result == [out_sg]
