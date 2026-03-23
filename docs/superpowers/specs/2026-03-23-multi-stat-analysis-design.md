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

Fetches how much each team concedes per position across all 30 teams. Uses NBA API endpoints (`leaguedashptdefend` or equivalent).

Returns per team, per position (PG/SG/SF/PF/C):
- **AST** allowed to position
- **Potential AST** allowed to position
- **REB** allowed to position (total rebounds)
- **REB opportunities** allowed to position
- **3PM** allowed to position
- **Potential 3PM** allowed to position

Data is cached per analysis run (fetched once, reused across all players).

#### `get_player_recent_stats_extended(player_id, last_n_games=15)`

Extends current `get_player_recent_stats()` to also return:
- `ast` (recent avg + season avg)
- `reb` (recent avg + season avg)
- `three_pm` (recent avg + season avg)
- `three_pa` (recent avg)
- `potential_ast` (if available)
- `potential_three_pm` (if available)

### Existing Scrapers (unchanged)

- **FantasyPros (`scrapers/fantasypros.py`):** Continues providing DvP for PTS only.
- **RotoWire (`scrapers/rotowire.py`):** No changes. Still provides projected lineups and injury data.

### Odds API Changes (`scrapers/odds.py`)

#### `get_player_lines()` — Extended Markets

Currently fetches `player_points` market only. Extended to also request:
- `player_assists`
- `player_rebounds`
- `player_threes`

Returns: `{player_name: {"pts": 22.5, "ast": 8.5, "reb": 10.5, "three_pt": 3.5}}`

If a market is unavailable for a player, value is `None`. Graceful degradation — missing lines don't block analysis.

## Scoring Engine Changes (`analysis/engine.py`)

### Architecture: 4 Parallel Scoring Passes

The engine runs 4 independent scoring passes after candidate identification. Each pass uses the same 0-6 scale with 3 signals.

### PTS Scoring (unchanged)

| Signal | Criteria | Points |
|--------|----------|--------|
| DvP (FantasyPros) | Position rank <= 6 (gate) | 0-3 |
| Recent form | Last 15g avg PTS >= season avg PTS | 0-1 |
| Zone match | Primary shot zone = opponent's weakest defensive zone | 0-2 |

### AST Scoring (new)

| Signal | Criteria | Points |
|--------|----------|--------|
| DvP (NBA API) | AST allowed to position — rank top 6 among all teams (gate) | 0-3 |
| Recent form | Last 15g avg AST >= season avg AST | 0-1 |
| Potential AST match | Potential AST allowed by opponent to position — top 6 | 0-2 |

### REB Scoring (new)

| Signal | Criteria | Points |
|--------|----------|--------|
| DvP (NBA API) | REB allowed to position — rank top 6 (gate) | 0-3 |
| Recent form | Last 15g avg REB >= season avg REB | 0-1 |
| REB opportunity | Rebound opportunities allowed by opponent to position — top 6 | 0-2 |

### 3PT Scoring (new)

| Signal | Criteria | Points |
|--------|----------|--------|
| DvP (NBA API) | 3PM allowed to position — rank top 6 (gate) | 0-3 |
| Recent form | Last 15g avg 3PM >= season avg 3PM | 0-1 |
| Potential 3PT match | Player's potential 3PM vs opponent's potential 3PM allowed to position — both high scores | 0-2 |

### Rating Thresholds (same for all stats)

- Score >= 6: **"BEST OF THE NIGHT"**
- Score 4-5: **"VERY FAVORABLE"**
- Score < 4: Filtered out

### Dedup Logic

After all 4 passes complete:
1. Collect all candidates across all stats.
2. If a player appears in multiple stats, keep only the entry with the highest score.
3. On tie, priority: PTS > 3PT > AST > REB.
4. Top 5 candidates per stat (max 1 per game within each stat).

## Pipeline Execution Flow

```
1. get_todays_games()                         (NBA API — unchanged)
2. get_projected_lineups()                    (RotoWire — unchanged)
3. get_defense_vs_position()                  (FantasyPros — PTS only)
4. get_team_defense_vs_position()             (NEW — NBA API, all teams, AST/REB/3PT)
5. For each game with injured starter:
   a. Identify candidates (bench, position compatible)
   b. Fetch extended recent stats (NBA API)
   c. Run 4 scoring passes: PTS, AST, REB, 3PT
6. Dedup — player stays in best stat only
7. Top 5 per stat (max 1 per game per stat)
8. get_player_lines()                         (Odds API — PTS + AST + REB + 3PT)
9. Save to Firestore
10. Notify Telegram
```

## Firestore Structure

**Collection:** `analyses/{date_str}`

```json
{
  "date": "2026-03-23",
  "ran_at": "2026-03-23T10:30:45.123456+00:00",
  "triggered_by": "scheduler",
  "game_count": 10,
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
          "dvp": 2,
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
- `candidate_count` removed (derivable from stats arrays).

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

History entries updated to show stats breakdown instead of flat list. Each historical entry shows player chips grouped by stat.

## Files Affected

| File | Change |
|------|--------|
| `scrapers/nba.py` | Add `get_team_defense_vs_position()`, extend `get_player_recent_stats()` |
| `scrapers/odds.py` | Extend `get_player_lines()` for 4 markets |
| `analysis/engine.py` | Add 3 new scoring functions, dedup logic, refactor `run_analysis()` |
| `scheduler.py` | Update Firestore save format, pass new data to engine |
| `app.py` | Update status/result serialization for new structure |
| `scrapers/telegram.py` | New 4-section message format |
| `static/analise.js` | Render 4 sections, update card template, update history |
| `static/index.html` | Section containers for 4 stats |
| `output/formatter.py` | Update plain text format |
| `routers/analyses.py` | Handle new Firestore structure in history endpoint |
| `tests/test_engine.py` | Tests for new scoring functions, dedup logic |

## Rate Limiting Considerations

- NBA API defensive stats: 1 call per analysis run (all teams at once), not per player.
- Player stats: Already rate-limited at 1s delay. Extended stats add no extra calls (same endpoint, more fields).
- Odds API: 1 extra market per event (4 markets vs 1). Check quota usage.
- FantasyPros: Unchanged (1 call per run for PTS DvP).
