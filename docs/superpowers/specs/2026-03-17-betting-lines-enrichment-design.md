# Betting Lines Enrichment — Design Spec

**Date:** 2026-03-17
**Status:** Approved

---

## Overview

After the analysis engine produces its top 5 candidates, fetch the points over/under betting line for each player from The Odds API (EU region) and include it in the formatted output. The goal is to show the exact consensus line next to each player so users know what number to bet over.

---

## Architecture

No existing modules are restructured. One new file is added (`scrapers/odds.py`), and two existing files receive small additions (`main.py`, `output/formatter.py`).

**Data flow:**

```
main.py
  ├── get_todays_games()         → list of today's games
  ├── get_projected_lineups()    → projected lineups per team
  ├── get_defense_vs_position()  → DvP rankings
  ├── run_analysis()             → top 5 candidates (list of dicts)
  ├── enrich_with_lines()        → adds 'line' key to each candidate dict
  └── format_results()           → formatted output string (now includes line)
```

---

## New Module: `scrapers/odds.py`

### Configuration

- API key stored in `.env` as `ODDS_API_KEY`, loaded with `python-dotenv`.
- If the key is missing, raise a `RuntimeError` at **call time** (inside `get_event_ids`), not at import time. This preserves the existing pipeline behaviour for users who have not yet configured the key.
- Base URL: `https://api.the-odds-api.com/v4`
- Region: `eu`
- Market: `player_points`
- All HTTP calls use `timeout=10`.

### Static tricode-to-API-name lookup

The Odds API returns full city+name strings (e.g. `"Oklahoma City Thunder"`). The games list from `get_todays_games()` carries `teamName` fragments without city (e.g. `"Thunder"`). Substring matching is ambiguous for LA teams (`"Los Angeles Lakers"` and `"Los Angeles Clippers"` both contain `"Los Angeles"`).

Use a static lookup table inside `scrapers/odds.py` mapping tricode → the exact team name string The Odds API uses:

```python
TRICODE_TO_API_NAME = {
    "ATL": "Atlanta Hawks",
    "BOS": "Boston Celtics",
    "BKN": "Brooklyn Nets",
    "CHA": "Charlotte Hornets",
    "CHI": "Chicago Bulls",
    "CLE": "Cleveland Cavaliers",
    "DAL": "Dallas Mavericks",
    "DEN": "Denver Nuggets",
    "DET": "Detroit Pistons",
    "GSW": "Golden State Warriors",
    "HOU": "Houston Rockets",
    "IND": "Indiana Pacers",
    "LAC": "Los Angeles Clippers",
    "LAL": "Los Angeles Lakers",
    "MEM": "Memphis Grizzlies",
    "MIA": "Miami Heat",
    "MIL": "Milwaukee Bucks",
    "MIN": "Minnesota Timberwolves",
    "NOP": "New Orleans Pelicans",
    "NYK": "New York Knicks",
    "OKC": "Oklahoma City Thunder",
    "ORL": "Orlando Magic",
    "PHI": "Philadelphia 76ers",
    "PHX": "Phoenix Suns",
    "POR": "Portland Trail Blazers",
    "SAC": "Sacramento Kings",
    "SAS": "San Antonio Spurs",
    "TOR": "Toronto Raptors",
    "UTA": "Utah Jazz",
    "WAS": "Washington Wizards",
}
```

### Function: `get_event_ids(games) → dict`

- Input: the `games` list returned by `get_todays_games()`. Each element has `away_tricode` and `home_tricode`.
- Calls `GET /v4/sports/basketball_nba/events?apiKey=...&regions=eu` with `timeout=10`.
- Logs the `x-requests-remaining` response header: `print(f"  [odds] requests remaining: {resp.headers.get('x-requests-remaining', 'unknown')}")`.
- Matches each API event to a game by comparing `TRICODE_TO_API_NAME[away_tricode]` and `TRICODE_TO_API_NAME[home_tricode]` against the API's `away_team` and `home_team` fields (exact string match after lookup).
- Returns `{(away_tricode, home_tricode): event_id}`.
- If the HTTP call fails or returns an error status, logs a warning and returns `{}`. This is a non-error expected path when lines are unavailable; all candidates will show `Line: N/A`.

### Function: `get_player_lines(candidates, event_ids) → dict`

- Input: `candidates` list (each has `"game"` key like `"BOS @ LAL"`, `"player"` key) and `event_ids` dict from `get_event_ids`.
- Deduplication: groups candidates by `c["game"]`. The game string `"BOS @ LAL"` is split on `" @ "` to get `(away_tricode, home_tricode)` = `("BOS", "LAL")`, which is used as the lookup key into `event_ids`.
- For each unique game, calls `GET /v4/sports/basketball_nba/events/{event_id}/odds` with query params `apiKey`, `regions=eu`, `markets=player_points` and `requests.get(..., timeout=10)`.
- Iterates bookmaker responses. For each bookmaker, finds the `player_points` market and the outcome whose `description` contains the candidate's name (case-insensitive substring match).
- Collects all `point` values (floats) across bookmakers for that player.
- Computes consensus line:
  - Use `statistics.multimode(values)` to get the most-common value(s) — it always returns a list.
  - If `len(modes) == 1`, use `modes[0]` (do not rely on truthiness alone).
  - If `len(modes) > 1` (tie), use `statistics.median(values)` of the full list.
- Returns `{player_name: line_value}` where `line_value` is a float (e.g. `14.5`).

---

## Changes: `main.py`

After `run_analysis()`, before `format_results()`:

```python
from scrapers.odds import get_event_ids, get_player_lines

print("Fetching betting lines (The Odds API)...")
event_ids = get_event_ids(games)
lines = get_player_lines(candidates, event_ids)
for c in candidates:
    c["line"] = lines.get(c["player"])
```

---

## Changes: `output/formatter.py`

Insert the `Line:` line immediately after `lines.append(f"      {icon} {p['rating']}")` and before the signals loop:

```python
line_str = f"{p['line']} pts" if p.get("line") is not None else "N/A"
lines.append(f"      Line: {line_str}")
```

This produces:

```
  #1 Cason Wallace (SG) - Thunder
      *** BEST OF THE NIGHT
      Line: 14.5 pts
      - Elite matchup vs Grizzlies (DvP #3, 26.1 pts/g allowed)
      Stats (last 15g): 16.2 pts | 3.1 reb | 4.0 ast | 29.4 min
```

---

## Dependencies

- `python-dotenv` — add to `requirements.txt` (not currently present).
- `requests` — already used in `scrapers/fantasypros.py`, no change needed.

---

## API Usage Estimate

- Max 6 API calls per run: 1 for the events list + up to 5 for player props (one per unique game in the top 5).
- At daily use: ~6 calls/day × 30 days = ~180 calls/month — well within the 500 requests/month free tier.
- Log `x-requests-remaining` from the `get_event_ids` response so usage can be monitored without logging into the dashboard.

---

## Error Handling Summary

| Scenario | Behaviour |
|----------|-----------|
| `ODDS_API_KEY` missing | `RuntimeError` raised at call time in `get_event_ids` |
| HTTP error or timeout | Warning logged, `{}` returned, all lines show `N/A` |
| HTTP 429 quota exceeded | Log `print("[odds] quota exceeded — HTTP 429")`, return `{}` |
| Player name not found in props | `line` is `None`, formatted as `N/A` |
| `get_event_ids` returns `{}` (zero matches) | `get_player_lines` returns `{}` silently — not a bug, just no data |

---

## Out of Scope

- Odds/juice values (e.g. `-110`) — not shown, only the line number.
- Multiple lines per player (e.g. alternate lines) — only the consensus standard line.
- Saving or caching lines between runs.
