"""
routers/nba.py — NBA live data endpoints with in-memory caching.
"""
import time
from fastapi import APIRouter, Depends
from deps import require_auth

router = APIRouter(prefix="/api/nba", tags=["nba"])

_cache: dict = {}

def _cache_get(key: str):
    entry = _cache.get(key)
    if entry and time.time() < entry["expires"]:
        return entry["data"]
    return None

def _cache_set(key: str, data, ttl: int):
    _cache[key] = {"data": data, "expires": time.time() + ttl}

def invalidate_cache():
    _cache.clear()

@router.get("/standings")
def get_standings(uid: str = Depends(require_auth)):
    cached = _cache_get("standings")
    if cached:
        return cached
    from scrapers.nba import get_conference_standings
    data = get_conference_standings()
    east, west = [], []
    for team_id, info in data.items():
        entry = {"team_id": team_id, **info}
        (east if info["conference"] == "East" else west).append(entry)
    east.sort(key=lambda x: x["seed"])
    west.sort(key=lambda x: x["seed"])
    result = {"east": east, "west": west}
    _cache_set("standings", result, ttl=3600)
    return result

@router.get("/today")
def get_today_games(uid: str = Depends(require_auth)):
    cached = _cache_get("today")
    if cached:
        return cached
    from scrapers.nba import get_todays_games, get_conference_standings
    from scrapers.rotowire import get_projected_lineups
    from analysis.engine import _team_has_stake

    games = get_todays_games()
    if not games:
        result = {"games": [], "message": "Sem jogos hoje"}
        _cache_set("today", result, ttl=1800)
        return result

    standings = get_conference_standings()
    lineups = get_projected_lineups()

    enriched = []
    for g in games:
        home_tc = g.get("home_tricode", "")
        away_tc = g.get("away_tricode", "")
        game_label = f"{away_tc} @ {home_tc}"

        # Determine stake tag: PLAYOFF, PLAY-IN, or LOW STAKE
        stake_tag = "LOW STAKE"
        for team_key in ["home_team_id", "away_team_id"]:
            team_id = g.get(team_key)
            team_standings = standings.get(team_id, {}) if team_id else {}
            if team_standings:
                has_stake, reason = _team_has_stake(team_standings)
                if has_stake:
                    seed = team_standings.get("seed", 99)
                    if seed <= 6:
                        stake_tag = "PLAYOFF"
                        break
                    elif seed <= 10:
                        if stake_tag != "PLAYOFF":
                            stake_tag = "PLAY-IN"

        # Get injuries from lineups
        injuries = []
        for team_tc in [home_tc, away_tc]:
            team_lineup = lineups.get(team_tc, {})
            for status_key in ["out", "questionable"]:
                for player in team_lineup.get(status_key, []):
                    injuries.append({
                        "name": player.get("name", ""),
                        "team": team_tc,
                        "status": status_key,
                    })

        enriched.append({
            **g,
            "game_label": game_label,
            "stake_tag": stake_tag,
            "injuries": injuries,
        })

    stake_order = {"PLAYOFF": 0, "PLAY-IN": 1, "LOW STAKE": 2}
    enriched.sort(key=lambda x: stake_order.get(x["stake_tag"], 3))
    result = {"games": enriched}
    _cache_set("today", result, ttl=1800)
    return result

@router.get("/dvp")
def get_dvp(uid: str = Depends(require_auth)):
    cached = _cache_get("dvp")
    if cached:
        return cached
    from scrapers.fantasypros import get_defense_vs_position
    data = get_defense_vs_position()
    snapshot = {}
    for pos, teams in data.items():
        sorted_teams = sorted(teams.items(), key=lambda x: x[1]["rank"])
        snapshot[pos] = [
            {"team": name, "rank": info["rank"], "pts": info["pts"]}
            for name, info in sorted_teams[:5]
        ]
    _cache_set("dvp", snapshot, ttl=3600)
    return snapshot
