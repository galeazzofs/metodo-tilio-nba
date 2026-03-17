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
- If the key is missing at import time, raise a clear `RuntimeError` — no silent failures.
- Base URL: `https://api.the-odds-api.com/v4`
- Region: `eu`
- Market: `player_points`

### Function: `get_event_ids(games) → dict`

Calls `GET /v4/sports/basketball_nba/events?apiKey=...&regions=eu`.

Returns a mapping of `(away_tricode, home_tricode) → event_id` by matching API team names against the tricodes already in memory. Matching is done by fuzzy substring on team names (case-insensitive).

### Function: `get_player_lines(candidates, event_ids) → dict`

For each unique game among the candidates:
1. Looks up the `event_id` from `event_ids`.
2. Calls `GET /v4/sports/basketball_nba/events/{event_id}/odds?apiKey=...&regions=eu&markets=player_points`.
3. Iterates bookmaker responses; for each bookmaker, finds the `player_points` market and the outcome matching the candidate's name (case-insensitive substring match).
4. Collects all `point` values across bookmakers for that player.
5. Computes the **mode** of those values; if no mode (all unique), uses the **median**.

Returns `{player_name: line_value}` where `line_value` is a float (e.g. `14.5`).

### Error handling

- HTTP errors or timeouts → log a warning, return empty dict. Output still renders, all lines show as `N/A`.
- Player name not found in any bookmaker prop → `line` is `None`, formatted as `N/A`.
- Quota exhausted (HTTP 429) → same as above, with a specific warning message.

---

## Changes: `main.py`

After `run_analysis()`, before `format_results()`:

```python
print("Fetching betting lines (The Odds API)...")
event_ids = get_event_ids(games)
lines = get_player_lines(candidates, event_ids)
for c in candidates:
    c["line"] = lines.get(c["player"])
```

Import added: `from scrapers.odds import get_event_ids, get_player_lines`

---

## Changes: `output/formatter.py`

One new line per player block, immediately after the rating line:

```
  #1 Cason Wallace (SG) - Thunder
      *** BEST OF THE NIGHT
      Line: 14.5 pts
      - Elite matchup vs Grizzlies (DvP #3, 26.1 pts/g allowed)
      Stats (last 15g): 16.2 pts | 3.1 reb | 4.0 ast | 29.4 min
```

If `line` is `None`: shows `Line: N/A`.

---

## Dependencies

- `python-dotenv` — for `.env` key loading (likely already available; add if not)
- `requests` — already used in `scrapers/fantasypros.py`
- No new scraping library needed (The Odds API is a clean REST JSON API)

---

## API Usage Estimate

- Max 5 candidates → max 5 unique games → max 5 + 1 API calls per run (1 for events list, up to 5 for player props).
- Daily use during NBA season (~170 game days) × 6 calls = ~1,020 calls/season.
- Free tier: 500 requests/month. Paid tiers start at $79/month for 30,000 requests.
- **Recommendation:** start on free tier and monitor quota via the `x-requests-remaining` response header, which the module should log.

---

## Out of Scope

- Odds/juice values (e.g. `-110`) — not shown, only the line number.
- Multiple lines per player (e.g. alternate lines) — only the consensus standard line.
- Saving or caching lines between runs.
