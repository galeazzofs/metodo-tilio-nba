# Design: Scoring Engine Tightening

**Date:** 2026-03-18
**Files affected:** `analysis/engine.py`, `scrapers/nba.py`

---

## Overview

Tighten the player scoring engine to reduce false positives. The main changes are:
- Stricter DvP matchup gate (top 6 teams only, down from top 12)
- Recent form signal now requires pts to be above season average before scoring
- Signal 4 (stepping up) converted from a scoring bonus to a mandatory gate
- Thresholds lowered to match the new max score of 7

---

## Changes

### `scrapers/nba.py`

#### `get_player_season_minutes` → `get_player_season_stats`

Rename the function and extend the return value to include `PTS` alongside `MIN`. No additional API call needed — `LeagueDashPlayerStats` already returns `PTS` in the same DataFrame.

**Before:**
```python
def get_player_season_minutes() -> dict[int, float]:
    # returns {player_id: avg_min}
```

**After:**
```python
def get_player_season_stats() -> dict[int, dict]:
    # returns {player_id: {"min": float, "pts": float}}
```

---

### `analysis/engine.py`

#### Import update

```python
from scrapers.nba import (
    ...
    get_player_season_stats,   # was: get_player_season_minutes
    ...
)
```

#### `_score_player` — signature change

```python
# Before
def _score_player(position, opponent_name, dvp, recent_stats, player_zones, opponent_defense_zones, is_stepping_up):

# After
def _score_player(position, opponent_name, dvp, recent_stats, season_avg_pts, player_zones, opponent_defense_zones, is_stepping_up):
```

#### Gate 0 (new): Stepping up

Added at the top of `_score_player`, before any scoring logic:

```python
if not is_stepping_up:
    return 0, None, []
```

Rationale: the entire analysis is predicated on a bench player filling a role created by an injury. If this condition is not met, no other signal is relevant.

#### Gate 1 (DvP): Stricter rank threshold

| | Before | After |
|---|---|---|
| Gate cutoff | rank > 12 → discard | rank > 6 → discard |
| +3 pts | rank ≤ 8 | rank ≤ 3 |
| +2 pts | rank 9–12 | rank 4–6 |

Only top-6 defensive weaknesses qualify. This reduces volume and improves precision.

#### Signal 2 (Recent form): Above-average gate

Before scoring, check if `pts_recent > season_avg_pts`. If not, score 0 for this signal (no points added, no signal message appended).

If above average, apply thresholds as before:

| pts_recent | Points |
|---|---|
| ≥ 18 | +3 |
| ≥ 12 | +2 |
| ≥ 7 | +1 |
| < 7 | +0 |

Rationale: a player averaging 15 pts/game recently is only interesting if that's above their season baseline. Someone averaging 15 on a 16-pt season is not trending up.

#### Signal 3 (Zone match): Unchanged

Still a gate: zone mismatch discards the player entirely (+1 if match).

#### Signal 4 (Stepping up): Converted to gate, no longer scores

- Was: `score += 1` if `is_stepping_up`
- Now: mandatory gate at top of function (see Gate 0 above)
- The `signals.append("Stepping up due to teammate injury")` message is also removed

#### Rating thresholds

New max score is 7 (3 + 3 + 1 = DvP + form + zone match).

| Score | Rating (before) | Rating (after) |
|---|---|---|
| ≥ 8 | BEST OF THE NIGHT | — (unreachable) |
| ≥ 7 | — | BEST OF THE NIGHT |
| ≥ 6 | VERY FAVORABLE | — |
| ≥ 5 | — | VERY FAVORABLE |
| 4–5 | FAVORABLE | None (not surfaced) |
| < 4 | None | None |

The FAVORABLE tier is removed entirely. Only BEST OF THE NIGHT and VERY FAVORABLE are surfaced.

#### `run_analysis` — loop updates

```python
# Before
season_minutes = get_player_season_minutes()
# ...
min_avg = season_minutes.get(player_id)
# ...
score, rating, signals = _score_player(..., is_stepping_up=True)

# After
season_stats = get_player_season_stats()
# ...
player_stats = season_stats.get(player_id)
min_avg = player_stats.get("min") if player_stats else None
# ...
season_avg_pts = player_stats["pts"]
score, rating, signals = _score_player(..., season_avg_pts=season_avg_pts, is_stepping_up=True)
```

---

## Score breakdown (new max: 7)

| Signal | Max pts | Type |
|---|---|---|
| Gate 0: Stepping up | — | Gate (discard if False) |
| Gate 1: DvP rank ≤ 6 | 3 | Gate (discard if > 6) + points |
| Signal 2: Recent pts > season avg | 3 | Signal (0 if not above avg) |
| Gate 3: Zone match | 1 | Gate (discard if mismatch) + points |
| **Total** | **7** | |

---

## What does not change

- `get_player_recent_stats` — unchanged
- `get_player_shot_zones` — unchanged
- `get_all_teams_defense_zones` — unchanged
- The one-player-per-game / top-5 selection logic — unchanged
- The `STARTER_MIN_THRESHOLD` filter — unchanged
