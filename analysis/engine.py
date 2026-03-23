from nba_api.stats.static import players as nba_players_static
from scrapers.nba import (
    get_player_shot_zones,
    get_player_recent_stats,
    get_all_teams_defense_zones,
    get_player_season_data,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PAINT_ZONES = {"Restricted Area", "In The Paint (Non-RA)"}
MID_ZONES = {"Mid-Range"}
THREE_ZONES = {"Left Corner 3", "Right Corner 3", "Above the Break 3"}

POSITION_MAP = {
    "PG": ["PG"],
    "SG": ["SG"],
    "SF": ["SF"],
    "PF": ["PF"],
    "C":  ["C"],
    "G":  ["PG", "SG"],
    "F":  ["SF", "PF"],
}

POSITION_COMPAT = {
    "PG": {"PG", "SG", "G"},
    "SG": {"SG", "PG", "G"},
    "G":  {"G",  "PG", "SG"},
    "SF": {"SF", "PF", "F"},
    "PF": {"PF", "SF", "F", "C"},
    "F":  {"F",  "SF", "PF"},
    "C":  {"C",  "PF"},
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_player_id(name):
    matches = nba_players_static.find_players_by_full_name(name)
    if matches:
        return matches[0]["id"]
    last = name.split()[-1]
    matches = nba_players_static.find_players_by_full_name(last)
    return matches[0]["id"] if matches else None


def _get_primary_zone(zones):
    """Zone with highest shot frequency (min 5 attempts)."""
    if not zones:
        return None
    eligible = {z: d for z, d in zones.items() if d["attempts"] >= 5}
    if not eligible:
        return max(zones, key=lambda z: zones[z]["attempts"])
    return max(eligible, key=lambda z: eligible[z]["frequency"])


def _zone_category(zone_name):
    if zone_name in PAINT_ZONES:
        return "paint"
    if zone_name in MID_ZONES:
        return "mid"
    if zone_name in THREE_ZONES:
        return "three"
    return "other"


def _get_opponent_weakest_zone(team_defense_zones):
    """
    Returns the zone category where the opponent concedes the most points.
    Uses FGA * FG_PCT as a proxy for points allowed per zone.
    """
    if not team_defense_zones:
        return None

    best_zone = None
    best_score = -1

    for zone, stats in team_defense_zones.items():
        # Points-allowed proxy: made shots per game from this zone
        zone_score = stats["fgm"]
        if zone_score > best_score:
            best_score = zone_score
            best_zone = zone

    return best_zone


def _best_dvp_rank(position, opponent_name, dvp):
    positions = POSITION_MAP.get(position, [position])
    best_rank = None
    best_pts = None

    for pos in positions:
        pos_data = dvp.get(pos, {})
        for fp_team, data in pos_data.items():
            if opponent_name.lower() in fp_team.lower() or fp_team.lower() in opponent_name.lower():
                if best_rank is None or data["rank"] < best_rank:
                    best_rank = data["rank"]
                    best_pts = data["pts"]

    return best_rank, best_pts


def _position_compatible(candidate_pos, out_starters):
    """
    Returns the subset of out_starters that this candidate can replace.

    Looks up candidate_pos in POSITION_COMPAT to get the set of out-starter
    positions this candidate covers, then filters out_starters to those whose
    position falls in that set.
    """
    allowed = POSITION_COMPAT.get(candidate_pos, set())
    return [s for s in out_starters if s.get("position", "") in allowed]


def _team_has_stake(team_data):
    """
    Returns (has_stake: bool, reason_tag: str).

    reason_tag is one of: "can improve", "can be caught", "eliminated"

    Stake conditions:
      can_improve  = games_back_from_above is not None
                     and games_back_from_above <= games_remaining
      can_be_caught = games_ahead_of_below is not None
                      and games_ahead_of_below <= games_remaining

    When both are True, returns "can improve" as the primary tag.
    filter_games_by_stake is responsible for appending " (both)" when needed.
    """
    gb_above = team_data.get("games_back_from_above")
    gb_below = team_data.get("games_ahead_of_below")
    remaining = team_data.get("games_remaining", 0)

    can_improve = gb_above is not None and gb_above <= remaining
    can_be_caught = gb_below is not None and gb_below <= remaining

    if can_improve:
        return True, "can improve"
    if can_be_caught:
        return True, "can be caught"
    return False, "eliminated"


def _ordinal(n):
    """Return English ordinal string for integer n (e.g. 1 → '1st', 11 → '11th')."""
    if 11 <= (n % 100) <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _format_team_line(tricode, team_data, reason_tag):
    """Build the detail log line for one team, prefixed with tricode."""
    seed = team_data["seed"]
    conf = team_data["conference"][0].upper()
    gb_above = team_data["games_back_from_above"]
    gb_below = team_data["games_ahead_of_below"]
    remaining = team_data["games_remaining"]

    above_str = (
        "n/a above" if gb_above is None
        else f"{gb_above} GB from {_ordinal(seed - 1)} (above)"
    )
    below_str = (
        "n/a below" if gb_below is None
        else f"{gb_below} ahead of {_ordinal(seed + 1)} (below)"
    )
    return (
        f"  {tricode}: seed {seed}{conf}, {above_str}, {below_str}, "
        f"{remaining} remaining → {reason_tag}"
    )


def _tighter_margin(data):
    """Return the smaller of games_back_from_above / games_ahead_of_below (None = inf)."""
    vals = [v for v in [data["games_back_from_above"], data["games_ahead_of_below"]] if v is not None]
    return min(vals) if vals else float("inf")


def filter_games_by_stake(games, standings):
    """
    Filters games to those where at least one team has playoff/play-in stake.

    A team has a stake if it can still improve its seed OR be caught by the
    team below it within the remaining games of the regular season.

    Games where a team_id is missing from standings are passed through with a warning.
    Returns the filtered list (same structure as input).
    """
    filtered = []

    for game in games:
        home_id = game["home_team_id"]
        away_id = game["away_team_id"]
        home_tri = game["home_tricode"]
        away_tri = game["away_tricode"]
        label = f"{away_tri} @ {home_tri}"

        # Handle missing standings data
        if home_id not in standings or away_id not in standings:
            missing = [tid for tid in (home_id, away_id) if tid not in standings]
            for tid in missing:
                print(f"[stake-filter] WARNING: no standings data for team_id={tid} — including game by default")
            filtered.append(game)
            continue

        home_data = standings[home_id]
        away_data = standings[away_id]

        home_stake, home_tag = _team_has_stake(home_data)
        away_stake, away_tag = _team_has_stake(away_data)

        if not home_stake and not away_stake:
            print(f"[stake-filter] {label} — skipped: neither team has a stake")
            print(_format_team_line(home_tri, home_data, home_tag))
            print(_format_team_line(away_tri, away_data, away_tag))
            continue

        # At least one team has a stake — include the game
        if home_stake and away_stake:
            if _tighter_margin(home_data) <= _tighter_margin(away_data):
                home_tag = home_tag + " (both)"
            else:
                away_tag = away_tag + " (both)"
            print(f"[stake-filter] {label} — included (both teams have stake)")
        else:
            print(f"[stake-filter] {label} — included")

        print(_format_team_line(home_tri, home_data, home_tag))
        print(_format_team_line(away_tri, away_data, away_tag))

        filtered.append(game)

    return filtered


def _score_player(position, opponent_name, dvp, recent_stats, player_zones, opponent_defense_zones, is_stepping_up):
    """
    Score a player 0-6 across three signals (stepping up is a mandatory gate).
    Thresholds: 6 = BEST OF THE NIGHT, 4-5 = VERY FAVORABLE.
    Returns (score, rating, signals_list).
    """
    score = 0
    signals = []

    # --- Gate 0: Stepping up (mandatory) ---
    if not is_stepping_up:
        return 0, None, []

    # --- Signal 1: DvP rank (0-3 pts) ---
    dvp_rank, dvp_pts = _best_dvp_rank(position, opponent_name, dvp)
    if dvp_rank is None:
        return 0, None, []
    if dvp_rank <= 6:
        score += 3
        signals.append(f"Elite matchup vs {opponent_name} (DvP #{dvp_rank}, {dvp_pts} pts/g allowed)")
    else:
        # Rank > 6: not worth surfacing
        return 0, None, []

    # --- Signal 2: Recent form vs season avg (0-1 pt) ---
    if recent_stats:
        pts_recent = recent_stats["pts"]
        season_avg_pts = recent_stats.get("season_avg_pts", 0)
        mins = recent_stats["min"]
        if pts_recent >= season_avg_pts:
            score += 1
            signals.append(f"Forma recente acima da média (15j: {pts_recent} pts vs {season_avg_pts} pts/g na season)")

        if mins >= 25:
            signals.append(f"High usage: {mins} min avg")

    # --- Signal 3: Zone match (required gate) ---
    # If the player's primary zone doesn't match where the opponent concedes,
    # the play isn't valid regardless of DvP rank or scoring form.
    primary_zone = _get_primary_zone(player_zones) if player_zones else None
    weakest_zone = _get_opponent_weakest_zone(opponent_defense_zones)

    if primary_zone and weakest_zone:
        player_cat = _zone_category(primary_zone)
        opponent_cat = _zone_category(weakest_zone)
        pz = player_zones[primary_zone]
        zone_str = f"{primary_zone} ({pz['frequency']}% freq, {pz['pct']}% FG)"

        if player_cat == opponent_cat:
            score += 2
            signals.append(f"Zone match: scores from {zone_str} -{opponent_name} concedes most there ({weakest_zone})")
        else:
            # Zone mismatch: discard this player
            return 0, None, []

    # --- Rating ---
    if score >= 6:
        rating = "BEST OF THE NIGHT"
    elif score >= 4:
        rating = "VERY FAVORABLE"
    else:
        rating = None

    return score, rating, signals


def _score_player_ast(position, opponent_name, team_defense, recent_stats, tracking_data, is_stepping_up):
    """
    Score a player's assist upside (0-6 scale).
    Returns (score, rating, signals_dict, context_dict).
    """
    # --- Gate 0: Stepping up (mandatory) ---
    if not is_stepping_up:
        return 0, None, {}, {}

    pos_def = team_defense.get(position, {})
    dvp_rank = pos_def.get("rank_ast")

    score = 0
    signals = {}
    descriptions = []

    # --- Signal 1: DvP AST rank (0 or 3 pts) ---
    if dvp_rank is None or dvp_rank > 6:
        return 0, None, {}, {}

    score += 3
    signals["dvp"] = 3
    descriptions.append(f"Elite AST matchup vs {opponent_name} (DvP #{dvp_rank})")

    # --- Signal 2: Recent form (0 or 1 pt) ---
    ast_recent = recent_stats.get("ast", 0)
    season_avg_ast = recent_stats.get("season_avg_ast", 0)
    if ast_recent >= season_avg_ast:
        score += 1
        signals["recent_form"] = 1
        descriptions.append(f"AST form above avg ({ast_recent} vs {season_avg_ast} season)")
    else:
        signals["recent_form"] = 0

    # --- Signal 3: Potential AST (0 or 2 pts) ---
    potential_bonus = 0
    if tracking_data is not None and tracking_data.get("rank_potential_ast", 99) <= 6:
        potential_bonus = 2
        descriptions.append(f"High potential AST (tracking rank {tracking_data['rank_potential_ast']})")
    elif tracking_data is None and dvp_rank <= 3:
        potential_bonus = 2
        descriptions.append(f"Fallback: top-3 DvP AST rank ({dvp_rank}) as potential AST proxy")

    if potential_bonus:
        score += potential_bonus
        signals["potential_ast"] = potential_bonus
    else:
        signals["potential_ast"] = 0

    # --- Rating ---
    if score >= 6:
        rating = "BEST OF THE NIGHT"
    elif score >= 4:
        rating = "VERY FAVORABLE"
    else:
        rating = None

    context = {"dvp_rank": dvp_rank, "signal_descriptions": descriptions}
    return score, rating, signals, context


def _score_player_reb(position, opponent_name, team_defense, recent_stats, tracking_data, is_stepping_up):
    """
    Score a player's rebound upside (0-6 scale).
    Returns (score, rating, signals_dict, context_dict).
    """
    if not is_stepping_up:
        return 0, None, {}, {}

    pos_def = team_defense.get(position, {})
    dvp_rank = pos_def.get("rank_reb")

    score = 0
    signals = {}
    descriptions = []

    # --- Signal 1: DvP REB rank (0 or 3 pts) ---
    if dvp_rank is None or dvp_rank > 6:
        return 0, None, {}, {}

    score += 3
    signals["dvp"] = 3
    descriptions.append(f"Elite REB matchup vs {opponent_name} (DvP #{dvp_rank})")

    # --- Signal 2: Recent form (0 or 1 pt) ---
    reb_recent = recent_stats.get("reb", 0)
    season_avg_reb = recent_stats.get("season_avg_reb", 0)
    if reb_recent >= season_avg_reb:
        score += 1
        signals["recent_form"] = 1
        descriptions.append(f"REB form above avg ({reb_recent} vs {season_avg_reb} season)")
    else:
        signals["recent_form"] = 0

    # --- Signal 3: Rebound opportunity (0 or 2 pts) ---
    reb_bonus = 0
    if tracking_data is not None and tracking_data.get("rank_reb_chances", 99) <= 6:
        reb_bonus = 2
        descriptions.append(f"High REB chances (tracking rank {tracking_data['rank_reb_chances']})")
    elif tracking_data is None and dvp_rank <= 3:
        reb_bonus = 2
        descriptions.append(f"Fallback: top-3 DvP REB rank ({dvp_rank}) as rebound opportunity proxy")

    if reb_bonus:
        score += reb_bonus
        signals["reb_opportunity"] = reb_bonus
    else:
        signals["reb_opportunity"] = 0

    # --- Rating ---
    if score >= 6:
        rating = "BEST OF THE NIGHT"
    elif score >= 4:
        rating = "VERY FAVORABLE"
    else:
        rating = None

    context = {"dvp_rank": dvp_rank, "signal_descriptions": descriptions}
    return score, rating, signals, context


# ---------------------------------------------------------------------------
# Main analysis
# ---------------------------------------------------------------------------

def run_analysis(games, lineups, dvp):
    """
    Returns up to 5 players -one per game -ranked by score.
    """
    print("  Fetching team defensive zone data...")
    all_defense_zones = get_all_teams_defense_zones()

    print("  Fetching player season data (starter/bench classification)...")
    season_minutes, starter_ids = get_player_season_data()

    # Build tricode → team_id map from today's games
    tricode_to_team_id = {}
    for game in games:
        tricode_to_team_id[game["home_tricode"]] = game["home_team_id"]
        tricode_to_team_id[game["away_tricode"]] = game["away_team_id"]

    # Collect all scored candidates, grouped by game
    candidates_by_game = {}

    for game in games:
        game_label = f"{game['away_tricode']} @ {game['home_tricode']}"
        candidates_by_game[game_label] = []

        for player_tricode, opponent_tricode in [
            (game["home_tricode"], game["away_tricode"]),
            (game["away_tricode"], game["home_tricode"]),
        ]:
            team_data = lineups.get(player_tricode, {})
            opponent_data = lineups.get(opponent_tricode, {})

            if not team_data:
                continue

            opponent_name = opponent_data.get("team_name", opponent_tricode)
            opponent_team_id = tricode_to_team_id.get(opponent_tricode)
            opponent_defense_zones = all_defense_zones.get(opponent_team_id, {})

            # Core rule: only look at teams where a *starter* is out tonight.
            # A bench player being out creates no stepping-up opportunity.
            out_starters = []
            for p in team_data.get("out", []):
                pid = _find_player_id(p["name"])
                if pid and pid in starter_ids:
                    out_starters.append({"name": p["name"], "position": p.get("position", "")})

            if not out_starters:
                print(f"  [skip] {player_tricode} - no starter out tonight (only bench players out or no injuries)")
                continue

            for starter in team_data.get("starters", []):
                player_name = starter["name"]
                position = starter["position"]

                player_id = _find_player_id(player_name)
                if not player_id:
                    print(f"  [skip] No ID found for: {player_name}")
                    continue

                # --- KEY GATE: bench players only ---
                # Uses NBA's own starter/bench classification (GS/GP > 50%).
                # This correctly identifies high-usage bench players (6th man
                # types averaging 28+ min/g) as bench players.
                min_avg = season_minutes.get(player_id)
                if min_avg is None:
                    print(f"  [skip] {player_name} - insufficient season data (<5 games)")
                    continue
                if player_id in starter_ids:
                    print(f"  [skip] {player_name} - regular starter ({min_avg} min/g this season)")
                    continue

                # --- Position gate: candidate must cover at least one out starter ---
                matched_starters = _position_compatible(position, out_starters)
                if not matched_starters:
                    print(f"  [skip] {player_name} - no position-compatible starter out ({position})")
                    continue

                print(f"  Analyzing {player_name} ({player_tricode} vs {opponent_tricode}, {min_avg} min/g)...")

                try:
                    recent_stats = get_player_recent_stats(player_id)
                    player_zones = get_player_shot_zones(player_id)
                except Exception as e:
                    print(f"    [error] {e} - skipping {player_name}")
                    continue

                score, rating, signals = _score_player(
                    position=position,
                    opponent_name=opponent_name,
                    dvp=dvp,
                    recent_stats=recent_stats,
                    player_zones=player_zones,
                    opponent_defense_zones=opponent_defense_zones,
                    is_stepping_up=True,  # always True: bench player on injured team
                )

                if rating:
                    candidates_by_game[game_label].append({
                        "player": player_name,
                        "team": team_data["team_name"],
                        "position": position,
                        "game": game_label,
                        "score": score,
                        "rating": rating,
                        "signals": signals,
                        "recent_stats": recent_stats,
                        "primary_zone": _get_primary_zone(player_zones),
                        "replaces": [s["name"] for s in matched_starters],
                    })

    # One best player per game → top 5 overall
    top_per_game = []
    for game_label, players in candidates_by_game.items():
        if players:
            best = max(players, key=lambda x: x["score"])
            top_per_game.append(best)

    top_per_game.sort(key=lambda x: x["score"], reverse=True)
    return top_per_game[:5]
