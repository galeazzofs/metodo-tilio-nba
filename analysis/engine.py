from nba_api.stats.static import players as nba_players_static
from scrapers.nba import (
    get_player_shot_zones,
    get_player_recent_stats,
    get_all_teams_defense_zones,
    get_player_season_stats,
    STARTER_MIN_THRESHOLD,
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


def _score_player(position, opponent_name, dvp, recent_stats, season_avg_pts, player_zones, opponent_defense_zones, is_stepping_up):
    """
    Score a player 0-7 across four signals.
    Thresholds: 7 = BEST OF THE NIGHT, 5-6 = VERY FAVORABLE.
    Returns (score, rating, signals_list).
    """
    score = 0
    signals = []

    # --- Gate 0: Stepping up (mandatory) ---
    if not is_stepping_up:
        return 0, None, []

    # --- Gate 1: DvP rank (0-3 pts) ---
    dvp_rank, dvp_pts = _best_dvp_rank(position, opponent_name, dvp)
    if dvp_rank is None:
        return 0, None, []
    if dvp_rank <= 3:
        score += 3
        signals.append(f"Elite matchup vs {opponent_name} (DvP #{dvp_rank}, {dvp_pts} pts/g allowed)")
    elif dvp_rank <= 6:
        score += 2
        signals.append(f"Good matchup vs {opponent_name} (DvP #{dvp_rank}, {dvp_pts} pts/g allowed)")
    else:
        # Rank > 6: not worth surfacing
        return 0, None, []

    # --- Signal 2: Recent scoring form (0-3 pts) ---
    if recent_stats:
        pts = recent_stats["pts"]
        mins = recent_stats["min"]
        if pts > season_avg_pts:
            if pts >= 18:
                score += 3
                signals.append(f"Hot scorer: {pts} pts avg last {recent_stats['games']}g")
            elif pts >= 12:
                score += 2
                signals.append(f"Solid scorer: {pts} pts avg last {recent_stats['games']}g")
            elif pts >= 7:
                score += 1
                signals.append(f"Moderate scorer: {pts} pts avg last {recent_stats['games']}g")
            # pts > season_avg but < 7: no points, no message

        if mins >= 25:
            signals.append(f"High usage: {mins} min avg")

    # --- Signal 3: Zone match (required gate) ---
    primary_zone = _get_primary_zone(player_zones) if player_zones else None
    weakest_zone = _get_opponent_weakest_zone(opponent_defense_zones)

    if primary_zone and weakest_zone:
        player_cat = _zone_category(primary_zone)
        opponent_cat = _zone_category(weakest_zone)
        pz = player_zones[primary_zone]
        zone_str = f"{primary_zone} ({pz['frequency']}% freq, {pz['pct']}% FG)"

        if player_cat == opponent_cat:
            score += 1
            signals.append(f"Zone match: scores from {zone_str} -{opponent_name} concedes most there ({weakest_zone})")
        else:
            # Zone mismatch: discard this player
            return 0, None, []

    # --- Rating ---
    if score >= 7:
        rating = "BEST OF THE NIGHT"
    elif score >= 5:
        rating = "VERY FAVORABLE"
    else:
        rating = None

    return score, rating, signals


# ---------------------------------------------------------------------------
# Main analysis
# ---------------------------------------------------------------------------

def run_analysis(games, lineups, dvp):
    """
    Returns up to 5 players -one per game -ranked by score.
    """
    print("  Fetching team defensive zone data...")
    all_defense_zones = get_all_teams_defense_zones()

    print("  Fetching player season stats (starter filter)...")
    season_stats = get_player_season_stats()

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

            has_injuries = bool(team_data.get("out"))
            opponent_name = opponent_data.get("team_name", opponent_tricode)
            opponent_team_id = tricode_to_team_id.get(opponent_tricode)
            opponent_defense_zones = all_defense_zones.get(opponent_team_id, {})

            # Core rule: only look at teams that have someone OUT tonight.
            # There is no replacement player to find if nobody is missing.
            if not has_injuries:
                continue

            for starter in team_data.get("starters", []):
                player_name = starter["name"]
                position = starter["position"]

                player_id = _find_player_id(player_name)
                if not player_id:
                    print(f"  [skip] No ID found for: {player_name}")
                    continue

                # --- KEY GATE: bench players only ---
                # We use season-avg minutes as a starter proxy (LeagueDashPlayerStats
                # does not expose GS). Players averaging >= 27 min/game this season
                # are regular starters and must be skipped.
                player_season = season_stats.get(player_id)
                if player_season is None:
                    print(f"  [skip] {player_name} - insufficient season data (<5 games)")
                    continue
                min_avg = player_season["min"]
                if min_avg >= STARTER_MIN_THRESHOLD:
                    print(f"  [skip] {player_name} - regular starter ({min_avg} min/g this season)")
                    continue

                season_avg_pts = player_season["pts"]  # safe: player_season is not None at this point

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
                    season_avg_pts=season_avg_pts,
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
                    })

    # One best player per game → top 5 overall
    top_per_game = []
    for game_label, players in candidates_by_game.items():
        if players:
            best = max(players, key=lambda x: x["score"])
            top_per_game.append(best)

    top_per_game.sort(key=lambda x: x["score"], reverse=True)
    return top_per_game[:5]
