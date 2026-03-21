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
- Each bet: green (win), red (loss), gray (void/push)
- Pending bets (`resultado === "pendente"`) are excluded from the timeline
- Consecutive streaks highlighted with colored background
- Shows last 50 resolved bets to keep it clean

**Layout:** Two bar charts side by side on desktop, timeline full width below. All stacked vertically on mobile.

### Section 3: Distribuições e Comparações

Three final charts to close out the betting dashboard.

**1. Histograma de Odds (bar chart)**
- Frequency distribution of odds across all bets
- Uses the same ranges as the Faixa de Odds chart for consistency: 1.00-1.50, 1.51-1.80, 1.81-2.20, 2.21-3.00, 3.01+
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
- Dashed reference line: ROI with flat betting using the user's median stake as the constant value
- Shows whether stake management adds value vs always betting the same

**Layout:** Histogram and scatter side by side, ROI evolution full width below.

---

## Page 2: Nova Aba NBA

New 4th tab in the navigation menu: ANÁLISE | **NBA** | APOSTAS | PAINEL

NBA tab placed adjacent to ANÁLISE since both are conceptually related (engine analysis).

### Section 4: Engine Scorecard

#### Outcome Tracking

Each analysis result in Firestore needs an `outcome` field to track whether the pick was correct. This requires:

- **New field:** `outcome: "hit" | "miss" | null` on each result entry in `analyses/{date}`
- **Definition of "hit":** The recommended player exceeded the betting line (points prop) that was fetched from The Odds API at analysis time. The line value is already stored in the analysis result.
- **Backend job:** A new daily job runs the morning after game day, fetches actual player stats from the NBA Stats API, compares against the stored line, and writes `outcome` back to Firestore.
- **New endpoint:** `POST /api/analyses/{date}/resolve` — manually trigger outcome resolution for a specific date (useful for backfilling).

Until outcome data exists, the Engine Scorecard section shows an empty state: "Dados de accuracy serão exibidos após os primeiros resultados serem processados."

**KPI Cards (row of 4):**

| Card | Description | Calculation |
|------|-------------|-------------|
| Accuracy Geral | % of picks that hit | `picks with outcome="hit" / total picks with non-null outcome` |
| Accuracy BEST OF NIGHT | % accuracy for top tier (score >= 6) | Filtered by score >= 6, same outcome logic |
| Accuracy VERY FAVORABLE | % accuracy for secondary tier (score 4-5) | Filtered by score 4-5, same outcome logic |
| Total de Picks | Total recommendations made | Count of all analyses with non-null outcome |

**Trend de Accuracy (line chart)**
- X axis: time
- Y axis: accuracy %
- 3 lines: overall, BEST OF NIGHT, VERY FAVORABLE
- Filters: last 30 / 60 / 90 days / all-time
- Tracks if the engine is improving or declining over time

**Accuracy por Score (bar chart)**
- Bar for each score value: 4, 5, 6
- Shows hit rate per score level
- Validates whether higher engine scores correlate with better outcomes
- (Note: DvP Matchup and Zone Match are hard gates in the engine — all picks have them. Only score level varies meaningfully between picks.)

**Layout:** 4 cards top, trend chart full width, score accuracy chart below.

### Section 5: Dados ao Vivo

**1. Standings Resumidos (two compact tables)**
- East and West tables side by side
- Columns: Position, Team, W-L, %, GB
- Visual divider between playoff (1-6), play-in (7-10), outside play-in (11-15)
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

**Match logic:**
1. Match bet to analysis by date: bet `data` field → `analyses/{date}` document
2. Match bet to game: normalize bet `partida` field by extracting team tricodes (e.g., "Lakers vs Celtics" → ["LAL", "BOS"]) and compare against analysis result `game` field (e.g., "BOS @ LAL"). Use a tricode lookup map (full name → tricode).
3. Match bet to player: check if any word in bet `descricao` matches analysis result `player` name (case-insensitive substring match on last name).
4. If all 3 match → bet "followed" the engine. If match fails at any step → "not followed."
5. Ambiguous matches (e.g., multiple engine picks in the same game) are excluded from correlation stats and logged for manual review.

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

## New API Endpoints

The NBA tab requires new backend routes since the scrapers are server-side Python functions with no HTTP endpoints:

| Endpoint | Method | Purpose | Source Function | Caching |
|----------|--------|---------|-----------------|---------|
| `GET /api/nba/standings` | GET | Conference standings | `scrapers/nba.py → get_conference_standings()` | 1 hour TTL in-memory |
| `GET /api/nba/today` | GET | Today's games + stake tags + injuries | `scrapers/nba.py → get_todays_games()` + `engine.py → filter_games_by_stake()` + `scrapers/rotowire.py → get_projected_lineups()` | 30 min TTL in-memory |
| `GET /api/nba/dvp` | GET | DvP rankings snapshot | `scrapers/fantasypros.py` | 1 hour TTL in-memory |
| `POST /api/analyses/{date}/resolve` | POST | Resolve pick outcomes for a date | New function: fetch actual stats from NBA API, compare vs stored lines | No cache |

Caching is in-memory (simple dict with TTL) to avoid hammering external APIs on every page load. Cache is invalidated when a new analysis run completes.

## Technical Notes

- All charts use Chart.js (already in project)
- All Painel (betting) calculations are client-side from existing `/api/bets` data (no new backend endpoints needed)
- NBA tab uses the new API endpoints above
- Follow existing "Midnight Court" design system (amber primary, cyan secondary, green/red for positive/negative)
- All new sections respect existing time period filters (week/month/year/all) where applicable
- Mobile responsive: cards 2-per-row, charts stack vertically

## Empty States

Each section must handle empty/missing data gracefully:

| Section | Condition | Message |
|---------|-----------|---------|
| KPI Cards (Painel) | No resolved bets | "Registre suas primeiras apostas para ver as estatísticas" |
| Pattern Analysis | Fewer than 7 resolved bets | "Aposte mais para ver padrões por dia da semana" |
| Engine Scorecard | No outcome data resolved yet | "Dados de accuracy serão exibidos após os primeiros resultados serem processados" |
| Jogos do Dia | No games scheduled | "Sem jogos hoje" |
| DvP Rankings | Scraper fails or no data | "Dados DvP indisponíveis no momento" |
| Correlation | No bets match any engine picks | "Nenhuma aposta correspondente a picks do engine encontrada" |
| Standings | Scraper fails | "Standings indisponíveis no momento" |

## Navigation Change

Reorder nav to group related tabs:
- Current: `ANÁLISE | APOSTAS | PAINEL`
- New: `ANÁLISE | NBA | APOSTAS | PAINEL`

NBA tab placed next to ANÁLISE since both relate to engine/analysis data. New tab uses the same nav component and styling as existing tabs.
