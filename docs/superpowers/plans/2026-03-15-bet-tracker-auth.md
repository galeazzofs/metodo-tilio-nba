# Bet Tracker + Auth Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend NBA Tonight with Firebase Auth (sign up/sign in), per-user Firestore bet tracking, bet365 CSV import, and a PT-BR dashboard — all inside the existing FastAPI app.

**Architecture:** Firebase JS SDK handles auth in the browser; ID tokens sent as `Authorization: Bearer` headers on every `/api/*` request; FastAPI verifies tokens with `firebase-admin`; bets stored in Firestore under `users/{uid}/bets/{bet_id}`; all dashboard stats computed client-side from the full bet list.

**Tech Stack:** FastAPI, firebase-admin (Python), Firebase JS SDK v9 compat (CDN), Firestore, Chart.js (CDN), vanilla JS modules.

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `app.py` | Modify | Add Firebase init, auth dependency, bet routes |
| `bets/router.py` | Create | All `/api/bets/*` route handlers |
| `bets/csv_parser.py` | Create | bet365 CSV parsing + mapping logic |
| `bets/__init__.py` | Create | Package marker |
| `requirements.txt` | Modify | Add `firebase-admin` |
| `static/index.html` | Rewrite | Auth gate + tab shell (no inline JS) |
| `static/firebase-config.js` | Create | Firebase project config (public keys) |
| `static/auth.js` | Create | Sign in, sign up, sign out, token getter |
| `static/analise.js` | Create | Existing analysis JS extracted from index.html |
| `static/apostas.js` | Create | Bet table, filters, manual entry, CSV import |
| `static/painel.js` | Create | Dashboard cards + Chart.js charts |

---

## Chunk 1: Firebase Backend Setup

### Task 1: Add firebase-admin and create auth dependency

**Files:**
- Modify: `requirements.txt`
- Modify: `app.py`
- Create: `bets/__init__.py`

- [ ] **Step 1: Add firebase-admin to requirements.txt**

Open `requirements.txt` and add at the end:
```
firebase-admin
```

- [ ] **Step 2: Install it**

```bash
pip install firebase-admin
```

Expected: installs successfully.

- [ ] **Step 3: Create bets package**

Create `bets/__init__.py` as an empty file.

- [ ] **Step 4: Add Firebase init + auth dependency to app.py**

Replace the top of `app.py` (imports section, before `app = FastAPI()`) with:

```python
import os
import sys
import json
import threading
import uvicorn
import firebase_admin
from firebase_admin import credentials, auth as firebase_auth
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# ---------------------------------------------------------------------------
# Firebase init (guard against double-init on hot reload)
# ---------------------------------------------------------------------------
if not firebase_admin._apps:
    _sa_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")
    if _sa_json:
        _cred = credentials.Certificate(json.loads(_sa_json))
        firebase_admin.initialize_app(_cred)
    # If env var not set (local dev without Firebase), skip — routes will return 401

# ---------------------------------------------------------------------------
# Auth dependency
# ---------------------------------------------------------------------------
_bearer = HTTPBearer(auto_error=False)

def require_auth(creds: HTTPAuthorizationCredentials = Depends(_bearer)) -> str:
    """FastAPI dependency — verifies Firebase ID token, returns uid."""
    if not creds:
        raise HTTPException(status_code=401, detail="Token ausente")
    try:
        decoded = firebase_auth.verify_id_token(creds.credentials)
        return decoded["uid"]
    except Exception:
        raise HTTPException(status_code=401, detail="Token inválido ou expirado")
```

- [ ] **Step 5: Add CORS middleware (dev only) after `app = FastAPI()`**

```python
app = FastAPI()

if os.environ.get("ENV") == "development":
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:8000"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
```

- [ ] **Step 6: Protect existing analysis routes**

Add `uid: str = Depends(require_auth)` to each existing route signature:

```python
@app.post("/api/run")
def start_analysis(uid: str = Depends(require_auth)):
    ...

@app.get("/api/status")
def get_status(uid: str = Depends(require_auth)):
    ...

@app.post("/api/reset")
def reset(uid: str = Depends(require_auth)):
    ...
```

- [ ] **Step 7: Commit**

```bash
git add app.py bets/__init__.py requirements.txt
git commit -m "feat: add firebase-admin auth dependency to all API routes"
```

---

### Task 2: CSV parser module

**Files:**
- Create: `bets/csv_parser.py`

- [ ] **Step 1: Create `bets/csv_parser.py`**

```python
"""
Parses bet365 PT-BR CSV exports into the Firestore bet data model.

Expected CSV columns (validated against real bet365 PT-BR export):
  Data de Liquidação, Descrição, Tipo, Odds, Valor, Retorno, Status
"""
import csv
import uuid
from datetime import datetime, timezone
from io import StringIO
from typing import Any


STATUS_MAP = {
    "Ganhou": "ganhou",
    "Perdeu": "perdeu",
    "Aberta": "pendente",
    "Anulada": "void",
}

TIPO_MAP = {
    "Futebol": "Outro",
    "Basquete": "Outro",
    "Acumulador": "Outro",
    # Extend as needed; unknown types default to "Outro"
}


def _parse_date(raw: str) -> str:
    """Normalise any date string to ISO 8601 YYYY-MM-DD."""
    for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    raise ValueError(f"Formato de data não reconhecido: {raw!r}")


def _parse_float(raw: str) -> float:
    """Parse Brazilian decimal format (1.234,56 or 1234.56)."""
    raw = raw.strip().replace("\xa0", "").replace(" ", "")
    # Brazilian format: dots as thousands sep, comma as decimal
    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    return float(raw)


def _parse_descricao(raw: str) -> tuple[str, str]:
    """Return (partida, descricao). partida = text before first ' - '."""
    descricao = raw.strip()
    if " - " in descricao:
        partida = descricao.split(" - ", 1)[0].strip()
    else:
        partida = descricao
    return partida, descricao


def parse_bet365_csv(content: bytes, uid: str) -> dict[str, Any]:
    """
    Parse a bet365 CSV file.

    Returns:
        {
            "bets": [list of bet dicts ready for Firestore],
            "erros": [list of error strings],
        }
    """
    text = content.decode("utf-8-sig")  # strip BOM if present
    reader = csv.DictReader(StringIO(text))

    bets = []
    erros = []
    now = datetime.now(timezone.utc).isoformat()

    for i, row in enumerate(reader, start=2):  # row 1 = header
        try:
            raw_status = row.get("Status", "").strip()
            resultado = STATUS_MAP.get(raw_status, "pendente")

            raw_date = row.get("Data de Liquidação", "").strip()
            if not raw_date:
                raise ValueError("Data de Liquidação vazia")
            data = _parse_date(raw_date)

            raw_desc = row.get("Descrição", "").strip()
            partida, descricao = _parse_descricao(raw_desc)

            tipo_raw = row.get("Tipo", "").strip()
            tipo_aposta = TIPO_MAP.get(tipo_raw, "Outro")

            odds = _parse_float(row.get("Odds", "0"))
            stake = _parse_float(row.get("Valor", "0"))

            if resultado == "pendente":
                lucro_prejuizo = None
            else:
                retorno_raw = row.get("Retorno", "").strip()
                retorno = _parse_float(retorno_raw) if retorno_raw else 0.0
                lucro_prejuizo = round(retorno - stake, 2)

            bets.append({
                "bet_id": str(uuid.uuid4()),
                "uid": uid,
                "data": data,
                "partida": partida,
                "tipo_aposta": tipo_aposta,
                "descricao": descricao,
                "odds": odds,
                "stake": stake,
                "resultado": resultado,
                "lucro_prejuizo": lucro_prejuizo,
                "importado_de": "bet365_csv",
                "criado_em": now,
            })

        except Exception as e:
            erros.append(f"Linha {i}: {e}")

    return {"bets": bets, "erros": erros}
```

- [ ] **Step 2: Write tests for the CSV parser**

Create `tests/test_csv_parser.py`:

```python
import pytest
from bets.csv_parser import parse_bet365_csv, _parse_date, _parse_float, _parse_descricao

SAMPLE_CSV = (
    "Data de Liquidação,Descrição,Tipo,Odds,Valor,Retorno,Status\n"
    "15/03/2026 20:00:00,Lakers vs Celtics - LeBron Mais de 25.5,Basquete,1.85,50.00,92.50,Ganhou\n"
    "15/03/2026 20:00:00,Warriors vs Nets,Basquete,2.10,30.00,0.00,Perdeu\n"
    "16/03/2026 00:00:00,Knicks vs Heat - Jogo Completo,Basquete,1.50,20.00,,Aberta\n"
).encode("utf-8")


def test_parse_date_formats():
    assert _parse_date("15/03/2026 20:00:00") == "2026-03-15"
    assert _parse_date("15/03/2026") == "2026-03-15"
    assert _parse_date("2026-03-15") == "2026-03-15"


def test_parse_float_brazilian():
    assert _parse_float("1.234,56") == 1234.56
    assert _parse_float("50.00") == 50.0
    assert _parse_float("92,50") == 92.5


def test_parse_descricao_with_separator():
    partida, descricao = _parse_descricao("Lakers vs Celtics - LeBron Mais de 25.5")
    assert partida == "Lakers vs Celtics"
    assert descricao == "Lakers vs Celtics - LeBron Mais de 25.5"


def test_parse_descricao_without_separator():
    partida, descricao = _parse_descricao("Warriors vs Nets")
    assert partida == "Warriors vs Nets"
    assert descricao == "Warriors vs Nets"


def test_parse_won_bet():
    result = parse_bet365_csv(SAMPLE_CSV, uid="test-uid")
    bet = result["bets"][0]
    assert bet["resultado"] == "ganhou"
    assert bet["lucro_prejuizo"] == round(92.50 - 50.00, 2)
    assert bet["partida"] == "Lakers vs Celtics"
    assert bet["data"] == "2026-03-15"
    assert bet["importado_de"] == "bet365_csv"
    assert bet["uid"] == "test-uid"


def test_parse_lost_bet():
    result = parse_bet365_csv(SAMPLE_CSV, uid="test-uid")
    bet = result["bets"][1]
    assert bet["resultado"] == "perdeu"
    assert bet["lucro_prejuizo"] == round(0.0 - 30.0, 2)


def test_parse_open_bet_has_null_lucro():
    result = parse_bet365_csv(SAMPLE_CSV, uid="test-uid")
    bet = result["bets"][2]
    assert bet["resultado"] == "pendente"
    assert bet["lucro_prejuizo"] is None


def test_no_errors_on_valid_csv():
    result = parse_bet365_csv(SAMPLE_CSV, uid="test-uid")
    assert result["erros"] == []


def test_invalid_row_produces_error():
    bad_csv = (
        "Data de Liquidação,Descrição,Tipo,Odds,Valor,Retorno,Status\n"
        "NAO-E-DATA,Alguma aposta,Basquete,abc,50.00,0.00,Perdeu\n"
    ).encode("utf-8")
    result = parse_bet365_csv(bad_csv, uid="test-uid")
    assert len(result["erros"]) == 1
    assert "Linha 2" in result["erros"][0]
```

- [ ] **Step 3: Run tests**

```bash
pip install pytest
pytest tests/test_csv_parser.py -v
```

Expected: all 9 tests pass.

- [ ] **Step 4: Commit**

```bash
git add bets/csv_parser.py tests/test_csv_parser.py
git commit -m "feat: add bet365 CSV parser with full test coverage"
```

---

### Task 3: Bet API routes

**Files:**
- Create: `bets/router.py`
- Modify: `app.py`

- [ ] **Step 1: Create `bets/router.py`**

```python
"""
Bet CRUD + CSV import routes.
All routes require a valid Firebase ID token (uid injected by require_auth dependency).
Firestore collection: users/{uid}/bets/{bet_id}
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel, Field
from firebase_admin import firestore

from app import require_auth
from bets.csv_parser import parse_bet365_csv

router = APIRouter(prefix="/api/bets", tags=["bets"])


def _db():
    return firestore.client()


def _compute_lucro(resultado: str, odds: float, stake: float) -> Optional[float]:
    if resultado == "ganhou":
        return round((odds - 1) * stake, 2)
    elif resultado == "perdeu":
        return round(-stake, 2)
    elif resultado == "void":
        return 0.0
    return None  # pendente


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class BetIn(BaseModel):
    partida: str
    descricao: str
    tipo_aposta: str = "Outro"
    odds: float
    stake: float
    data: str  # YYYY-MM-DD
    resultado: str = "pendente"  # ganhou | perdeu | pendente | void


class BetUpdate(BaseModel):
    partida: Optional[str] = None
    descricao: Optional[str] = None
    tipo_aposta: Optional[str] = None
    odds: Optional[float] = None
    stake: Optional[float] = None
    data: Optional[str] = None
    resultado: Optional[str] = None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("")
def list_bets(uid: str = Depends(require_auth)):
    """Return all bets for the authenticated user."""
    db = _db()
    docs = db.collection("users").document(uid).collection("bets").stream()
    return [doc.to_dict() for doc in docs]


@router.post("", status_code=201)
def add_bet(bet: BetIn, uid: str = Depends(require_auth)):
    """Add a single bet manually."""
    db = _db()
    bet_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    data = {
        "bet_id": bet_id,
        "uid": uid,
        "data": bet.data,
        "partida": bet.partida,
        "tipo_aposta": bet.tipo_aposta,
        "descricao": bet.descricao,
        "odds": bet.odds,
        "stake": bet.stake,
        "resultado": bet.resultado,
        "lucro_prejuizo": _compute_lucro(bet.resultado, bet.odds, bet.stake),
        "importado_de": "manual",
        "criado_em": now,
    }
    db.collection("users").document(uid).collection("bets").document(bet_id).set(data)
    return data


@router.post("/import")
async def import_bets(
    file: UploadFile = File(...),
    uid: str = Depends(require_auth),
):
    """Import bets from a bet365 CSV file."""
    content = await file.read()
    parsed = parse_bet365_csv(content, uid)

    db = _db()
    user_bets_ref = db.collection("users").document(uid).collection("bets")

    # Fetch existing bets for deduplication
    existing = {
        (d.get("data"), d.get("descricao"), d.get("odds"), d.get("stake"))
        for doc in user_bets_ref.stream()
        for d in [doc.to_dict()]
    }

    importadas = 0
    ignoradas = len(parsed["erros"])  # start with parse errors

    for bet in parsed["bets"]:
        key = (bet["data"], bet["descricao"], bet["odds"], bet["stake"])
        if key in existing:
            ignoradas += 1
            continue
        user_bets_ref.document(bet["bet_id"]).set(bet)
        existing.add(key)
        importadas += 1

    return {
        "importadas": importadas,
        "ignoradas": ignoradas,
        "erros": parsed["erros"],
    }


@router.put("/{bet_id}")
def update_bet(bet_id: str, update: BetUpdate, uid: str = Depends(require_auth)):
    """Update a bet. Recalculates lucro_prejuizo on every save."""
    db = _db()
    ref = db.collection("users").document(uid).collection("bets").document(bet_id)
    doc = ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Aposta não encontrada")

    current = doc.to_dict()
    if current.get("uid") != uid:
        raise HTTPException(status_code=403, detail="Acesso negado")

    changes = {k: v for k, v in update.model_dump().items() if v is not None}
    merged = {**current, **changes}
    merged["lucro_prejuizo"] = _compute_lucro(
        merged["resultado"], merged["odds"], merged["stake"]
    )
    ref.set(merged)
    return merged


@router.delete("/{bet_id}", status_code=204)
def delete_bet(bet_id: str, uid: str = Depends(require_auth)):
    """Delete a bet."""
    db = _db()
    ref = db.collection("users").document(uid).collection("bets").document(bet_id)
    doc = ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Aposta não encontrada")
    if doc.to_dict().get("uid") != uid:
        raise HTTPException(status_code=403, detail="Acesso negado")
    ref.delete()
```

- [ ] **Step 2: Register the router in app.py**

Add at the bottom of the imports section in `app.py`:

```python
from bets.router import router as bets_router
```

And after `app = FastAPI()` and the CORS block:

```python
app.include_router(bets_router)
```

- [ ] **Step 3: Commit**

```bash
git add bets/router.py app.py
git commit -m "feat: add bet CRUD and CSV import API routes"
```

---

## Chunk 2: Frontend — Auth + Shell

### Task 4: Firebase config file

**Files:**
- Create: `static/firebase-config.js`

- [ ] **Step 1: Create a Firebase project**

1. Go to [console.firebase.google.com](https://console.firebase.google.com)
2. Click **Add project** → name it `nba-tonight` → continue
3. **Authentication** → Get started → Email/Password → Enable
4. **Firestore Database** → Create database → Start in **test mode** (you'll lock it down later)
5. **Project settings** → Your apps → Add app (Web `</>`) → Register → copy config

- [ ] **Step 2: Create `static/firebase-config.js`**

```js
// Firebase web config — public keys, safe to commit.
// Security enforced via Firestore Security Rules, not by hiding this file.
const firebaseConfig = {
  apiKey: "YOUR_API_KEY",
  authDomain: "YOUR_PROJECT.firebaseapp.com",
  projectId: "YOUR_PROJECT_ID",
  storageBucket: "YOUR_PROJECT.appspot.com",
  messagingSenderId: "YOUR_SENDER_ID",
  appId: "YOUR_APP_ID"
};
```

Replace placeholder values with your real Firebase config.

- [ ] **Step 3: Commit**

```bash
git add static/firebase-config.js
git commit -m "feat: add Firebase web config"
```

---

### Task 5: Auth JS module

**Files:**
- Create: `static/auth.js`

- [ ] **Step 1: Create `static/auth.js`**

```js
// auth.js — Firebase Auth helpers
// Depends on: firebase-config.js loaded before this script

firebase.initializeApp(firebaseConfig);

const auth = firebase.auth();

// Use session persistence: token cleared when tab closes
auth.setPersistence(firebase.auth.Auth.Persistence.SESSION).catch(console.error);

/** Sign in with email + password. Throws on failure. */
async function signIn(email, password) {
  await auth.signInWithEmailAndPassword(email, password);
}

/** Create account. Throws on failure. */
async function signUp(email, password) {
  await auth.createUserWithEmailAndPassword(email, password);
}

/** Sign out. */
async function signOut() {
  await auth.signOut();
}

/** Get a fresh ID token for API calls. Returns null if not signed in. */
async function getToken() {
  const user = auth.currentUser;
  if (!user) return null;
  return user.getIdToken(/* forceRefresh */ false);
}

/**
 * Make an authenticated fetch. Automatically adds Authorization header.
 * Usage: await authFetch('/api/bets', { method: 'GET' })
 */
async function authFetch(url, options = {}) {
  const token = await getToken();
  const headers = {
    ...(options.headers || {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
  return fetch(url, { ...options, headers });
}

/**
 * Register a callback that fires whenever auth state changes.
 * Callback receives the Firebase user object (or null if signed out).
 */
function onAuthChange(callback) {
  auth.onAuthStateChanged(callback);
}
```

- [ ] **Step 2: Commit**

```bash
git add static/auth.js
git commit -m "feat: add Firebase auth JS module with authFetch helper"
```

---

### Task 6: Rewrite index.html as auth gate + tab shell

**Files:**
- Rewrite: `static/index.html`
- Create: `static/analise.js` (extract existing JS from index.html)

- [ ] **Step 1: Extract existing JS from index.html into `static/analise.js`**

Open `static/index.html`, copy everything inside the `<script>` tag at the bottom, and paste into a new file `static/analise.js`. The JS references `authFetch` instead of bare `fetch` for API calls.

In `analise.js`, replace every `fetch('/api/run'` with `authFetch('/api/run'` and every `fetch('/api/status'` with `authFetch('/api/status'`.

- [ ] **Step 2: Rewrite `static/index.html`**

```html
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>NBA Tonight</title>
  <style>
    :root {
      --bg: #080810; --surface: #0f0f1a;
      --card: rgba(255,255,255,0.04); --card-border: rgba(255,255,255,0.08);
      --orange: #f76c1b; --orange-glow: rgba(247,108,27,0.3);
      --gold: #fbbf24; --purple: #a78bfa; --green: #34d399;
      --red: #f87171; --text: #f1f5f9; --muted: #64748b;
      --border: rgba(255,255,255,0.06);
    }
    * { margin:0; padding:0; box-sizing:border-box; }
    body { background:var(--bg); color:var(--text); font-family:'Segoe UI',system-ui,sans-serif; min-height:100vh; }

    /* ── Auth screen ── */
    #authScreen {
      display:flex; align-items:center; justify-content:center;
      min-height:100vh;
      background: radial-gradient(ellipse at 30% 30%, rgba(247,108,27,0.08) 0%, transparent 60%),
                  radial-gradient(ellipse at 70% 70%, rgba(167,139,250,0.06) 0%, transparent 60%);
    }
    .auth-card {
      background:var(--surface); border:1px solid var(--card-border);
      border-radius:20px; padding:40px; width:360px; max-width:90vw;
    }
    .auth-logo { text-align:center; margin-bottom:28px; }
    .auth-logo .ball { font-size:36px; }
    .auth-logo h1 { font-size:22px; font-weight:800; margin-top:8px; }
    .auth-logo p  { font-size:13px; color:var(--muted); margin-top:4px; }
    .auth-toggle  { display:flex; gap:0; margin-bottom:24px; border:1px solid var(--border); border-radius:10px; overflow:hidden; }
    .auth-toggle button {
      flex:1; padding:10px; background:transparent; border:none; color:var(--muted);
      font-size:13px; font-weight:600; cursor:pointer; transition:all .2s;
    }
    .auth-toggle button.active { background:var(--orange); color:#fff; }
    .auth-field { margin-bottom:14px; }
    .auth-field label { display:block; font-size:12px; color:var(--muted); margin-bottom:6px; font-weight:600; letter-spacing:.5px; text-transform:uppercase; }
    .auth-field input {
      width:100%; padding:12px 14px; background:var(--card); border:1px solid var(--border);
      border-radius:10px; color:var(--text); font-size:14px; outline:none;
      transition:border-color .2s;
    }
    .auth-field input:focus { border-color:var(--orange); }
    .btn-auth {
      width:100%; padding:14px; background:var(--orange); border:none; border-radius:50px;
      color:#fff; font-size:15px; font-weight:700; cursor:pointer; margin-top:8px;
      box-shadow:0 0 24px var(--orange-glow); transition:all .2s;
    }
    .btn-auth:hover:not(:disabled) { transform:translateY(-1px); box-shadow:0 0 40px var(--orange-glow); }
    .btn-auth:disabled { opacity:.6; cursor:not-allowed; }
    .auth-error { color:var(--red); font-size:13px; margin-top:12px; text-align:center; min-height:20px; }

    /* ── App shell ── */
    #appShell { display:none; flex-direction:column; min-height:100vh; }

    /* Header */
    .app-header {
      display:flex; align-items:center; justify-content:space-between;
      padding:16px 32px; border-bottom:1px solid var(--border);
      background:rgba(8,8,16,0.8); backdrop-filter:blur(10px);
      position:sticky; top:0; z-index:100;
    }
    .header-brand { font-size:16px; font-weight:800; letter-spacing:-0.5px; }
    .header-brand span { color:var(--orange); }
    .header-tabs { display:flex; gap:4px; }
    .tab-btn {
      padding:8px 20px; border:none; background:transparent; color:var(--muted);
      font-size:13px; font-weight:600; cursor:pointer; border-radius:8px; transition:all .2s;
    }
    .tab-btn.active { background:var(--orange); color:#fff; }
    .tab-btn:hover:not(.active) { color:var(--text); background:var(--card); }
    .btn-sair {
      padding:8px 16px; border:1px solid var(--border); background:transparent;
      color:var(--muted); font-size:13px; border-radius:8px; cursor:pointer; transition:all .2s;
    }
    .btn-sair:hover { color:var(--red); border-color:var(--red); }

    /* Tab panels */
    .tab-panel { display:none; }
    .tab-panel.active { display:block; }

    /* Toast */
    #toast {
      position:fixed; bottom:32px; left:50%; transform:translateX(-50%) translateY(80px);
      background:var(--surface); border:1px solid var(--border); border-radius:12px;
      padding:14px 24px; font-size:14px; z-index:999; transition:transform .3s;
      pointer-events:none;
    }
    #toast.show { transform:translateX(-50%) translateY(0); }
  </style>
</head>
<body>

<!-- ── Auth Screen ── -->
<div id="authScreen">
  <div class="auth-card">
    <div class="auth-logo">
      <div class="ball">🏀</div>
      <h1>NBA Tonight</h1>
      <p>Análise de apostas esportivas</p>
    </div>
    <div class="auth-toggle">
      <button id="btnToggleEntrar" class="active" onclick="setMode('entrar')">Entrar</button>
      <button id="btnToggleCriar" onclick="setMode('criar')">Criar conta</button>
    </div>
    <div class="auth-field">
      <label>Email</label>
      <input type="email" id="authEmail" placeholder="seu@email.com" />
    </div>
    <div class="auth-field">
      <label>Senha</label>
      <input type="password" id="authPassword" placeholder="••••••••" />
    </div>
    <div class="auth-field" id="fieldConfirm" style="display:none">
      <label>Confirmar senha</label>
      <input type="password" id="authConfirm" placeholder="••••••••" />
    </div>
    <button class="btn-auth" id="btnAuth" onclick="handleAuth()">Entrar</button>
    <div class="auth-error" id="authError"></div>
  </div>
</div>

<!-- ── App Shell ── -->
<div id="appShell">
  <header class="app-header">
    <div class="header-brand">🏀 <span>NBA</span> Tonight</div>
    <nav class="header-tabs">
      <button class="tab-btn active" onclick="switchTab('analise')">Análise</button>
      <button class="tab-btn" onclick="switchTab('apostas')">Minhas Apostas</button>
      <button class="tab-btn" onclick="switchTab('painel')">Painel</button>
    </nav>
    <button class="btn-sair" onclick="handleSignOut()">Sair</button>
  </header>

  <main>
    <div id="tab-analise" class="tab-panel active"></div>
    <div id="tab-apostas" class="tab-panel"></div>
    <div id="tab-painel"  class="tab-panel"></div>
  </main>
</div>

<div id="toast"></div>

<!-- Firebase SDKs (compat v9) -->
<script src="https://www.gstatic.com/firebasejs/9.22.2/firebase-app-compat.js"></script>
<script src="https://www.gstatic.com/firebasejs/9.22.2/firebase-auth-compat.js"></script>

<!-- App modules -->
<script src="/static/firebase-config.js"></script>
<script src="/static/auth.js"></script>
<script src="/static/analise.js"></script>
<script src="/static/apostas.js"></script>
<script src="/static/painel.js"></script>

<script>
  // ── Shell logic ──
  let _mode = 'entrar';

  function setMode(mode) {
    _mode = mode;
    document.getElementById('btnToggleEntrar').classList.toggle('active', mode === 'entrar');
    document.getElementById('btnToggleCriar').classList.toggle('active', mode === 'criar');
    document.getElementById('fieldConfirm').style.display = mode === 'criar' ? 'block' : 'none';
    document.getElementById('btnAuth').textContent = mode === 'entrar' ? 'Entrar' : 'Criar conta';
    document.getElementById('authError').textContent = '';
  }

  const AUTH_ERRORS = {
    'auth/invalid-email': 'Email inválido.',
    'auth/user-not-found': 'Email ou senha inválidos.',
    'auth/wrong-password': 'Email ou senha inválidos.',
    'auth/email-already-in-use': 'Email já cadastrado.',
    'auth/weak-password': 'Senha muito fraca (mínimo 6 caracteres).',
    'auth/too-many-requests': 'Muitas tentativas. Tente novamente mais tarde.',
  };

  async function handleAuth() {
    const email = document.getElementById('authEmail').value.trim();
    const password = document.getElementById('authPassword').value;
    const confirm = document.getElementById('authConfirm').value;
    const errEl = document.getElementById('authError');
    const btn = document.getElementById('btnAuth');

    errEl.textContent = '';
    if (_mode === 'criar' && password !== confirm) {
      errEl.textContent = 'As senhas não coincidem.'; return;
    }

    btn.disabled = true;
    try {
      if (_mode === 'entrar') await signIn(email, password);
      else await signUp(email, password);
    } catch (e) {
      errEl.textContent = AUTH_ERRORS[e.code] || 'Erro desconhecido. Tente novamente.';
    } finally {
      btn.disabled = false;
    }
  }

  async function handleSignOut() {
    await signOut();
  }

  // Tab switching
  function switchTab(name) {
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.getElementById('tab-' + name).classList.add('active');
    document.querySelectorAll('.tab-btn').forEach(b => {
      if (b.textContent.toLowerCase().includes(
        name === 'analise' ? 'nális' : name === 'apostas' ? 'aposta' : 'painel'
      )) b.classList.add('active');
    });
    // Update URL hash
    history.replaceState(null, '', '#' + name);
    // Notify modules
    if (name === 'apostas') loadApostas();
    if (name === 'painel') loadPainel();
  }

  // Auth state listener — shows/hides auth screen vs app
  onAuthChange(user => {
    document.getElementById('authScreen').style.display = user ? 'none' : 'flex';
    document.getElementById('appShell').style.display = user ? 'flex' : 'none';
    if (user) {
      // Restore tab from URL hash
      const hash = location.hash.replace('#', '') || 'analise';
      switchTab(hash);
    }
  });

  // Global toast helper
  function showToast(msg, duration = 3000) {
    const t = document.getElementById('toast');
    t.textContent = msg;
    t.classList.add('show');
    setTimeout(() => t.classList.remove('show'), duration);
  }

  // Enter key submits auth form
  document.addEventListener('keydown', e => {
    if (e.key === 'Enter' && document.getElementById('authScreen').style.display !== 'none') {
      handleAuth();
    }
  });
</script>
</body>
</html>
```

- [ ] **Step 3: Commit**

```bash
git add static/index.html static/analise.js
git commit -m "feat: add auth gate, tab shell, extract analise.js"
```

---

## Chunk 3: Frontend — Apostas + Painel

### Task 7: Minhas Apostas tab

**Files:**
- Create: `static/apostas.js`

- [ ] **Step 1: Create `static/apostas.js`**

```js
// apostas.js — Minhas Apostas tab
// Depends on: auth.js (authFetch, getToken), showToast (index.html)

let _allBets = [];

async function loadApostas() {
  const container = document.getElementById('tab-apostas');
  container.innerHTML = '<div style="padding:40px;text-align:center;color:var(--muted)">Carregando...</div>';

  try {
    const res = await authFetch('/api/bets');
    if (!res.ok) throw new Error('Erro ao carregar apostas');
    _allBets = await res.json();
    renderApostas();
  } catch (e) {
    container.innerHTML = `<div style="padding:40px;text-align:center;color:var(--red)">${e.message}</div>`;
  }
}

function renderApostas() {
  const container = document.getElementById('tab-apostas');

  // Filter state
  const q = (document.getElementById('filtroTexto')?.value || '').toLowerCase();
  const res = document.getElementById('filtroResultado')?.value || 'todos';
  const de = document.getElementById('filtroDe')?.value || '';
  const ate = document.getElementById('filtroAte')?.value || '';

  let bets = [..._allBets].sort((a, b) => b.data.localeCompare(a.data));

  if (q) bets = bets.filter(b =>
    b.partida?.toLowerCase().includes(q) || b.descricao?.toLowerCase().includes(q));
  if (res !== 'todos') bets = bets.filter(b => b.resultado === res);
  if (de) bets = bets.filter(b => b.data >= de);
  if (ate) bets = bets.filter(b => b.data <= ate);

  const BADGE = {
    ganhou: '<span style="background:rgba(52,211,153,.15);color:#34d399;padding:2px 10px;border-radius:20px;font-size:11px;font-weight:700">🟢 Ganhou</span>',
    perdeu: '<span style="background:rgba(248,113,113,.15);color:#f87171;padding:2px 10px;border-radius:20px;font-size:11px;font-weight:700">🔴 Perdeu</span>',
    pendente: '<span style="background:rgba(251,191,36,.15);color:#fbbf24;padding:2px 10px;border-radius:20px;font-size:11px;font-weight:700">🟡 Pendente</span>',
    void: '<span style="background:rgba(255,255,255,.08);color:#94a3b8;padding:2px 10px;border-radius:20px;font-size:11px;font-weight:700">⚪ Void</span>',
  };

  const lpColor = v => v == null ? 'var(--muted)' : v >= 0 ? '#34d399' : '#f87171';
  const lpText  = v => v == null ? '—' : (v >= 0 ? '+' : '') + 'R$ ' + v.toFixed(2);

  const rows = bets.length === 0
    ? `<tr><td colspan="7" style="text-align:center;padding:48px;color:var(--muted)">
         Nenhuma aposta encontrada.</td></tr>`
    : bets.map(b => `
      <tr style="border-bottom:1px solid var(--border)">
        <td style="padding:14px 12px;color:var(--muted);font-size:13px">${b.data}</td>
        <td style="padding:14px 12px;font-weight:600">${esc(b.partida)}</td>
        <td style="padding:14px 12px;color:var(--muted);font-size:13px;max-width:240px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(b.descricao)}</td>
        <td style="padding:14px 12px;text-align:right">${b.odds?.toFixed(2) ?? '—'}</td>
        <td style="padding:14px 12px;text-align:right">R$ ${b.stake?.toFixed(2) ?? '—'}</td>
        <td style="padding:14px 12px">${BADGE[b.resultado] ?? b.resultado}</td>
        <td style="padding:14px 12px;text-align:right;font-weight:700;color:${lpColor(b.lucro_prejuizo)}">${lpText(b.lucro_prejuizo)}</td>
      </tr>`).join('');

  const emptyState = _allBets.length === 0
    ? `<div style="text-align:center;padding:60px;color:var(--muted)">
        <div style="font-size:48px;margin-bottom:16px">🎰</div>
        <p>Nenhuma aposta registrada ainda.<br>Importe do bet365 ou adicione manualmente.</p>
       </div>` : '';

  container.innerHTML = `
    <div style="max-width:1100px;margin:0 auto;padding:32px 24px">
      <!-- Toolbar -->
      <div style="display:flex;align-items:center;gap:12px;margin-bottom:24px;flex-wrap:wrap">
        <h2 style="font-size:20px;font-weight:800;flex:1">Minhas Apostas</h2>
        <button onclick="abrirFormulario()" style="padding:10px 20px;background:var(--orange);border:none;border-radius:50px;color:#fff;font-weight:700;cursor:pointer">+ Adicionar</button>
        <label style="padding:10px 20px;background:var(--card);border:1px solid var(--border);border-radius:50px;color:var(--text);font-weight:700;cursor:pointer">
          Importar do bet365
          <input type="file" accept=".csv" style="display:none" onchange="importarCSV(this)" />
        </label>
      </div>

      <!-- Filters -->
      <div style="display:flex;gap:12px;margin-bottom:20px;flex-wrap:wrap">
        <input id="filtroTexto" placeholder="Buscar partida ou descrição..." oninput="renderApostas()"
          style="flex:1;min-width:200px;padding:10px 14px;background:var(--card);border:1px solid var(--border);border-radius:10px;color:var(--text);font-size:13px" />
        <select id="filtroResultado" onchange="renderApostas()"
          style="padding:10px 14px;background:var(--card);border:1px solid var(--border);border-radius:10px;color:var(--text);font-size:13px">
          <option value="todos">Todos</option>
          <option value="ganhou">Ganhou</option>
          <option value="perdeu">Perdeu</option>
          <option value="pendente">Pendente</option>
          <option value="void">Void</option>
        </select>
        <input type="date" id="filtroDe" onchange="renderApostas()"
          style="padding:10px;background:var(--card);border:1px solid var(--border);border-radius:10px;color:var(--text);font-size:13px" />
        <input type="date" id="filtroAte" onchange="renderApostas()"
          style="padding:10px;background:var(--card);border:1px solid var(--border);border-radius:10px;color:var(--text);font-size:13px" />
      </div>

      ${emptyState || `
      <!-- Table -->
      <div style="overflow-x:auto;border:1px solid var(--border);border-radius:16px">
        <table style="width:100%;border-collapse:collapse">
          <thead>
            <tr style="border-bottom:1px solid var(--border)">
              <th style="padding:12px;text-align:left;font-size:11px;letter-spacing:1px;text-transform:uppercase;color:var(--muted)">Data</th>
              <th style="padding:12px;text-align:left;font-size:11px;letter-spacing:1px;text-transform:uppercase;color:var(--muted)">Partida</th>
              <th style="padding:12px;text-align:left;font-size:11px;letter-spacing:1px;text-transform:uppercase;color:var(--muted)">Descrição</th>
              <th style="padding:12px;text-align:right;font-size:11px;letter-spacing:1px;text-transform:uppercase;color:var(--muted)">Odds</th>
              <th style="padding:12px;text-align:right;font-size:11px;letter-spacing:1px;text-transform:uppercase;color:var(--muted)">Stake</th>
              <th style="padding:12px;text-align:left;font-size:11px;letter-spacing:1px;text-transform:uppercase;color:var(--muted)">Resultado</th>
              <th style="padding:12px;text-align:right;font-size:11px;letter-spacing:1px;text-transform:uppercase;color:var(--muted)">L/P</th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>`}

      <!-- Manual entry slide-in -->
      <div id="formPanel" style="display:none;position:fixed;top:0;right:0;bottom:0;width:380px;max-width:100vw;
           background:var(--surface);border-left:1px solid var(--border);padding:32px;overflow-y:auto;z-index:200">
        <h3 style="font-size:18px;font-weight:800;margin-bottom:24px">Nova Aposta</h3>
        ${formField('Partida','formPartida','text','Lakers vs Celtics')}
        ${formField('Descrição','formDescricao','text','LeBron Mais de 25.5')}
        <div style="margin-bottom:16px">
          <label style="display:block;font-size:12px;color:var(--muted);margin-bottom:6px;font-weight:600;text-transform:uppercase">Tipo</label>
          <select id="formTipo" style="width:100%;padding:12px;background:var(--card);border:1px solid var(--border);border-radius:10px;color:var(--text)">
            <option>Vencedor</option><option>Handicap</option><option>Totais</option><option>Jogador</option><option>Outro</option>
          </select>
        </div>
        ${formField('Odds','formOdds','number','1.85')}
        ${formField('Stake (R$)','formStake','number','50')}
        ${formField('Data','formData','date','')}
        <div style="margin-bottom:24px">
          <label style="display:block;font-size:12px;color:var(--muted);margin-bottom:6px;font-weight:600;text-transform:uppercase">Resultado</label>
          <select id="formResultado" style="width:100%;padding:12px;background:var(--card);border:1px solid var(--border);border-radius:10px;color:var(--text)">
            <option value="pendente">Pendente</option>
            <option value="ganhou">Ganhou</option>
            <option value="perdeu">Perdeu</option>
            <option value="void">Void</option>
          </select>
        </div>
        <div style="display:flex;gap:12px">
          <button onclick="salvarAposta()" style="flex:1;padding:14px;background:var(--orange);border:none;border-radius:50px;color:#fff;font-weight:700;cursor:pointer">Salvar</button>
          <button onclick="fecharFormulario()" style="padding:14px 20px;background:var(--card);border:1px solid var(--border);border-radius:50px;color:var(--text);cursor:pointer">Cancelar</button>
        </div>
      </div>
    </div>`;
}

function formField(label, id, type, placeholder) {
  const today = type === 'date' ? new Date().toISOString().slice(0,10) : '';
  const val = type === 'date' ? `value="${today}"` : '';
  return `<div style="margin-bottom:16px">
    <label style="display:block;font-size:12px;color:var(--muted);margin-bottom:6px;font-weight:600;text-transform:uppercase">${label}</label>
    <input type="${type}" id="${id}" placeholder="${placeholder}" ${val}
      style="width:100%;padding:12px;background:var(--card);border:1px solid var(--border);border-radius:10px;color:var(--text);font-size:14px" />
  </div>`;
}

function abrirFormulario() { document.getElementById('formPanel').style.display = 'block'; }
function fecharFormulario() { document.getElementById('formPanel').style.display = 'none'; }

async function salvarAposta() {
  const body = {
    partida: document.getElementById('formPartida').value,
    descricao: document.getElementById('formDescricao').value,
    tipo_aposta: document.getElementById('formTipo').value,
    odds: parseFloat(document.getElementById('formOdds').value),
    stake: parseFloat(document.getElementById('formStake').value),
    data: document.getElementById('formData').value,
    resultado: document.getElementById('formResultado').value,
  };
  const res = await authFetch('/api/bets', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (res.ok) {
    const bet = await res.json();
    _allBets.unshift(bet);
    fecharFormulario();
    renderApostas();
    showToast('✅ Aposta adicionada!');
  } else {
    showToast('❌ Erro ao salvar aposta');
  }
}

async function importarCSV(input) {
  const file = input.files[0];
  if (!file) return;
  const form = new FormData();
  form.append('file', file);
  showToast('⏳ Importando...');
  const res = await authFetch('/api/bets/import', { method: 'POST', body: form });
  if (res.ok) {
    const data = await res.json();
    showToast(`✅ ${data.importadas} apostas importadas, ${data.ignoradas} ignoradas`);
    await loadApostas();
  } else {
    showToast('❌ Erro ao importar CSV');
  }
  input.value = '';
}

function esc(str) {
  return String(str ?? '').replace(/[&<>"']/g, c =>
    ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
```

- [ ] **Step 2: Commit**

```bash
git add static/apostas.js
git commit -m "feat: add Minhas Apostas tab with table, filters, manual entry and CSV import"
```

---

### Task 8: Painel (Dashboard) tab

**Files:**
- Create: `static/painel.js`

- [ ] **Step 1: Create `static/painel.js`**

```js
// painel.js — Dashboard tab
// Depends on: auth.js (authFetch), Chart.js (loaded via CDN in index.html)

let _chartLucro = null;
let _chartResultado = null;
let _chartTipo = null;

async function loadPainel() {
  const container = document.getElementById('tab-painel');
  container.innerHTML = '<div style="padding:40px;text-align:center;color:var(--muted)">Carregando...</div>';

  try {
    const res = await authFetch('/api/bets');
    if (!res.ok) throw new Error('Erro ao carregar apostas');
    const bets = await res.json();
    renderPainel(bets);
  } catch (e) {
    container.innerHTML = `<div style="padding:40px;text-align:center;color:var(--red)">${e.message}</div>`;
  }
}

function renderPainel(bets) {
  const container = document.getElementById('tab-painel');

  if (bets.length === 0) {
    container.innerHTML = `
      <div style="text-align:center;padding:80px;color:var(--muted)">
        <div style="font-size:48px;margin-bottom:16px">📊</div>
        <p>Sem dados ainda. Importe ou adicione apostas para ver seu desempenho.</p>
      </div>`;
    return;
  }

  // Date filter state
  const de  = document.getElementById('painelDe')?.value  || '';
  const ate = document.getElementById('painelAte')?.value || '';
  let filtered = bets;
  if (de)  filtered = filtered.filter(b => b.data >= de);
  if (ate) filtered = filtered.filter(b => b.data <= ate);

  const stats = calcStats(filtered);

  container.innerHTML = `
    <div style="max-width:1100px;margin:0 auto;padding:32px 24px">
      <div style="display:flex;align-items:center;gap:16px;margin-bottom:28px;flex-wrap:wrap">
        <h2 style="font-size:20px;font-weight:800;flex:1">Painel de Desempenho</h2>
        <label style="font-size:12px;color:var(--muted)">De</label>
        <input type="date" id="painelDe" value="${de}" onchange="loadPainel()"
          style="padding:8px;background:var(--card);border:1px solid var(--border);border-radius:8px;color:var(--text);font-size:13px" />
        <label style="font-size:12px;color:var(--muted)">Até</label>
        <input type="date" id="painelAte" value="${ate}" onchange="loadPainel()"
          style="padding:8px;background:var(--card);border:1px solid var(--border);border-radius:8px;color:var(--text);font-size:13px" />
      </div>

      <!-- Summary cards -->
      <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:16px;margin-bottom:32px">
        ${card('Lucro / Prejuízo Total', fmtMoney(stats.totalLP), stats.totalLP >= 0 ? '#34d399' : '#f87171')}
        ${card('Taxa de Acerto', stats.winRate === null ? '—' : stats.winRate.toFixed(1) + '%', '#f76c1b')}
        ${card('Retorno (ROI)', stats.roi === null ? '—' : stats.roi.toFixed(1) + '%', stats.roi >= 0 ? '#34d399' : '#f87171')}
        ${card('Odds Médias', stats.avgOdds === null ? '—' : stats.avgOdds.toFixed(2), '#fbbf24')}
        ${card('Sequência Atual', stats.streakLabel, stats.streakVal > 0 ? '#34d399' : '#f87171')}
        ${card('Total de Apostas', stats.total, '#a78bfa')}
      </div>

      <!-- Charts -->
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:24px;margin-bottom:24px">
        <div style="background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:24px">
          <h3 style="font-size:13px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:16px">Lucro Acumulado</h3>
          <canvas id="chartLucro" height="180"></canvas>
        </div>
        <div style="background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:24px">
          <h3 style="font-size:13px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:16px">Apostas por Resultado</h3>
          <canvas id="chartResultado" height="180"></canvas>
        </div>
      </div>
      <div style="background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:24px;margin-bottom:24px">
        <h3 style="font-size:13px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:16px">L/P por Tipo de Aposta</h3>
        <canvas id="chartTipo" height="120"></canvas>
      </div>
    </div>`;

  // Destroy old charts to avoid canvas reuse errors
  [_chartLucro, _chartResultado, _chartTipo].forEach(c => c?.destroy());

  drawCharts(filtered, stats);
}

function calcStats(bets) {
  const resolved = bets.filter(b => b.resultado === 'ganhou' || b.resultado === 'perdeu');
  const won = bets.filter(b => b.resultado === 'ganhou');
  const lost = bets.filter(b => b.resultado === 'perdeu');

  const totalLP = bets
    .filter(b => ['ganhou','perdeu','void'].includes(b.resultado))
    .reduce((s, b) => s + (b.lucro_prejuizo ?? 0), 0);

  const winRate = resolved.length > 0 ? (won.length / resolved.length) * 100 : null;

  const roiStake = resolved.reduce((s, b) => s + (b.stake ?? 0), 0);
  const roiLP    = resolved.reduce((s, b) => s + (b.lucro_prejuizo ?? 0), 0);
  const roi = roiStake > 0 ? (roiLP / roiStake) * 100 : null;

  const avgOdds = resolved.length > 0
    ? resolved.reduce((s, b) => s + (b.odds ?? 0), 0) / resolved.length
    : null;

  // Streak: sort by criado_em desc, count consecutive same result
  const sorted = [...bets]
    .filter(b => b.resultado === 'ganhou' || b.resultado === 'perdeu')
    .sort((a, b) => b.criado_em.localeCompare(a.criado_em));
  let streakVal = 0, streakLabel = '—';
  if (sorted.length > 0) {
    const first = sorted[0].resultado;
    for (const b of sorted) {
      if (b.resultado !== first) break;
      streakVal += (first === 'ganhou' ? 1 : -1);
    }
    streakLabel = streakVal > 0
      ? `+${Math.abs(streakVal)} vitória${Math.abs(streakVal) > 1 ? 's' : ''}`
      : `-${Math.abs(streakVal)} derrota${Math.abs(streakVal) > 1 ? 's' : ''}`;
  }

  return { totalLP, winRate, roi, avgOdds, streakVal, streakLabel, total: bets.length };
}

function drawCharts(bets, stats) {
  const CHART_DEFAULTS = {
    plugins: { legend: { labels: { color: '#94a3b8', font: { size: 12 } } } },
    scales: {},
  };

  // 1. Cumulative P&L line chart
  const resolvedSorted = bets
    .filter(b => b.resultado !== 'pendente')
    .sort((a, b) => a.data.localeCompare(b.data));
  let cum = 0;
  const lineData = resolvedSorted.map(b => {
    cum += (b.lucro_prejuizo ?? 0);
    return { x: b.data, y: parseFloat(cum.toFixed(2)) };
  });

  _chartLucro = new Chart(document.getElementById('chartLucro'), {
    type: 'line',
    data: {
      labels: lineData.map(d => d.x),
      datasets: [{
        label: 'Lucro Acumulado (R$)',
        data: lineData.map(d => d.y),
        borderColor: '#f76c1b',
        backgroundColor: 'rgba(247,108,27,0.08)',
        fill: true,
        tension: 0.3,
        pointRadius: 2,
      }],
    },
    options: {
      ...CHART_DEFAULTS,
      scales: {
        x: { ticks: { color: '#64748b', maxTicksLimit: 8 }, grid: { color: 'rgba(255,255,255,0.04)' } },
        y: { ticks: { color: '#64748b' }, grid: { color: 'rgba(255,255,255,0.04)' } },
      },
    },
  });

  // 2. Doughnut — results breakdown
  const counts = { Ganhou: 0, Perdeu: 0, Pendente: 0, Void: 0 };
  bets.forEach(b => {
    if (b.resultado === 'ganhou') counts.Ganhou++;
    else if (b.resultado === 'perdeu') counts.Perdeu++;
    else if (b.resultado === 'pendente') counts.Pendente++;
    else counts.Void++;
  });

  _chartResultado = new Chart(document.getElementById('chartResultado'), {
    type: 'doughnut',
    data: {
      labels: Object.keys(counts),
      datasets: [{
        data: Object.values(counts),
        backgroundColor: ['#34d399','#f87171','#fbbf24','#64748b'],
        borderWidth: 0,
      }],
    },
    options: { ...CHART_DEFAULTS, cutout: '65%' },
  });

  // 3. Bar — L/P by bet type
  const byTipo = {};
  bets.filter(b => b.resultado !== 'pendente').forEach(b => {
    const t = b.tipo_aposta || 'Outro';
    byTipo[t] = (byTipo[t] ?? 0) + (b.lucro_prejuizo ?? 0);
  });

  _chartTipo = new Chart(document.getElementById('chartTipo'), {
    type: 'bar',
    data: {
      labels: Object.keys(byTipo),
      datasets: [{
        label: 'L/P (R$)',
        data: Object.values(byTipo).map(v => parseFloat(v.toFixed(2))),
        backgroundColor: Object.values(byTipo).map(v => v >= 0 ? 'rgba(52,211,153,0.7)' : 'rgba(248,113,113,0.7)'),
        borderRadius: 6,
      }],
    },
    options: {
      ...CHART_DEFAULTS,
      indexAxis: 'y',
      scales: {
        x: { ticks: { color: '#64748b' }, grid: { color: 'rgba(255,255,255,0.04)' } },
        y: { ticks: { color: '#94a3b8' }, grid: { display: false } },
      },
    },
  });
}

function card(label, value, color) {
  return `
    <div style="background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:20px">
      <div style="font-size:11px;color:var(--muted);font-weight:600;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">${label}</div>
      <div style="font-size:24px;font-weight:800;color:${color}">${value}</div>
    </div>`;
}

function fmtMoney(v) {
  if (v == null) return '—';
  return (v >= 0 ? '+' : '') + 'R$ ' + Math.abs(v).toFixed(2);
}
```

- [ ] **Step 2: Add Chart.js CDN to index.html**

In `static/index.html`, before the `</body>` closing tag (after the Firebase SDK scripts), add:

```html
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.2/dist/chart.umd.min.js"></script>
```

- [ ] **Step 3: Commit**

```bash
git add static/painel.js static/index.html
git commit -m "feat: add Painel dashboard with Chart.js charts and summary cards"
```

---

## Chunk 4: Deployment

### Task 9: Set up Firestore Security Rules

- [ ] **Step 1: Open Firestore in Firebase console**

Go to Firebase Console → Firestore Database → Rules tab.

- [ ] **Step 2: Replace default rules with**

```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /users/{uid}/bets/{betId} {
      allow read, write: if request.auth != null && request.auth.uid == uid;
    }
  }
}
```

Click **Publish**. This ensures users can only read/write their own bets.

---

### Task 10: Generate service account + deploy to Render

- [ ] **Step 1: Generate Firebase service account**

Firebase Console → Project settings → Service accounts → Generate new private key → Download JSON.

- [ ] **Step 2: Set Render environment variables**

In Render dashboard → your service → Environment:
- `FIREBASE_SERVICE_ACCOUNT_JSON` = paste entire contents of the downloaded JSON file
- `ENV` = (leave unset for production)

- [ ] **Step 3: Update Render build command**

In Render dashboard → your service → Settings:
- **Build command:** `pip install -r requirements.txt && python -m playwright install chromium`
- **Start command:** `python app.py`

- [ ] **Step 4: Push all changes and trigger deploy**

```bash
git push origin main
```

Watch Render build logs. Expected: build succeeds, app starts on port from `$PORT`.

- [ ] **Step 5: Smoke test**

1. Open the Render URL — should show the PT-BR sign-in screen
2. Create an account → sign in → see three tabs
3. Run analysis (Análise tab) → should work as before
4. Add a manual bet → appears in Minhas Apostas
5. Open Painel → shows dashboard cards and charts
6. Sign out → returns to sign-in screen

---

### Task 11: Push final state to GitHub

- [ ] **Step 1: Final commit and push**

```bash
git add -A
git status  # review — should not include .env or credential files
git commit -m "feat: complete bet tracker with auth, CSV import and dashboard"
git push origin main
```
