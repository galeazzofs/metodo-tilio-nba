"""
Shared FastAPI dependencies — imported by app.py and bets/router.py.
Kept in a separate module to avoid circular imports.
"""
import os
import json

import firebase_admin
from firebase_admin import credentials, auth as firebase_auth
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# ---------------------------------------------------------------------------
# Firebase init (guard against double-init on hot reload)
# ---------------------------------------------------------------------------
def init_firebase():
    if firebase_admin._apps:
        return
    sa_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")
    if sa_json:
        cred = credentials.Certificate(json.loads(sa_json))
        firebase_admin.initialize_app(cred)
    # If env var not set (local dev without Firebase), skip — routes will return 401

# ---------------------------------------------------------------------------
# Auth dependency
# ---------------------------------------------------------------------------
_bearer = HTTPBearer(auto_error=False)

_DEV_MODE = not os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")

def require_auth(creds: HTTPAuthorizationCredentials = Depends(_bearer)) -> str:
    """FastAPI dependency — verifies Firebase ID token, returns uid.
    In dev mode (no service account configured), skips verification and
    returns a fixed local uid so the app works without Firebase credentials.
    """
    if _DEV_MODE:
        return "dev-local-uid"
    if not creds:
        raise HTTPException(status_code=401, detail="Token ausente")
    try:
        decoded = firebase_auth.verify_id_token(creds.credentials)
        return decoded["uid"]
    except Exception:
        raise HTTPException(status_code=401, detail="Token inválido ou expirado")
