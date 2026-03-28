# tests/test_engine.py
from unittest.mock import patch
import io
import sys
from analysis.engine import (
    _score_player, run_analysis, _position_compatible, _team_has_stake,
    filter_games_by_stake, _ordinal, _score_player_ast, _score_player_reb,
    _score_player_3pt, _dedup_candidates,
    filter_games_by_blowout, BLOWOUT_ODD_THRESHOLD,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

DVP_ELITE = {"PG": {"TeamA": {"rank": 2, "pts": 28.4}}}   # rank ≤ 6  → +3
DVP_GOOD  = {"PG": {"TeamA": {"rank": 5, "pts": 24.1}}}   # rank ≤ 6  → +3
DVP_POOR  = {"PG": {"TeamA": {"rank": 7, "pts": 20.0}}}   # rank > 6  → discard

RECENT_HOT    = {"pts": 19.0, "min": 28.0, "games": 15, "season_avg_pts": 10.0}
RECENT_SOLID  = {"pts": 13.0, "min": 24.0, "games": 15, "season_avg_pts": 10.0}
RECENT_MOD    = {"pts": 8.0,  "min": 20.0, "games": 15, "season_avg_pts": 10.0}
RECENT_LOW    = {"pts": 5.0,  "min": 18.0, "games": 15, "season_avg_pts": 10.0}

ZONES_PAINT = {"Restricted Area": {"attempts": 20, "made": 14, "pct": 70.0, "frequency": 50.0}}
OPP_DEFENSE_PAINT = {"Restricted Area": {"fgm": 18.0, "fga": 28.0, "pct": 0.64}}

# ---------------------------------------------------------------------------
# Blowout filter fixtures
# ---------------------------------------------------------------------------

GAME_BOS_LAL = {
    "home_tricode": "LAL", "away_tricode": "BOS",
    "home_team_id": 1, "away_team_id": 2,
}
GAME_MIA_NYK = {
    "home_tricode": "NYK", "away_tricode": "MIA",
    "home_team_id": 3, "away_team_id": 4,
}
GAME_GSW_SAC = {
    "home_tricode": "SAC", "away_tricode": "GSW",
    "home_team_id": 5, "away_team_id": 6,
}

# ---------------------------------------------------------------------------
# Gate 0: is_stepping_up
# ---------------------------------------------------------------------------

def test_gate0_not_stepping_up_returns_none():
    score, rating, signals = _score_player(
        position="PG", opponent_name="TeamA", dvp=DVP_ELITE,
        recent_stats=RECENT_HOT,
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
        recent_stats=RECENT_HOT,
        player_zones=ZONES_PAINT, opponent_defense_zones=OPP_DEFENSE_PAINT,
        is_stepping_up=True,
    )
    assert score == 0
    assert rating is None
    assert signals == []


def test_gate1_elite_dvp_adds_3():
    score, rating, signals = _score_player(
        position="PG", opponent_name="TeamA", dvp=DVP_ELITE,
        recent_stats={},
        player_zones=None, opponent_defense_zones=None,
        is_stepping_up=True,
    )
    # DvP +3, no Signal 2 (empty recent_stats), no zone data → no zone discard
    assert score == 3


def test_gate1_good_dvp_adds_3():
    # rank 5 <= 6 → binary +3 (same as elite)
    score, rating, signals = _score_player(
        position="PG", opponent_name="TeamA", dvp=DVP_GOOD,
        recent_stats={},
        player_zones=None, opponent_defense_zones=None,
        is_stepping_up=True,
    )
    assert score == 3


# ---------------------------------------------------------------------------
# Signal 2: Recent form above-average gate
# ---------------------------------------------------------------------------

def test_signal2_below_season_avg_does_not_score():
    # recent pts (8.0) is below season avg (10.0) → Signal 2 scores 0
    score, rating, signals = _score_player(
        position="PG", opponent_name="TeamA", dvp=DVP_ELITE,
        recent_stats=RECENT_MOD,
        player_zones=None, opponent_defense_zones=None,
        is_stepping_up=True,
    )
    # DvP +3 only
    assert score == 3
    assert not any("scorer" in s.lower() for s in signals)


def test_signal2_equal_to_season_avg_does_score():
    # pts == season_avg_pts: >= means equal qualifies for +1
    recent = {"pts": 10.0, "min": 20.0, "games": 15, "season_avg_pts": 10.0}
    score, rating, signals = _score_player(
        position="PG", opponent_name="TeamA", dvp=DVP_ELITE,
        recent_stats=recent,
        player_zones=None, opponent_defense_zones=None,
        is_stepping_up=True,
    )
    assert score == 4  # DvP +3, form +1


def test_signal2_above_avg_form_adds_1():
    # recent pts 19.0 >= season avg 10.0 → +1 (binary, not tiered)
    score, rating, signals = _score_player(
        position="PG", opponent_name="TeamA", dvp=DVP_ELITE,
        recent_stats=RECENT_HOT,
        player_zones=None, opponent_defense_zones=None,
        is_stepping_up=True,
    )
    assert score == 4  # DvP +3, form +1
    assert any("Forma recente" in s for s in signals)


def test_signal2_above_avg_solid_form_adds_1():
    # recent pts 13.0 >= season avg 10.0 → +1
    score, rating, signals = _score_player(
        position="PG", opponent_name="TeamA", dvp=DVP_ELITE,
        recent_stats=RECENT_SOLID,
        player_zones=None, opponent_defense_zones=None,
        is_stepping_up=True,
    )
    assert score == 4  # DvP +3, form +1
    assert any("Forma recente" in s for s in signals)


def test_signal2_above_avg_moderate_form_adds_1():
    # recent pts 8.0 >= season avg 5.0 → +1
    score, rating, signals = _score_player(
        position="PG", opponent_name="TeamA", dvp=DVP_ELITE,
        recent_stats={**RECENT_MOD, "season_avg_pts": 5.0},
        player_zones=None, opponent_defense_zones=None,
        is_stepping_up=True,
    )
    assert score == 4  # DvP +3, form +1
    assert any("Forma recente" in s for s in signals)


def test_signal2_above_avg_low_pts_still_scores():
    # recent pts 6.0 >= season avg 4.0 → +1 (no minimum pts threshold)
    recent = {"pts": 6.0, "min": 18.0, "games": 15, "season_avg_pts": 4.0}
    score, rating, signals = _score_player(
        position="PG", opponent_name="TeamA", dvp=DVP_ELITE,
        recent_stats=recent,
        player_zones=None, opponent_defense_zones=None,
        is_stepping_up=True,
    )
    assert score == 4  # DvP +3, form +1
    assert any("Forma recente" in s for s in signals)


def test_signal2_empty_recent_stats_skips_block():
    score, _, _ = _score_player(
        position="PG", opponent_name="TeamA", dvp=DVP_ELITE,
        recent_stats={},
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
        recent_stats=RECENT_HOT,
        player_zones=zones_paint, opponent_defense_zones=opp_defense_three,
        is_stepping_up=True,
    )
    assert score == 0
    assert rating is None
    assert signals == []


# ---------------------------------------------------------------------------
# Rating thresholds
# ---------------------------------------------------------------------------

def test_rating_best_of_night_at_6():
    # DvP +3, form +1, zone +2 = 6 (maximum possible score)
    score, rating, _ = _score_player(
        position="PG", opponent_name="TeamA", dvp=DVP_ELITE,
        recent_stats=RECENT_HOT,
        player_zones=ZONES_PAINT, opponent_defense_zones=OPP_DEFENSE_PAINT,
        is_stepping_up=True,
    )
    assert score == 6
    assert rating == "BEST OF THE NIGHT"


def test_rating_very_favorable_at_4():
    # DvP +3 (rank 5 <= 6), form +1, no zone data = 4
    score, rating, _ = _score_player(
        position="PG", opponent_name="TeamA", dvp=DVP_GOOD,
        recent_stats=RECENT_HOT,
        player_zones=None, opponent_defense_zones=None,
        is_stepping_up=True,
    )
    assert score == 4
    assert rating == "VERY FAVORABLE"


def test_rating_none_below_4():
    # DvP +3, form below avg (no +1), no zone = 3 → rating None
    score, rating, _ = _score_player(
        position="PG", opponent_name="TeamA", dvp=DVP_GOOD,
        recent_stats=RECENT_LOW,
        player_zones=None, opponent_defense_zones=None,
        is_stepping_up=True,
    )
    assert score == 3
    assert rating is None


def test_no_favorable_tier():
    # Score of 4 must not return FAVORABLE
    _, rating, _ = _score_player(
        position="PG", opponent_name="TeamA", dvp=DVP_GOOD,
        recent_stats=RECENT_SOLID,
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
            "out": [{"name": "Injured Player", "position": "PG"}],
        },
        "AWY": {"team_name": "TeamB", "starters": [], "out": []},
    }
    dvp = {}

    with patch("analysis.engine.get_all_teams_defense_zones", return_value={}), \
         patch("analysis.engine.get_player_season_data", return_value=(
             {9999: 20.0}, {9999}
         )), \
         patch("analysis.engine._find_player_id", return_value=9999), \
         patch("analysis.engine.get_player_recent_stats", return_value={"pts": 15.0, "min": 22.0, "games": 15}), \
         patch("analysis.engine.get_player_shot_zones", return_value={}):
        result = run_analysis(games, lineups, dvp, {}, None)

    # No TypeError = wiring is correct. Result may be empty (dvp={} means no DvP match).
    assert isinstance(result, dict)
    assert set(result.keys()) == {"pts", "ast", "reb", "three_pt"}


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


# ---------------------------------------------------------------------------
# _team_has_stake
# ---------------------------------------------------------------------------

def _standing(seed, gb_above, gb_below, remaining):
    return {
        "seed": seed,
        "games_back_from_above": gb_above,
        "games_ahead_of_below": gb_below,
        "games_remaining": remaining,
    }


def test_has_stake_can_improve():
    """Team can reach the seed above within remaining games."""
    data = _standing(seed=8, gb_above=3.0, gb_below=10.0, remaining=10)
    has_stake, tag = _team_has_stake(data)
    assert has_stake is True
    assert tag == "can improve"


def test_has_stake_can_be_caught():
    """Team cannot improve but can be caught from below."""
    data = _standing(seed=3, gb_above=15.0, gb_below=2.0, remaining=10)
    has_stake, tag = _team_has_stake(data)
    assert has_stake is True
    assert tag == "can be caught"


def test_has_stake_both_conditions_true_returns_can_improve():
    """When both conditions are true, tag is 'can improve'."""
    data = _standing(seed=5, gb_above=4.0, gb_below=3.0, remaining=10)
    has_stake, tag = _team_has_stake(data)
    assert has_stake is True
    assert tag == "can improve"


def test_has_stake_eliminated():
    """Both conditions false — team is eliminated."""
    data = _standing(seed=13, gb_above=12.0, gb_below=7.0, remaining=6)
    has_stake, tag = _team_has_stake(data)
    assert has_stake is False
    assert tag == "eliminated"


def test_has_stake_seed1_no_above():
    """Seed 1 has games_back_from_above=None — can_improve is always False."""
    data = _standing(seed=1, gb_above=None, gb_below=3.0, remaining=8)
    has_stake, tag = _team_has_stake(data)
    assert has_stake is True   # can be caught
    assert tag == "can be caught"


def test_has_stake_seed15_no_below():
    """Seed 15 has games_ahead_of_below=None — can_be_caught is always False."""
    data = _standing(seed=15, gb_above=4.0, gb_below=None, remaining=8)
    has_stake, tag = _team_has_stake(data)
    assert has_stake is True   # can still improve
    assert tag == "can improve"


def test_has_stake_exact_boundary_games_back_equals_remaining():
    """games_back_from_above == games_remaining — can_improve is True (<=, not <)."""
    data = _standing(seed=10, gb_above=5.0, gb_below=20.0, remaining=5)
    has_stake, tag = _team_has_stake(data)
    assert has_stake is True
    assert tag == "can improve"


def test_has_stake_one_game_over_remaining():
    """games_back_from_above > games_remaining — can_improve is False."""
    data = _standing(seed=10, gb_above=6.0, gb_below=20.0, remaining=5)
    has_stake, tag = _team_has_stake(data)
    assert has_stake is False
    assert tag == "eliminated"


def test_ordinal_correctness():
    assert _ordinal(1)  == "1st"
    assert _ordinal(2)  == "2nd"
    assert _ordinal(3)  == "3rd"
    assert _ordinal(4)  == "4th"
    assert _ordinal(11) == "11th"
    assert _ordinal(12) == "12th"
    assert _ordinal(13) == "13th"
    assert _ordinal(21) == "21st"
    assert _ordinal(22) == "22nd"
    assert _ordinal(23) == "23rd"


# ---------------------------------------------------------------------------
# filter_games_by_stake
# ---------------------------------------------------------------------------

def _make_game(home_id=1, away_id=2, home_tri="HME", away_tri="AWY"):
    return {
        "home_team_id": home_id, "away_team_id": away_id,
        "home_tricode": home_tri, "away_tricode": away_tri,
    }


def _make_standing(team_id, seed, conf, gb_above, gb_below, remaining=10):
    return {
        "team_id": team_id, "seed": seed, "conference": conf,
        "games_back_from_above": gb_above,
        "games_ahead_of_below": gb_below,
        "games_remaining": remaining,
    }


def test_filter_includes_game_when_home_team_has_stake():
    games = [_make_game()]
    standings = {
        1: _make_standing(1, seed=8, conf="East", gb_above=3.0, gb_below=10.0),
        2: _make_standing(2, seed=13, conf="East", gb_above=12.0, gb_below=5.0),
    }
    result = filter_games_by_stake(games, standings)
    assert result == games


def test_filter_includes_game_when_away_team_has_stake():
    games = [_make_game()]
    standings = {
        1: _make_standing(1, seed=14, conf="East", gb_above=15.0, gb_below=3.0),
        2: _make_standing(2, seed=9, conf="East", gb_above=2.0, gb_below=8.0),
    }
    result = filter_games_by_stake(games, standings)
    assert result == games


def test_filter_excludes_game_when_both_eliminated():
    # Both teams eliminated: gb_above > remaining AND gb_below > remaining for each
    games = [_make_game()]
    standings = {
        1: _make_standing(1, seed=13, conf="East", gb_above=12.0, gb_below=8.0, remaining=5),
        2: _make_standing(2, seed=14, conf="West", gb_above=15.0, gb_below=9.0, remaining=5),
    }
    result = filter_games_by_stake(games, standings)
    assert result == []


def test_filter_includes_game_when_both_have_stake():
    games = [_make_game()]
    standings = {
        1: _make_standing(1, seed=3, conf="East", gb_above=2.0, gb_below=1.5),
        2: _make_standing(2, seed=8, conf="East", gb_above=3.0, gb_below=2.0),
    }
    result = filter_games_by_stake(games, standings)
    assert result == games


def test_filter_pass_through_when_team_missing_from_standings(capsys):
    games = [_make_game(home_id=999)]   # 999 not in standings
    standings = {
        2: _make_standing(2, seed=8, conf="East", gb_above=3.0, gb_below=2.0),
    }
    result = filter_games_by_stake(games, standings)
    assert result == games   # pass-through
    captured = capsys.readouterr()
    assert "WARNING" in captured.out
    assert "999" in captured.out


def test_filter_multiple_games_mixed_results():
    game_with_stake = _make_game(home_id=1, away_id=2, home_tri="BOS", away_tri="CLE")
    game_no_stake   = _make_game(home_id=3, away_id=4, home_tri="MEM", away_tri="SAS")
    standings = {
        1: _make_standing(1, seed=1, conf="East", gb_above=None, gb_below=4.0),
        2: _make_standing(2, seed=2, conf="East", gb_above=4.0,  gb_below=3.0),
        3: _make_standing(3, seed=12, conf="West", gb_above=10.0, gb_below=6.0, remaining=5),
        4: _make_standing(4, seed=14, conf="West", gb_above=12.0, gb_below=7.0, remaining=5),
    }
    result = filter_games_by_stake([game_with_stake, game_no_stake], standings)
    assert result == [game_with_stake]
    assert game_no_stake not in result


def test_filter_skipped_logs_correct_format():
    """Both teams eliminated: log output must contain the expected format strings."""
    # seed 14E, gb_above=15 > remaining=5 → can't improve; gb_below=None → can't be caught
    # seed 13W, gb_above=12 > remaining=5 → can't improve; gb_below=9 > remaining=5 → can't be caught
    game = _make_game(home_id=1, away_id=2, home_tri="HME", away_tri="AWY")
    standings = {
        1: _make_standing(1, seed=14, conf="East", gb_above=15.0, gb_below=None, remaining=5),
        2: _make_standing(2, seed=13, conf="West", gb_above=12.0, gb_below=9.0,  remaining=5),
    }

    buf = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = buf
    try:
        result = filter_games_by_stake([game], standings)
    finally:
        sys.stdout = old_stdout

    output = buf.getvalue()

    assert result == []
    assert "skipped: neither team has a stake" in output
    assert "seed 14E" in output
    assert "GB from" in output
    assert "(above)" in output
    assert "n/a below" in output
    assert "\u2192 eliminated" in output


# ---------------------------------------------------------------------------
# run_analysis — position gate wiring
# ---------------------------------------------------------------------------

def _make_games():
    return [{
        "game_id": "001",
        "home_team": "TeamA", "home_team_id": 1, "home_tricode": "HME",
        "away_team": "TeamB", "away_team_id": 2, "away_tricode": "AWY",
    }]


def _patch_run_analysis(season_minutes, out_players, candidate_name="Bench Player", candidate_pos="PG"):
    """
    Returns (games, lineups, dvp) for testing run_analysis
    without real NBA API calls.

    season_minutes: dict mapping player_id → avg minutes
    out_players:    list of dicts [{name, position}] placed in HME's out list
    """
    games = _make_games()
    lineups = {
        "HME": {
            "team_name": "TeamA",
            "starters": [{"name": candidate_name, "position": candidate_pos}],
            "out": out_players,
        },
        "AWY": {"team_name": "TeamB", "starters": [], "out": []},
    }
    dvp = {"PG": {"TeamB": {"rank": 2, "pts": 28.0}}}
    return games, lineups, dvp


def test_run_analysis_position_gate_compatible_starter_out_yields_candidate():
    """
    When the out starter's position is compatible with the candidate's position,
    the candidate is not skipped by the position gate and reaches scoring.
    With DVP rank 2 and recent pts above season avg, score = 4 (VERY FAVORABLE).
    """
    # PG out, PG candidate — positions match
    out_players = [{"name": "Star PG", "position": "PG"}]
    games, lineups, dvp = _patch_run_analysis(
        season_minutes={9999: 20.0, 8888: 30.0},
        out_players=out_players,
        candidate_name="Bench PG",
        candidate_pos="PG",
    )
    with patch("analysis.engine.get_all_teams_defense_zones", return_value={}), \
         patch("analysis.engine.get_player_season_data", return_value=(
             {9999: 20.0, 8888: 30.0}, {8888}
         )), \
         patch("analysis.engine._find_player_id", side_effect=lambda name: 8888 if "Star" in name else 9999), \
         patch("analysis.engine.get_player_recent_stats", return_value={"pts": 15.0, "season_avg_pts": 10.0, "min": 22.0, "games": 15}), \
         patch("analysis.engine.get_player_shot_zones", return_value={}):
        result = run_analysis(games, lineups, dvp, {}, None)
    # Gate did not crash and did not wrongly exclude a compatible candidate
    assert isinstance(result, dict)
    assert set(result.keys()) == {"pts", "ast", "reb", "three_pt"}
    # With rank-1 DVP and recent pts above season avg, the candidate should score >= 4
    assert len(result["pts"]) > 0, "Compatible PG candidate with elite DVP should not be excluded by position gate"


def test_run_analysis_position_gate_incompatible_starter_out_excludes_candidate():
    """
    When the only out starter is a C and the candidate is a PG,
    the position gate must exclude the candidate — result is empty.
    """
    out_players = [{"name": "Star C", "position": "C"}]
    games, lineups, dvp = _patch_run_analysis(
        season_minutes={9999: 20.0, 8888: 30.0},
        out_players=out_players,
        candidate_name="Bench PG",
        candidate_pos="PG",
    )
    with patch("analysis.engine.get_all_teams_defense_zones", return_value={}), \
         patch("analysis.engine.get_player_season_data", return_value=(
             {9999: 20.0, 8888: 30.0}, {8888}
         )), \
         patch("analysis.engine._find_player_id", side_effect=lambda name: 8888 if "Star" in name else 9999), \
         patch("analysis.engine.get_player_recent_stats", return_value={"pts": 15.0, "season_avg_pts": 10.0, "min": 22.0, "games": 15}), \
         patch("analysis.engine.get_player_shot_zones", return_value={}):
        result = run_analysis(games, lineups, dvp, {}, None)
    # PG cannot replace a C — must be excluded; all buckets empty
    assert all(len(v) == 0 for v in result.values())


def test_run_analysis_replaces_field_contains_only_matched_starters():
    """
    When two starters are out (PG and C) and the candidate is an SG,
    the replaces field must only list the PG (the compatible one), not the C.
    """
    out_players = [
        {"name": "Star PG", "position": "PG"},
        {"name": "Star C",  "position": "C"},
    ]
    games, lineups, dvp = _patch_run_analysis(
        season_minutes={9999: 20.0, 7777: 30.0, 8888: 30.0},
        out_players=out_players,
        candidate_name="Bench SG",
        candidate_pos="SG",
    )
    # Use a DVP that will produce a rating so the candidate appears in results
    dvp = {"SG": {"TeamB": {"rank": 1, "pts": 30.0}}}

    with patch("analysis.engine.get_all_teams_defense_zones", return_value={}), \
         patch("analysis.engine.get_player_season_data", return_value=(
             {9999: 20.0, 7777: 30.0, 8888: 30.0}, {7777, 8888}
         )), \
         patch("analysis.engine._find_player_id", side_effect=lambda name: {
             "Star PG": 7777, "Star C": 8888
         }.get(name, 9999)), \
         patch("analysis.engine.get_player_recent_stats", return_value={
             "pts": 20.0, "season_avg_pts": 10.0, "min": 28.0, "games": 15
         }), \
         patch("analysis.engine.get_player_shot_zones", return_value={}):
        result = run_analysis(games, lineups, dvp, {}, None)

    assert result["pts"], "Expected non-empty PTS result: SG candidate with rank-1 DVP vs TeamB should score >= 4 (VERY FAVORABLE)"
    assert result["pts"][0]["replaces"] == ["Star PG"]
    assert "Star C" not in result["pts"][0]["replaces"]


# ---------------------------------------------------------------------------
# main() wiring: filter_games_by_stake called before get_projected_lineups
# ---------------------------------------------------------------------------

def test_filter_games_by_stake_wiring_in_main():
    """
    Smoke test: filter_games_by_stake is called before get_projected_lineups
    when main() runs. Verifies the wiring order, not real standings data.
    """
    import main as main_module

    fake_games = [{
        "home_team_id": 1, "away_team_id": 2,
        "home_tricode": "HME", "away_tricode": "AWY",
    }]
    fake_standings = {
        1: {"team_id": 1, "seed": 8, "conference": "East",
            "games_back_from_above": 3.0, "games_ahead_of_below": 10.0, "games_remaining": 10},
        2: {"team_id": 2, "seed": 13, "conference": "East",
            "games_back_from_above": 12.0, "games_ahead_of_below": 5.0, "games_remaining": 6},
    }

    call_order = []

    with patch("main.get_todays_games", return_value=fake_games), \
         patch("main.get_conference_standings", side_effect=lambda: call_order.append("standings") or fake_standings), \
         patch("main.filter_games_by_stake", side_effect=lambda g, s: call_order.append("filter") or g) as m_filter, \
         patch("main.get_projected_lineups", side_effect=lambda: call_order.append("lineups") or {}) as m_lineups, \
         patch("main.get_defense_vs_position", return_value={}), \
         patch("main.run_analysis", return_value=[]), \
         patch("main.get_event_ids", return_value={}), \
         patch("main.get_player_lines", return_value={}), \
         patch("main.format_results", return_value=""):
        main_module.main()

    # standings and filter must precede lineups
    assert call_order.index("standings") < call_order.index("lineups")
    assert call_order.index("filter") < call_order.index("lineups")


# ---------------------------------------------------------------------------
# _score_player_ast
# ---------------------------------------------------------------------------


def test_ast_dvp_rank_1_scores_3():
    team_defense = {"PG": {"rank_ast": 1}}
    recent = {"ast": 8, "season_avg_ast": 7}
    score, rating, signals, ctx = _score_player_ast("PG", "OPP", team_defense, recent, None)
    assert signals["dvp"] == 3

def test_ast_dvp_rank_4_scores_2():
    team_defense = {"PG": {"rank_ast": 4}}
    recent = {"ast": 5, "season_avg_ast": 6}
    score, rating, signals, ctx = _score_player_ast("PG", "OPP", team_defense, recent, None)
    assert signals["dvp"] == 2

def test_ast_dvp_rank_7_scores_0():
    team_defense = {"PG": {"rank_ast": 7}}
    recent = {"ast": 8, "season_avg_ast": 7}
    score, rating, signals, ctx = _score_player_ast("PG", "OPP", team_defense, recent, None)
    assert signals["dvp"] == 0

def test_ast_potential_rank_3_scores_2():
    team_defense = {"PG": {"rank_ast": 1}}
    recent = {"ast": 8, "season_avg_ast": 7}
    tracking = {"rank_potential_ast": 3}
    score, rating, signals, ctx = _score_player_ast("PG", "OPP", team_defense, recent, tracking)
    assert signals["potential_ast"] == 2

def test_ast_potential_rank_8_scores_1():
    team_defense = {"PG": {"rank_ast": 1}}
    recent = {"ast": 8, "season_avg_ast": 7}
    tracking = {"rank_potential_ast": 8}
    score, rating, signals, ctx = _score_player_ast("PG", "OPP", team_defense, recent, tracking)
    assert signals["potential_ast"] == 1

def test_ast_potential_rank_11_scores_0():
    team_defense = {"PG": {"rank_ast": 1}}
    recent = {"ast": 8, "season_avg_ast": 7}
    tracking = {"rank_potential_ast": 11}
    score, rating, signals, ctx = _score_player_ast("PG", "OPP", team_defense, recent, tracking)
    assert signals["potential_ast"] == 0

def test_ast_full_score_6_best_of_night():
    team_defense = {"SG": {"rank_ast": 1}}
    recent = {"ast": 9, "season_avg_ast": 7}
    tracking = {"rank_potential_ast": 2}
    score, rating, signals, ctx = _score_player_ast("SG", "OPP", team_defense, recent, tracking)
    assert score == 6
    assert rating == "BEST OF THE NIGHT"

def test_ast_score_5_very_favorable():
    team_defense = {"PG": {"rank_ast": 3}}
    recent = {"ast": 8, "season_avg_ast": 7}
    tracking = {"rank_potential_ast": 2}
    score, rating, signals, ctx = _score_player_ast("PG", "OPP", team_defense, recent, tracking)
    assert score == 5
    assert rating == "VERY FAVORABLE"

def test_ast_score_4_filtered_out():
    team_defense = {"PG": {"rank_ast": 3}}
    recent = {"ast": 8, "season_avg_ast": 7}
    tracking = {"rank_potential_ast": 8}
    score, rating, signals, ctx = _score_player_ast("PG", "OPP", team_defense, recent, tracking)
    assert score == 4
    assert rating is None


# ---------------------------------------------------------------------------
# _score_player_reb
# ---------------------------------------------------------------------------


def test_reb_dvp_rank_2_scores_3():
    team_defense = {"C": {"rank_reb": 2}}
    recent = {"reb": 10, "season_avg_reb": 9}
    score, rating, signals, ctx = _score_player_reb("C", "OPP", team_defense, recent, None)
    assert signals["dvp"] == 3

def test_reb_dvp_rank_5_scores_2():
    team_defense = {"PF": {"rank_reb": 5}}
    recent = {"reb": 7, "season_avg_reb": 8}
    score, rating, signals, ctx = _score_player_reb("PF", "OPP", team_defense, recent, None)
    assert signals["dvp"] == 2

def test_reb_dvp_rank_8_scores_0():
    team_defense = {"C": {"rank_reb": 8}}
    recent = {"reb": 10, "season_avg_reb": 9}
    score, rating, signals, ctx = _score_player_reb("C", "OPP", team_defense, recent, None)
    assert signals["dvp"] == 0

def test_reb_opportunity_rank_3_scores_2():
    team_defense = {"C": {"rank_reb": 1}}
    recent = {"reb": 10, "season_avg_reb": 9}
    tracking = {"rank_reb_chances": 3}
    score, rating, signals, ctx = _score_player_reb("C", "OPP", team_defense, recent, tracking)
    assert signals["reb_opportunity"] == 2

def test_reb_opportunity_rank_7_scores_1():
    team_defense = {"C": {"rank_reb": 1}}
    recent = {"reb": 10, "season_avg_reb": 9}
    tracking = {"rank_reb_chances": 7}
    score, rating, signals, ctx = _score_player_reb("C", "OPP", team_defense, recent, tracking)
    assert signals["reb_opportunity"] == 1

def test_reb_opportunity_rank_11_scores_0():
    team_defense = {"C": {"rank_reb": 1}}
    recent = {"reb": 10, "season_avg_reb": 9}
    tracking = {"rank_reb_chances": 11}
    score, rating, signals, ctx = _score_player_reb("C", "OPP", team_defense, recent, tracking)
    assert signals["reb_opportunity"] == 0

def test_reb_full_score_6_best_of_night():
    team_defense = {"C": {"rank_reb": 2}}
    recent = {"reb": 10, "season_avg_reb": 9}
    tracking = {"rank_reb_chances": 1}
    score, rating, signals, ctx = _score_player_reb("C", "OPP", team_defense, recent, tracking)
    assert score == 6
    assert rating == "BEST OF THE NIGHT"

def test_reb_score_5_very_favorable():
    team_defense = {"PF": {"rank_reb": 4}}
    recent = {"reb": 8, "season_avg_reb": 7}
    tracking = {"rank_reb_chances": 2}
    score, rating, signals, ctx = _score_player_reb("PF", "OPP", team_defense, recent, tracking)
    assert score == 5
    assert rating == "VERY FAVORABLE"

def test_reb_score_4_filtered_out():
    team_defense = {"C": {"rank_reb": 4}}
    recent = {"reb": 10, "season_avg_reb": 9}
    tracking = {"rank_reb_chances": 8}
    score, rating, signals, ctx = _score_player_reb("C", "OPP", team_defense, recent, tracking)
    assert score == 4
    assert rating is None


# ---------------------------------------------------------------------------
# _score_player_3pt
# ---------------------------------------------------------------------------

TEAM_DEF_3PT_ELITE = {"PG": {"rank_ast": 10, "rank_reb": 10, "rank_three_pm": 2, "rank_three_pa": 3}}
TEAM_DEF_3PT_GOOD = {"PG": {"rank_ast": 10, "rank_reb": 10, "rank_three_pm": 5, "rank_three_pa": 5}}
TEAM_DEF_3PT_POOR = {"PG": {"rank_ast": 10, "rank_reb": 10, "rank_three_pm": 7, "rank_three_pa": 5}}
TEAM_DEF_3PT_RANK_PA_TOP3 = {"PG": {"rank_ast": 10, "rank_reb": 10, "rank_three_pm": 4, "rank_three_pa": 3}}
TEAM_DEF_3PT_RANK_PA_4 = {"PG": {"rank_ast": 10, "rank_reb": 10, "rank_three_pm": 4, "rank_three_pa": 4}}

RECENT_3PT_ABOVE_AVG = {"three_pm": 3.0, "season_avg_three_pm": 2.0, "three_pa": 8.0, "season_avg_three_pa": 6.0}
RECENT_3PT_BELOW_AVG = {"three_pm": 1.0, "season_avg_three_pm": 2.0, "three_pa": 8.0, "season_avg_three_pa": 6.0}
RECENT_3PT_VOLUME_DOWN = {"three_pm": 3.0, "season_avg_three_pm": 2.0, "three_pa": 5.0, "season_avg_three_pa": 6.0}


def test_3pt_gate_dvp_rank_above_6():
    score, rating, signals, context = _score_player_3pt(
        position="PG", opponent_name="TeamA",
        team_defense=TEAM_DEF_3PT_POOR,
        recent_stats=RECENT_3PT_ABOVE_AVG,
        tracking_data=None,
    )
    assert score == 0
    assert rating is None


def test_3pt_full_score_6():
    """DvP rank 2 (+3) + form above avg (+1) + both Signal 3 conditions (+2) = 6 BEST."""
    score, rating, signals, context = _score_player_3pt(
        position="PG", opponent_name="TeamA",
        team_defense=TEAM_DEF_3PT_ELITE,
        recent_stats=RECENT_3PT_ABOVE_AVG,
        tracking_data=None,
    )
    assert score == 6
    assert rating == "BEST OF THE NIGHT"
    assert signals["dvp"] == 3
    assert signals["recent_form"] == 1
    assert signals["potential_3pt"] == 2


def test_3pt_dvp_rank_3_to_6_gives_2():
    """DvP rank 5 (3-6 range) → +2 instead of +3. Max score = 5 = VERY FAVORABLE."""
    score, rating, signals, context = _score_player_3pt(
        position="PG", opponent_name="TeamA",
        team_defense=TEAM_DEF_3PT_GOOD,
        recent_stats=RECENT_3PT_ABOVE_AVG,
        tracking_data=None,
    )
    assert signals["dvp"] == 2
    assert score == 5  # 2 + 1 + 2
    assert rating == "VERY FAVORABLE"


def test_3pt_volume_down_opponent_permissive():
    """Volume DOWN but opponent permissive (rank_three_pa <= 6) → only one condition → +1."""
    score, rating, signals, context = _score_player_3pt(
        position="PG", opponent_name="TeamA",
        team_defense=TEAM_DEF_3PT_ELITE,
        recent_stats=RECENT_3PT_VOLUME_DOWN,
        tracking_data=None,
    )
    assert signals["potential_3pt"] == 1
    # DvP rank 2 (+3) + form +1 + one condition (+1) = 5
    assert score == 5
    assert rating == "VERY FAVORABLE"


def test_3pt_both_signal3_conditions():
    """rank_three_pa <= 6 AND volume up → +2 (both conditions met)."""
    score, rating, signals, context = _score_player_3pt(
        position="PG", opponent_name="TeamA",
        team_defense=TEAM_DEF_3PT_RANK_PA_TOP3,
        recent_stats=RECENT_3PT_ABOVE_AVG,
        tracking_data=None,
    )
    assert signals["potential_3pt"] == 2


def test_3pt_rank_pa_4_both_conditions():
    """rank_three_pa=4 (<=6, condition A met) + volume up (condition B met) → +2."""
    score, rating, signals, context = _score_player_3pt(
        position="PG", opponent_name="TeamA",
        team_defense=TEAM_DEF_3PT_RANK_PA_4,
        recent_stats=RECENT_3PT_ABOVE_AVG,
        tracking_data=None,
    )
    assert signals["potential_3pt"] == 2
    # DvP rank 4 (+2) + form +1 + both conditions (+2) = 5
    assert score == 5


def test_3pt_neither_signal3_condition():
    """Opponent NOT permissive (rank > 6) AND volume DOWN → 0 for Signal 3."""
    team_def_strict = {"PG": {"rank_ast": 10, "rank_reb": 10, "rank_three_pm": 2, "rank_three_pa": 8}}
    recent_vol_down = {"three_pm": 3.0, "season_avg_three_pm": 2.0, "three_pa": 5.0, "season_avg_three_pa": 6.0}
    score, rating, signals, context = _score_player_3pt(
        position="PG", opponent_name="TeamA",
        team_defense=team_def_strict,
        recent_stats=recent_vol_down,
        tracking_data=None,
    )
    assert signals["potential_3pt"] == 0
    # DvP rank 2 (+3) + form +1 + neither (0) = 4
    assert score == 4
    assert rating == "VERY FAVORABLE"


def test_3pt_only_volume_up():
    """Volume UP but opponent rank_three_pa > 6 → only one condition → +1."""
    team_def_strict = {"PG": {"rank_ast": 10, "rank_reb": 10, "rank_three_pm": 2, "rank_three_pa": 8}}
    score, rating, signals, context = _score_player_3pt(
        position="PG", opponent_name="TeamA",
        team_defense=team_def_strict,
        recent_stats=RECENT_3PT_ABOVE_AVG,
        tracking_data=None,
    )
    assert signals["potential_3pt"] == 1


# ---------------------------------------------------------------------------
# _dedup_candidates
# ---------------------------------------------------------------------------

def _c(name, game, score):
    """Shorthand to create a candidate dict."""
    return {"player_name": name, "game": game, "score": score}


def test_dedup_player_in_pts_and_ast_stays_in_best():
    """Player in PTS (5) and AST (6) -> stays in AST only."""
    candidates = {
        "pts": [_c("Alice", "G1", 5)],
        "ast": [_c("Alice", "G1", 6)],
        "reb": [],
        "three_pt": [],
    }
    result = _dedup_candidates(candidates)
    assert not any(p["player_name"] == "Alice" for p in result["pts"])
    assert any(p["player_name"] == "Alice" for p in result["ast"])


def test_dedup_tie_score_stays_in_higher_priority():
    """Tie score 5 in PTS and AST -> stays in PTS (priority 0 < 2)."""
    candidates = {
        "pts": [_c("Bob", "G1", 5)],
        "ast": [_c("Bob", "G1", 5)],
        "reb": [],
        "three_pt": [],
    }
    result = _dedup_candidates(candidates)
    assert any(p["player_name"] == "Bob" for p in result["pts"])
    assert not any(p["player_name"] == "Bob" for p in result["ast"])


def test_dedup_two_players_same_game_only_highest():
    """Two players same game in PTS -> only highest stays."""
    candidates = {
        "pts": [_c("Carol", "G1", 6), _c("Dave", "G1", 4)],
        "ast": [],
        "reb": [],
        "three_pt": [],
    }
    result = _dedup_candidates(candidates)
    assert len([p for p in result["pts"] if p["game"] == "G1"]) == 1
    assert result["pts"][0]["player_name"] == "Carol"


def test_dedup_max_5_per_stat():
    """8 players in PTS -> only 5 kept."""
    candidates = {
        "pts": [_c(f"P{i}", f"G{i}", 6 - i % 3) for i in range(8)],
        "ast": [],
        "reb": [],
        "three_pt": [],
    }
    result = _dedup_candidates(candidates)
    assert len(result["pts"]) <= 5


def test_dedup_player_in_3_stats_stays_in_best():
    """Player in PTS (3), AST (5), REB (4) -> stays in AST only."""
    candidates = {
        "pts": [_c("Eve", "G1", 3)],
        "ast": [_c("Eve", "G1", 5)],
        "reb": [_c("Eve", "G1", 4)],
        "three_pt": [],
    }
    result = _dedup_candidates(candidates)
    assert not any(p["player_name"] == "Eve" for p in result["pts"])
    assert any(p["player_name"] == "Eve" for p in result["ast"])
    assert not any(p["player_name"] == "Eve" for p in result["reb"])


# ---------------------------------------------------------------------------
# run_analysis — returns 4-stat dict
# ---------------------------------------------------------------------------

def test_run_analysis_returns_stat_dict():
    """run_analysis should return dict with pts/ast/reb/three_pt keys."""
    with patch("analysis.engine.get_all_teams_defense_zones", return_value={}), \
         patch("analysis.engine.get_player_season_data", return_value=({}, set())):
        result = run_analysis([], {}, {}, {}, None)
    assert isinstance(result, dict)
    assert set(result.keys()) == {"pts", "ast", "reb", "three_pt"}


def test_blowout_filter_excludes_at_threshold():
    """Odd exactly equal to threshold (1.10) should be excluded."""
    games = [GAME_BOS_LAL]
    moneylines = {("BOS", "LAL"): 1.10}
    result = filter_games_by_blowout(games, moneylines)
    assert result == []

def test_blowout_filter_excludes_below_threshold():
    """Odd below threshold (e.g. 1.05) should be excluded."""
    games = [GAME_BOS_LAL]
    moneylines = {("BOS", "LAL"): 1.05}
    result = filter_games_by_blowout(games, moneylines)
    assert result == []

def test_blowout_filter_includes_above_threshold():
    """Odd above threshold (e.g. 1.45) should be included."""
    games = [GAME_MIA_NYK]
    moneylines = {("MIA", "NYK"): 1.45}
    result = filter_games_by_blowout(games, moneylines)
    assert len(result) == 1
    assert result[0] is GAME_MIA_NYK

def test_blowout_filter_includes_when_no_odds_data():
    """Games without odds data should pass through (fail-open)."""
    games = [GAME_GSW_SAC]
    moneylines = {}
    result = filter_games_by_blowout(games, moneylines)
    assert len(result) == 1
    assert result[0] is GAME_GSW_SAC

def test_blowout_filter_mixed_games():
    """Multiple games: some excluded, some included."""
    games = [GAME_BOS_LAL, GAME_MIA_NYK, GAME_GSW_SAC]
    moneylines = {
        ("BOS", "LAL"): 1.08,
        ("MIA", "NYK"): 1.45,
    }
    result = filter_games_by_blowout(games, moneylines)
    assert len(result) == 2
    assert GAME_BOS_LAL not in result
    assert GAME_MIA_NYK in result
    assert GAME_GSW_SAC in result

def test_blowout_filter_logs_excluded_game(capsys):
    """Excluded games should log in the correct format."""
    games = [GAME_BOS_LAL]
    moneylines = {("BOS", "LAL"): 1.08}
    filter_games_by_blowout(games, moneylines)
    captured = capsys.readouterr()
    assert "[blowout-filter] BOS @ LAL" in captured.out
    assert "excluded" in captured.out
    assert "1.08" in captured.out

def test_blowout_threshold_value():
    """Threshold constant should be 1.10."""
    assert BLOWOUT_ODD_THRESHOLD == 1.10
