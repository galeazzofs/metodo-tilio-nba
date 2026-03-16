# Design Spec: Bet Tracker + Auth — NBA Tonight
**Date:** 2026-03-15
**Status:** Approved
**Language:** PT-BR (toda a interface em português do Brasil)

---

## Overview

Extend the existing NBA Tonight FastAPI app with:
1. Firebase Authentication (sign up / sign in)
2. Per-user bet tracking (Firestore)
3. bet365 CSV import
4. Dashboard with performance metrics
5. Full PT-BR UI

Everything lives inside the same app and Render deployment. No new servers or repos.

---

## Architecture

```
Browser (Firebase JS SDK)
    │
    ├── Firebase Auth  ←→  Firebase (hosted by Google, free tier)
    │       │
    │       └── ID Token (JWT) sent with every /api/bets/* request
    │
    └── FastAPI (app.py)
            │
            ├── /api/run, /api/status, /api/reset  ← existing routes (remain public)
            ├── /api/bets/*                         ← new routes (token-protected)
            └── Firestore SDK (Python)              ← per-user bet storage
```

### Why Firebase?
- Auth + Firestore are free within generous limits (10K users/month, 1GB storage, 50K reads/day)
- Firebase JS SDK handles all auth UI state in the browser — no session management on the server
- ID tokens verified server-side via `firebase-admin` Python SDK

### Route Protection Policy
- **Existing routes** (`/api/run`, `/api/status`, `/api/reset`) remain **public** — no token required. The analysis tool continues to work as before.
- **All `/api/bets/*` routes** require a valid Firebase ID token in the `Authorization: Bearer <token>` header.

---

## Authentication

### Sign Up / Sign In Page
- Shown to unauthenticated users before any other content
- Fields: email, password (+ confirm password on sign up)
- Toggle between "Entrar" and "Criar conta"
- Error messages in PT-BR (e.g. "Email ou senha inválidos", "Email já cadastrado")
- On success: user directed to main app
- Dark theme matching existing design (orange accent, glassmorphism cards)

### Firebase Auth Persistence
Use `firebase.auth.browserSessionPersistence` — session is preserved across page refreshes within the same browser tab but cleared when the tab/browser is closed. Set via:
```js
await firebase.auth().setPersistence(firebase.auth.Auth.Persistence.SESSION);
```

### Token Flow
1. User signs in → Firebase JS SDK returns ID token
2. Token attached as `Authorization: Bearer <token>` header on all `/api/bets/*` requests
3. FastAPI dependency calls `firebase_admin.auth.verify_id_token(token)` on each protected request
4. If invalid/expired → 401 returned, frontend redirects to sign in page
5. Token auto-refreshed by Firebase JS SDK (tokens expire every 1 hour; SDK refreshes silently)

### Sign Out
- "Sair" button visible in header when logged in
- Calls `firebase.auth().signOut()`, clears session, returns to sign in page

---

## Navigation

Three tabs in the header (replaces current single-page layout):

| Tab | PT-BR Label | Description |
|-----|------------|-------------|
| Analysis | **Análise** | Existing NBA Tonight analysis (unchanged logic) |
| My Bets | **Minhas Apostas** | Bet history table + import |
| Dashboard | **Painel** | Performance metrics + charts |

Active tab highlighted in orange. Tab state preserved in URL hash (`#analise`, `#apostas`, `#painel`).

### Frontend Refactor Note
The existing `static/index.html` is a monolithic single-file app. As part of this work, the existing inline JS will be extracted to `analise.js`. The `index.html` becomes the shared shell containing: auth gate, tab navigation, and `<script>` tags for all JS modules. Existing behaviour of the Análise tab is unchanged.

---

## Data Model (Firestore)

Collection: `users/{uid}/bets/{bet_id}`

```json
{
  "bet_id": "uuid-v4",
  "uid": "firebase-user-id",
  "data": "2026-03-14",
  "partida": "Lakers vs Celtics",
  "tipo_aposta": "Vencedor | Handicap | Totais | Jogador | Outro",
  "descricao": "LeBron James — Mais de 25.5 pontos",
  "odds": 1.85,
  "stake": 50.00,
  "resultado": "ganhou | perdeu | pendente | void",
  "lucro_prejuizo": 42.50,
  "importado_de": "bet365_csv | manual",
  "criado_em": "2026-03-14T22:00:00Z"
}
```

### `lucro_prejuizo` — Storage Rule
Calculated and **stored on every write**. The stored value is always authoritative. Rules by source:

- **CSV import:** use `Retorno - Valor` from the bet365 export directly (preserves bonuses/promotions). If `resultado == "pendente"`, set `lucro_prejuizo = null` and ignore `Retorno`.
- **Manual entry (POST) and updates (PUT):** compute from formula: Won=`round((odds-1)*stake, 2)`, Lost=`round(-stake, 2)`, Void=`0.0`, Pending=`null`. Recalculate and overwrite on every PUT.

### `bet_id` in Document
`bet_id` is stored both as the Firestore document ID and as a field inside the document. This duplication is intentional — it makes the frontend easier to work with (no need to separately track document IDs from query snapshots).

---

## Bet365 CSV Import

### User Flow
1. User goes to bet365 → Minha Conta → Extrato → Exportar (selects date range)
2. In the app, clicks "Importar do bet365" on the Minhas Apostas tab
3. File picker opens, user selects the `.csv` file
4. Frontend sends file to `POST /api/bets/import`
5. Backend parses CSV, maps columns, deduplicates, saves to Firestore
6. Returns `{ "importadas": N, "ignoradas": M, "erros": [...] }`

### CSV Column Mapping
> **Note:** Column names below were validated against a real bet365 PT-BR account export. If the export format changes, the parser must be updated.

| CSV Column | Maps To | Notes |
|-----------|---------|-------|
| `Data de Liquidação` | `data` | Normalized to ISO 8601 (`YYYY-MM-DD`) |
| `Descrição` | `descricao` + `partida` | See parsing rule below |
| `Tipo` | `tipo_aposta` | Mapped to PT-BR enum values |
| `Odds` | `odds` | Cast to float |
| `Valor` | `stake` | Cast to float |
| `Retorno` | `lucro_prejuizo` | `Retorno - Valor = net profit`; stored as signed float |
| `Status` | `resultado` | "Ganhou"→"ganhou", "Perdeu"→"perdeu", "Aberta"→"pendente", "Anulada"→"void" |

### `Descrição` Parsing Rule
The full `Descrição` value is stored in `descricao`. `partida` is extracted as the substring before the first ` - ` separator if present; otherwise `partida` equals the full `descricao`. Example:
- `"Lakers vs Celtics - LeBron James Mais de 25.5"` → `partida = "Lakers vs Celtics"`, `descricao = "Lakers vs Celtics - LeBron James Mais de 25.5"`

### Deduplication
Before saving each row, check whether a bet with the same `(data, descricao, odds, stake)` tuple already exists in the user's collection. Dates are compared after normalizing both to ISO 8601. Re-importing the same CSV export is a no-op (0 new bets imported). Duplicates are counted in `"ignoradas"`.

### Open Bets
If `Status == "Aberta"`, set `resultado = "pendente"` and `lucro_prejuizo = null`. Skip the `Retorno` column entirely for these rows.

### Parsing Errors
Invalid rows (e.g. non-numeric odds) are skipped and their error message added to `"erros"`. Valid rows are saved. Import is **partial** (not atomic) — save what is valid, skip what is not.

### Response Format
```json
{ "importadas": 12, "ignoradas": 3, "erros": ["Linha 5: odds inválidas"] }
```

---

## Minhas Apostas Tab

### Bet Table
Columns: Data | Partida | Descrição | Odds | Stake | Resultado | L/P

- Resultado shown as colored badge: 🟢 Ganhou / 🔴 Perdeu / 🟡 Pendente / ⚪ Void
- L/P (lucro/prejuízo) shown in green for positive, red for negative
- Sorted by date descending by default
- Filtering is **client-side** in v1 (all bets fetched, filtered in browser). Acceptable given expected volume (<5,000 bets).

### Empty State
When user has zero bets: show centered message "Nenhuma aposta registrada ainda. Importe do bet365 ou adicione manualmente."

### Filters
- Date range (De / Até)
- Resultado (Todos / Ganhou / Perdeu / Pendente / Void)
- Text search on Partida + Descrição

### Manual Entry Form (slide-in panel)
Fields:
- **Partida** (text, e.g. "Lakers vs Celtics")
- **Descrição** (text, e.g. "LeBron James — Mais de 25.5 pontos")
- **Tipo** (select: Vencedor / Handicap / Totais / Jogador / Outro)
- **Odds** (number, decimal)
- **Stake** (number, decimal)
- **Data** (date picker, defaults to today)
- **Resultado** (select: Pendente / Ganhou / Perdeu / Void)

On submit: POST /api/bets, close panel, refresh table.

### Import Button
"Importar do bet365" → file picker → upload → toast shows "12 apostas importadas, 3 ignoradas".

---

## Painel (Dashboard) Tab

### Empty State
When user has zero bets: show centered message "Sem dados ainda. Importe ou adicione apostas para ver seu desempenho."

### Summary Cards (top row)
| Card | PT-BR Label | Calculation |
|------|------------|-------------|
| Total P&L | **Lucro / Prejuízo Total** | `sum(lucro_prejuizo)` where resultado ∈ {ganhou, perdeu, void}. Void contributes 0. Pending excluded. |
| Win Rate | **Taxa de Acerto** | `ganhou / (ganhou + perdeu) × 100%` — void and pending excluded |
| ROI | **Retorno (ROI)** | `sum(lucro_prejuizo where resultado ∈ {ganhou, perdeu}) / sum(stake where resultado ∈ {ganhou, perdeu}) × 100%` — void and pending excluded from both numerator and denominator |
| Avg Odds | **Odds Médias** | Mean of `odds` across all resolved bets (ganhou + perdeu only) |
| Streak | **Sequência Atual** | Consecutive same-result bets (ganhou or perdeu) sorted by `criado_em` descending. Displayed as `+N vitórias` or `-N derrotas`. Resets on void/pending. |
| Total Bets | **Total de Apostas** | Count of all bets |

Color coding: positive values in green, negative in red, neutral in orange.

### Charts
1. **Lucro Acumulado** — line chart, cumulative `lucro_prejuizo` by date (Chart.js). Pending bets excluded.
2. **Apostas por Resultado** — doughnut chart: Ganhou / Perdeu / Pendente / Void counts (Chart.js)
3. **L/P por Tipo de Aposta** — horizontal bar chart grouped by `tipo_aposta`, sum of `lucro_prejuizo` per type

All charts use dark color palette: orange, gold, purple, green on dark backgrounds.

### Filters
Date range (De / Até) — applies to all cards and charts simultaneously.

---

## Backend Routes

All `/api/bets/*` routes require `Authorization: Bearer <token>` header. The backend verifies the token and extracts `uid`. All mutating routes verify that the authenticated `uid` matches the bet's stored `uid` before processing.

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/api/bets` | List all user's bets (full list; all stats computed client-side) |
| POST | `/api/bets` | Add single bet manually (`importado_de = "manual"`) |
| POST | `/api/bets/import` | Import bets from bet365 CSV upload (`importado_de = "bet365_csv"`) |
| PUT | `/api/bets/{bet_id}` | Update a bet (recalculates `lucro_prejuizo` on save) |
| DELETE | `/api/bets/{bet_id}` | Delete a bet |

> **No `/api/bets/stats` route.** All dashboard metrics are computed client-side in `painel.js` from the full bet list. This is consistent with the client-side filtering policy and eliminates the FastAPI route-ordering conflict.

---

## Frontend Structure

```
static/
  index.html          ← auth gate + tab shell + <script> tags
  analise.js          ← existing analysis logic (extracted from index.html)
  apostas.js          ← bet table, filters, import, manual entry
  painel.js           ← dashboard charts + summary cards
  auth.js             ← firebase auth logic (sign in, sign up, sign out, token)
  firebase-config.js  ← Firebase project config (public API keys — intentionally tracked in git)
```

> **Note on `firebase-config.js`:** Firebase web API keys are public by design and are safe to commit. Security is enforced via Firebase Security Rules on the Firestore side, not by keeping the config secret.

---

## Environment & Config

### Firebase Backend Credentials (Render)
Do **not** use `GOOGLE_APPLICATION_CREDENTIALS` with a file path on Render — files are not persisted between deploys.

Instead: set the full service account JSON as a single environment variable `FIREBASE_SERVICE_ACCOUNT_JSON` in Render's dashboard. Initialize in `app.py` as:
```python
import json, os
from firebase_admin import credentials, initialize_app

cred = credentials.Certificate(json.loads(os.environ["FIREBASE_SERVICE_ACCOUNT_JSON"]))
initialize_app(cred)
```

### CORS
In production on Render, the frontend and API share the same origin — no CORS headers are needed. In development (`localhost`), add `CORSMiddleware` to allow `http://localhost:8000`. Use an env var `ENV=development` to toggle the middleware on/off, so it is never accidentally enabled in production.

### Firebase Init Guard
Use the following pattern in `app.py` to prevent `ValueError: The default Firebase app already exists` on hot-reload:
```python
import firebase_admin
if not firebase_admin._apps:
    cred = credentials.Certificate(json.loads(os.environ["FIREBASE_SERVICE_ACCOUNT_JSON"]))
    firebase_admin.initialize_app(cred)
```

### New dependencies (`requirements.txt`)
```
firebase-admin
```

### `.gitignore` additions
```
firebase-service-account.json
# firebase-config.js is intentionally NOT gitignored (public keys by design)
```

---

## Free Tier Limits (Firebase Spark Plan)

| Resource | Free Limit | Expected Usage |
|----------|-----------|----------------|
| Auth users | 10,000/month | ~5 |
| Firestore reads | 50,000/day | ~1,000/day |
| Firestore writes | 20,000/day | ~200/day |
| Firestore storage | 1 GB | ~5 MB |

Well within free limits for a small group of friends.

---

## Out of Scope
- bet365 Playwright scraping (replaced by CSV import)
- Social features (sharing bets, leaderboards)
- Multiple bookmakers (bet365 only for now)
- Push notifications
- Mobile app
- Pagination on `/api/bets` (acceptable in v1 given expected volume)
