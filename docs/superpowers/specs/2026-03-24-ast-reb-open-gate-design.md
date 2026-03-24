# AST/REB Open Gate Design

**Date:** 2026-03-24
**Status:** Approved

## Problem

AST and REB analysis currently requires a starter to be injured and only evaluates bench players stepping up. This limits the pool to very few candidates — on many game nights, zero players qualify. AST and REB matchup opportunities exist independent of injuries.

## Change Summary

Remove the starter injury gate for AST and REB only. PTS and 3PT keep the existing gate. Compensate with stricter scoring threshold (5 instead of 4) and a pace gate that filters out slow-paced games.

## Player Universe (AST/REB only)

For each game today, analyze:

1. **Projected starters** from RotoWire lineup
2. **Bench players** with **>= 20 min/g** season average

This applies to ALL games, regardless of injury status. PTS and 3PT continue to require the injury gate.

## Pace Gate (AST/REB only)

Before scoring any player for AST or REB, check the pace of both teams in the game:

1. Fetch pace for all 30 teams (NBA API `leaguedashteamstats` with pace stat)
2. Calculate the **league median** pace
3. For each game, check both teams' pace against the median:
   - **At least one team above median** → game passes, proceed to scoring
   - **Both teams below median** → game blocked for AST/REB analysis (too slow-paced)

This gate does NOT award points. It only filters out games where both teams play slow, reducing opportunities for assists and rebounds.

PTS and 3PT are NOT affected by this gate.

## Scoring — AST

No gates. All signals are pure scoring.

| Signal | Criteria | Points |
|--------|----------|--------|
| DvP | AST allowed to position — rank 1-2: 3pts, rank 3-6: 2pts, 7+: 0 | 0-3 |
| Recent form | AST avg last 15g >= season avg | 0-1 |
| Potential AST | Potential AST allowed to position — rank 1-2: 2pts, rank 3-6: 1pt (NOTE: max is 2, not 3), 7+: 0 | 0-2 |

**Max score:** 6

## Scoring — REB

No gates. All signals are pure scoring.

| Signal | Criteria | Points |
|--------|----------|--------|
| DvP | REB allowed to position — rank 1-2: 3pts, rank 3-6: 2pts, 7+: 0 | 0-3 |
| Recent form | REB avg last 15g >= season avg | 0-1 |
| REB opportunity | REB opportunities allowed to position — rank 1-2: 2pts, rank 3-6: 1pt (NOTE: max is 2, not 3), 7+: 0 | 0-2 |

**Max score:** 6

## Threshold and Rating (AST/REB)

- Score >= 6: "BEST OF THE NIGHT"
- Score 5: "VERY FAVORABLE"
- Score < 5: Filtered out

This is stricter than PTS/3PT (threshold 4).

## Unchanged

- **PTS scoring:** Keeps injury gate, FantasyPros DvP, threshold 4
- **3PT scoring:** Keeps injury gate, NBA API DvP, threshold 4
- **Dedup:** Player appears only in best stat. Tie-break: PTS > 3PT > AST > REB
- **UI:** 4 sections unchanged
- **Firestore structure:** Unchanged
- **Telegram format:** Unchanged
- **Odds API:** Unchanged

## Engine Flow Change

Current flow for AST/REB:
```
for each game with injured starter → for each projected starter (bench only) → score AST/REB
```

New flow:
```
for each game:
  1. Check pace gate (both teams' pace vs league median)
     - If both below median → skip game for AST/REB
  2. For each projected starter + bench >= 20min/g → score AST/REB
```

PTS and 3PT keep the old flow (injury gate).

## Graduated Rank Scoring Reference

Used by both DvP and Potential/Opportunity signals for AST and REB:

| Rank | DvP points (max 3) | Potential/Opportunity points (max 2) |
|------|-------------------|--------------------------------------|
| 1-2  | 3                 | 2                                    |
| 3-6  | 2                 | 1                                    |
| 7+   | 0                 | 0                                    |
