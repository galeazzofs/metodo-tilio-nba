# Multi-Stat Player Analysis Design

**Date:** 2026-03-23
**Status:** Approved

## Overview

Expand the current PTS-only analysis engine to score players across 4 stat categories: **Points (PTS)**, **Assists (AST)**, **Rebounds (REB)**, and **3-Point Shots (3PT)**. Each stat has its own scoring pipeline with adapted signals. The UI displays 4 separate sections, and each player appears only once (in the stat where they score highest).

## Core Rules

- **Injury gate preserved for all stats:** Only bench players stepping up for an injured starter are analyzed.
- **DvP by position (PG, SG, SF, PF, C)** for all 4 stats.
- **PTS keeps FantasyPros** for DvP data; AST, REB, and 3PT use NBA API defensive stats.
- **No player duplication:** A player appears in only one stat section (the one with their highest score). Tiebreaker priority: PTS > 3PT > AST > REB.

## Data Layer Changes

### New NBA API Functions (`scrapers/nba.py`)

#### `get_team_defense_vs_position(last_n_games=15)`

Fetches how much each team concedes per position across all 30 teams.

**Implementation approach:** Use `leaguedashplayerstats` endpoint with `measure_type="Opponent"` and filter by `player_position_nullable` for each position. This gives opponent stats (what each team concedes) broken down by position. Requires 5 API calls (one per position: PG, SG, SF, PF, C), each returning all 30 teams. With 1s delay between calls, total ~5s.

Returns per team, per position (PG/SG/SF/PF/C):
- **AST** allowed to position
- **REB** allowed to position (total rebounds)
- **3PM** allowed to position

Data is cached per analysis run (fetched once, reused across all players).

#### `get_team_defense_tracking(last_n_games=15)`

Fetches advanced tracking stats for opponent defense. Uses `leaguedashptstats` with `player_or_team="Team"` and `pt_measure_type="Passing"` / `"Rebounding"` / `"SpeedDistance"`.

Returns per team:
- **Potential AST** allowed (from passing tracking)
- **REB opportunities** allowed (from rebounding tracking: `REB_CHANCES`)
- **Potential 3PM** allowed (from shooting tracking or derived from 3PA allowed)

If tracking endpoints are unavailable or return incomplete data, fallback values:
- **Potential AST fallback:** Use raw AST allowed (already available from base stats)
- **REB opportunities fallback:** Use total REB allowed
- **Potential 3PM fallback:** Use 3PA (three-point attempts) allowed as proxy

#### `get_player_recent_stats_extended(player_id, last_n_games=15)`

Extends current `get_player_recent_stats()` to also return:
- `ast` (recent avg + season avg)
- `reb` (recent avg + season avg)
- `three_pm` (recent avg + season avg)
- `three_pa` (recent avg)

These are all standard box score fields available in the existing `PlayerGameLog` endpoint — no additional API calls needed.

**Tracking stats (potential_ast, potential_three_pm):** Fetched separately via `playerdashptpass` and `playerdashptshotlog` if available. If unavailable for a player (common for low-minute bench players), use `None` and the scoring engine uses the fallback signal.

### Existing Scrapers (unchanged)

- **FantasyPros (`scrapers/fantasypros.py`):** Continues providing DvP for PTS only.
- **RotoWire (`scrapers/rotowire.py`):** No changes. Still provides projected lineups and injury data.

### Odds API Changes (`scrapers/odds.py`)

#### `get_player_lines()` — Extended Markets

Currently fetches `player_points` market only. Extended to also request:
- `player_assists`
- `player_rebounds`
- `player_threes` (verify exact market key from API docs at implementation time; may be `player_three_pointers`)

Returns: `{player_name: {"pts": 22.5, "ast": 8.5, "reb": 10.5, "three_pt": 3.5}}`

If a market is unavailable for a player, value is `None`. Graceful degradation — missing lines don't block analysis.

## Scoring Engine Changes (`analysis/engine.py`)

### Architecture: 4 Parallel Scoring Passes

The engine runs 4 independent scoring passes after candidate identification. Each pass uses the same 0-6 scale with 3 signals.

**DvP scoring is binary (gate):** Rank <= 6 awards 3 points; rank > 6 discards the player entirely (score = 0). There is no gradient. This matches the existing PTS implementation.

### PTS Scoring (unchanged)

| Signal | Criteria | Points |
|--------|----------|--------|
| DvP (FantasyPros) | Position rank <= 6: +3 / rank > 6: discard | 0 or 3 |
| Recent form | Last 15g avg PTS >= season avg PTS | 0-1 |
| Zone match | Primary shot zone = opponent's weakest defensive zone / mismatch: discard | 0 or 2 |

### AST Scoring (new)

| Signal | Criteria | Points |
|--------|----------|--------|
| DvP (NBA API) | AST allowed to position — rank top 6: +3 / else: discard | 0 or 3 |
| Recent form | Last 15g avg AST >= season avg AST | 0-1 |
| Potential AST match | Potential AST allowed by opponent to position — rank top 6: +2. **Fallback if tracking unavailable:** AST allowed rank top 3 (stricter threshold since less precise) | 0 or 2 |

### REB Scoring (new)

| Signal | Criteria | Points |
|--------|----------|--------|
| DvP (NBA API) | REB allowed to position — rank top 6: +3 / else: discard | 0 or 3 |
| Recent form | Last 15g avg REB >= season avg REB | 0-1 |
| REB opportunity | REB opportunities (REB_CHANCES) allowed by opponent to position — rank top 6: +2. **Fallback:** total REB allowed rank top 3 | 0 or 2 |

**Note:** "REB opportunities" = `REB_CHANCES` from NBA tracking stats — the number of rebound chances (missed shots where a player could contest) that the opponent allows per position.

### 3PT Scoring (new)

| Signal | Criteria | Points |
|--------|----------|--------|
| DvP (NBA API) | 3PM allowed to position — rank top 6: +3 / else: discard | 0 or 3 |
| Recent form | Last 15g avg 3PM >= season avg 3PM | 0-1 |
| Potential 3PT match | Player's 3PA (volume) is above their season avg AND opponent's 3PA allowed to position ranks top 6: +2. **Fallback if tracking unavailable:** use 3PA allowed rank top 3 | 0 or 2 |

### Rating Thresholds (same for all stats)

- Score >= 6: **"BEST OF THE NIGHT"**
- Score 4-5: **"VERY FAVORABLE"**
- Score < 4: Filtered out

### Dedup Logic

After all 4 passes complete, in this exact order:
1. Collect all rated candidates (score >= 4) across all 4 stats.
2. **Dedup first:** If a player appears in multiple stats, keep only the entry with the highest score. On tie, priority: PTS > 3PT > AST > REB.
3. **Then per-stat filtering:** Within each stat, apply max 1 per game (keep highest score per game), then take top 5.

This means: if Player A and Player B are both from the same game and both score in PTS, only the higher one stays in PTS. If Player A was deduped away from AST, Player B does NOT backfill into AST.

## Pipeline Execution Flow

```
1. get_todays_games()                         (NBA API — unchanged)
2. get_projected_lineups()                    (RotoWire — unchanged)
3. get_defense_vs_position()                  (FantasyPros — PTS only)
4. get_team_defense_vs_position()             (NEW — NBA API, 5 calls for 5 positions)
5. get_team_defense_tracking()                (NEW — NBA API, tracking stats, 2-3 calls)
6. For each game with injured starter:
   a. Identify candidates (bench, position compatible)
   b. Fetch extended recent stats (NBA API — same endpoint, more fields)
   c. Run 4 scoring passes: PTS, AST, REB, 3PT
7. Dedup — player stays in best stat only
8. Per-stat: max 1 per game, top 5
9. get_player_lines()                         (Odds API — PTS + AST + REB + 3PT)
10. Save to Firestore
11. Notify Telegram
```

**Shared pipeline:** Both `app.py` (manual trigger) and `scheduler.py` (automated trigger) currently duplicate the analysis pipeline. As part of this work, extract the pipeline into a shared function (e.g., `analysis/pipeline.py`) to avoid maintaining two copies of the new multi-stat flow.

## Firestore Structure

**Collection:** `analyses/{date_str}`

```json
{
  "date": "2026-03-23",
  "ran_at": "2026-03-23T10:30:45.123456+00:00",
  "triggered_by": "scheduler",
  "game_count": 10,
  "candidate_count": 12,
  "stats": {
    "pts": [
      {
        "player_name": "...",
        "player_id": 123,
        "team": "LAL",
        "position": "SG",
        "opponent": "BOS",
        "game": "LAL @ BOS",
        "score": 5,
        "rating": "VERY FAVORABLE",
        "signals": {
          "dvp": 3,
          "recent_form": 1,
          "zone_match": 2
        },
        "context": {
          "starter_out": "Anthony Davis",
          "dvp_rank": 3,
          "signal_descriptions": [
            "Elite matchup vs Celtics (DvP #3)",
            "Recent form above season avg"
          ]
        },
        "recent_stats": {
          "pts": 18.5,
          "reb": 5.1,
          "ast": 3.0,
          "min": 28.4
        },
        "line": {
          "value": 18.5,
          "odds": -110
        }
      }
    ],
    "ast": [],
    "reb": [],
    "three_pt": []
  }
}
```

**Key changes from current structure:**
- `results` array replaced by `stats` object with 4 keys (`pts`, `ast`, `reb`, `three_pt`).
- Each entry includes `signals` breakdown (numeric) and `context` (human-readable).
- `line` becomes an object with `value` and `odds` (or `null` if unavailable).
- `candidate_count` kept for backward compatibility (sum of all stat arrays). This preserves the existing Firestore query in `routers/analyses.py` which filters on `candidate_count > 0`.
- `player_id` added to each entry (not present in current output).

**Backward compatibility:** The history endpoint and frontend must handle both old-format (`results` array) and new-format (`stats` object) documents. Check for `stats` key; if absent, fall back to rendering `results` as before.

## Telegram Notification Format

```
🏀 SCOUT · 23/03/2026
8 jogos

📊 PONTOS (PTS)
🔥 #1 J. Harden (SG) — LAL
   BEST OF THE NIGHT
   Jogo: LAL @ BOS · Linha: O 22.5 (-110)
   › Elite matchup vs Celtics (DvP #2)
   › Forma recente acima da média

🎯 ASSISTÊNCIAS (AST)
⚡ #1 T. Haliburton (PG) — IND
   VERY FAVORABLE
   Jogo: IND vs MIA · Linha: O 8.5 (-115)
   › AST cedidas à posição — top 3
   › Potential AST — top 5

🏀 REBOTES (REB)
⚡ #1 I. Stewart (C) — DET
   VERY FAVORABLE
   Jogo: DET vs ORL · Linha: —
   › REB cedidos à posição — top 2
   › Oportunidades de REB — top 4

💧 CESTAS DE 3 (3PT)
🔥 #1 B. Hield (SG) — GSW
   BEST OF THE NIGHT
   Jogo: GSW vs SAC · Linha: O 3.5 (+100)
   › 3PM cedidas à posição — top 1
   › Potential 3PM match — jogador + defesa
```

**Empty sections are omitted** from the message.

**Message length:** With up to 20 players (5 per stat x 4 stats), the message may exceed Telegram's 4096-character limit. If the formatted message exceeds 4000 chars, split into multiple messages: one per stat section that has results.

## Frontend UI Changes (`static/analise.js`, `static/index.html`)

### Layout: 4 Stat Sections

Replace the current single grouped list with 4 sections:

```
📊 PONTOS (PTS)
  [Card] [Card] ... [Card]

🎯 ASSISTÊNCIAS (AST)
  [Card] [Card] ... [Card]

🏀 REBOTES (REB)
  [Card] [Card] ... [Card]

💧 CESTAS DE 3 (3PT)
  [Card] [Card] ... [Card]
```

### Card Content (per stat)

Each card shows:
- Player name, team, position
- Game (e.g., "LAL @ BOS")
- Rating badge (BEST OF THE NIGHT / VERY FAVORABLE)
- Betting line for that stat (or hidden if unavailable)
- Top 2 signal descriptions
- Relevant recent stats for the section (e.g., AST section shows AST avg)
- Starter replaced (who is out)

### Empty Section

"Nenhuma oportunidade identificada hoje" with muted styling.

### History

History entries updated to show stats breakdown instead of flat list. Each historical entry shows player chips grouped by stat. Must handle old-format documents (flat `results` array) for backward compatibility.

## Files Affected

| File | Change |
|------|--------|
| `scrapers/nba.py` | Add `get_team_defense_vs_position()`, `get_team_defense_tracking()`, extend `get_player_recent_stats()` |
| `scrapers/odds.py` | Extend `get_player_lines()` for 4 markets |
| `analysis/engine.py` | Add 3 new scoring functions (`_score_player_ast`, `_score_player_reb`, `_score_player_3pt`), dedup logic, refactor `run_analysis()` to return 4-stat structure |
| `analysis/pipeline.py` | **NEW** — Extract shared pipeline from `app.py` and `scheduler.py` |
| `scheduler.py` | Use shared pipeline, update Firestore save format |
| `app.py` | Use shared pipeline, update status/result serialization |
| `scrapers/telegram.py` | New 4-section message format, message splitting for length |
| `static/analise.js` | Render 4 sections, update card template, update history, backward compat |
| `static/index.html` | Section containers for 4 stats |
| `output/formatter.py` | Update plain text format for 4 stats |
| `routers/analyses.py` | Handle new Firestore structure, keep `candidate_count` query working |
| `tests/test_engine.py` | Tests for new scoring functions, dedup logic, shared pipeline |

## Rate Limiting Considerations

- NBA API defensive stats by position: 5 calls (one per position), ~5s total with 1s delay.
- NBA API tracking stats: 2-3 calls for team-level tracking data, ~3s total.
- Player stats: Already rate-limited at 1s delay. Extended stats use same `PlayerGameLog` endpoint with more fields parsed — no extra calls.
- Odds API: Fetches 4 markets per event instead of 1. Each event is still a single API call (multiple markets in one request). Check quota usage.
- FantasyPros: Unchanged (1 call per run for PTS DvP).
- Total additional time per run: ~8-10s for team defense data (acceptable).
