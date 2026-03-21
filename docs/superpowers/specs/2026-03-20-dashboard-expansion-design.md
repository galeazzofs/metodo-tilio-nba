# Dashboard Expansion Design

**Date:** 2026-03-20
**Status:** Approved

## Overview

Expand the existing Painel (Dashboard) tab with advanced betting analytics and create a new NBA tab with engine performance data, live NBA info, and engine-to-bets correlation.

## Scope

Two workstreams:
1. **Painel de Apostas (existing tab)** — add risk management KPIs, pattern analysis charts, and distribution/comparison charts
2. **Nova Aba NBA (new tab)** — engine scorecard, live NBA data, and engine x bets correlation

---

## Page 1: Painel de Apostas (Expanded)

### Section 1: KPI Cards Expandidos

**Existing cards (row 1):** Lucro Total, Win Rate, ROI, Odds Médias — unchanged.

**New cards (row 2):**

| Card | Description | Calculation |
|------|-------------|-------------|
| Max Drawdown | Largest peak-to-valley drop in cumulative P&L | Max difference between a peak and its subsequent valley |
| Longest Win Streak | Longest consecutive winning bets | Sequential count of `resultado === "ganhou"` |
| Longest Loss Streak | Longest consecutive losing bets | Sequential count of `resultado === "perdeu"` |
| Profit Factor | Ratio of gross wins to gross losses | `sum(profits) / abs(sum(losses))` — above 1.0 = profitable |

Each new card follows the existing visual style: comparison badge vs last 30 days, green/red coloring based on positive/negative.

**Layout:** 4 cards row 1 + 4 cards row 2. Mobile: 2 per row.

### Section 2: Análise de Padrões

Three new charts below the KPI cards.

**1. Performance por Dia da Semana (bar chart)**
- X axis: Mon, Tue, Wed, Thu, Fri, Sat, Sun
- Y axis: Cumulative profit/loss per day
- Green/red bars based on positive/negative
- Tooltip: total staked, bet count, win rate for that day

**2. Performance por Faixa de Odds (grouped bar chart)**
- Ranges: 1.00-1.50, 1.51-1.80, 1.81-2.20, 2.21-3.00, 3.01+
- Each range shows: bet count, win rate, total profit
- Identifies which odds ranges are most profitable

**3. Hot/Cold Streaks (timeline visual)**
- Horizontal timeline with colored markers
- Each bet: green (win), red (loss), gray (void)
- Consecutive streaks highlighted with colored background
- Shows last 50 bets to keep it clean

**Layout:** Two bar charts side by side on desktop, timeline full width below. All stacked vertically on mobile.

### Section 3: Distribuições e Comparações

Three final charts to close out the betting dashboard.

**1. Histograma de Odds (bar chart)**
- Frequency distribution of odds across all bets
- Bins of 0.10 (e.g., 1.50-1.60, 1.60-1.70...)
- Reveals betting selection bias

**2. Scatter Plot: Odds vs Resultado (scatter)**
- X axis: bet odds
- Y axis: profit/loss for that bet
- Green dots (win), red dots (loss)
- Reference line at Y=0
- Shows if high odds compensate risk or if profit comes from low odds

**3. Evolução do ROI ao Longo do Tempo (line chart)**
- X axis: dates
- Y axis: cumulative ROI (%)
- Main line: user's actual ROI
- Dashed reference line: ROI with flat betting (constant stake)
- Shows whether stake management adds value vs always betting the same

**Layout:** Histogram and scatter side by side, ROI evolution full width below.

---

## Page 2: Nova Aba NBA

New 4th tab in the navigation menu: Análise | Apostas | Painel | **NBA**

### Section 4: Engine Scorecard

**KPI Cards (row of 4):**

| Card | Description | Calculation |
|------|-------------|-------------|
| Accuracy Geral | % of picks that hit | `correct picks / total picks with result` |
| Accuracy BEST OF NIGHT | % accuracy for top tier (score >= 6) | Filtered by score >= 6 |
| Accuracy VERY FAVORABLE | % accuracy for secondary tier (score 4-5) | Filtered by score 4-5 |
| Total de Picks | Total recommendations made | Count of all analyses with result |

**Trend de Accuracy (line chart)**
- X axis: time
- Y axis: accuracy %
- 3 lines: overall, BEST OF NIGHT, VERY FAVORABLE
- Filters: last 30 / 60 / 90 days / all-time
- Tracks if the engine is improving or declining over time

**Accuracy por Signal (bar chart)**
- Bar for each engine signal: DvP Matchup, Recent Form, Zone Match
- Shows which signal is most predictive
- Helps understand engine strengths and weaknesses

**Layout:** 4 cards top, trend chart full width, signal chart below.

### Section 5: Dados ao Vivo

**1. Standings Resumidos (two compact tables)**
- East and West tables side by side
- Columns: Position, Team, W-L, %, GB
- Visual divider between playoff (1-6), play-in (7-10), eliminated (11-15)
- Amber highlight on teams playing today

**2. Jogos do Dia (game cards)**
- Card per game showing:
  - Away vs Home with abbreviations
  - Stake tag: "PLAYOFF", "PLAY-IN", or "LOW STAKE" (from `filter_games_by_stake`)
  - Confirmed out players (from RotoWire injury report)
  - If engine generated a pick for this game, badge with player name and tier
- High stake games sorted to top
- "No games today" message when empty

**3. DvP Rankings Snapshot (compact table)**
- Top 5 worst defenses by position (PG, SG, SF, PF, C)
- Data from FantasyPros scraper (already available)
- Shows most vulnerable teams by position right now

**Layout:** Standings side by side top, game cards grid middle, DvP table full width bottom.

### Section 6: Correlação Engine x Apostas

**KPI Cards (row of 3):**

| Card | Description |
|------|-------------|
| ROI Seguindo o Engine | ROI of bets matching engine picks |
| ROI Não Seguindo | ROI of bets without engine picks |
| Diferença | Delta between the two — shows engine's added value |

Match logic: cross-reference bet `data` + `partida` with analysis from the same date. If the bet was on a player the engine recommended, it counts as "followed."

**Lucro Acumulado Comparativo (line chart, 2 lines)**
- Line 1 (amber): cumulative P&L of bets that followed the engine
- Line 2 (gray): cumulative P&L of bets without engine recommendation
- Visually shows if following the engine yields superior results

**Performance por Score do Engine (bar chart)**
- X axis: engine pick score (4, 5, 6)
- Y axis: win rate of bets made at that score
- Validates if higher scores truly predict better outcomes
- Helps decide whether to bet only on score 6 or if 4-5 also pays off

**Layout:** 3 cards top, comparative line chart full width, score bar chart below.

---

## Data Sources

| Data | Source | Endpoint/Collection |
|------|--------|-------------------|
| Bets | Firestore | `users/{uid}/bets/` via `/api/bets` |
| Analyses + results | Firestore | `analyses/{date}` via `/api/analyses` |
| Standings | NBA Stats API | `scrapers/nba.py` → `get_conference_standings()` |
| Today's games | NBA Stats API | `scrapers/nba.py` → `get_todays_games()` |
| Lineups/injuries | RotoWire | `scrapers/rotowire.py` → `get_projected_lineups()` |
| DvP rankings | FantasyPros | `scrapers/fantasypros.py` |
| Stake filter | Analysis engine | `analysis/engine.py` → `filter_games_by_stake()` |

## Technical Notes

- All charts use Chart.js (already in project)
- All calculations are client-side from existing API data (no new backend endpoints needed for betting metrics)
- NBA tab will need a new API endpoint or use existing `/api/analyses` + scraper endpoints
- Follow existing "Midnight Court" design system (amber primary, cyan secondary, green/red for positive/negative)
- All new sections respect existing time period filters (week/month/year/all) where applicable
- Mobile responsive: cards 2-per-row, charts stack vertically

## Navigation Change

Add 4th tab to the nav menu:
- Current: `ANALISE | APOSTAS | PAINEL`
- New: `ANALISE | APOSTAS | PAINEL | NBA`

New tab uses the same nav component and styling as existing tabs.
