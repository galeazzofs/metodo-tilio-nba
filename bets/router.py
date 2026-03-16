"""
Bet CRUD + CSV import routes.
All routes require a valid Firebase ID token (uid injected by require_auth dependency).
Firestore collection: users/{uid}/bets/{bet_id}
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from firebase_admin import firestore

from deps import require_auth
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
    data: str           # YYYY-MM-DD
    resultado: str = "pendente"


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
    """Retorna todas as apostas do usuário autenticado."""
    db = _db()
    docs = db.collection("users").document(uid).collection("bets").stream()
    return [doc.to_dict() for doc in docs]


@router.post("", status_code=201)
def add_bet(bet: BetIn, uid: str = Depends(require_auth)):
    """Adiciona uma aposta manualmente."""
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
    """Importa apostas de um arquivo CSV do bet365."""
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
    ignoradas = len(parsed["erros"])

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
    """Atualiza uma aposta. Recalcula lucro_prejuizo automaticamente."""
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
    """Exclui uma aposta."""
    db = _db()
    ref = db.collection("users").document(uid).collection("bets").document(bet_id)
    doc = ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Aposta não encontrada")
    if doc.to_dict().get("uid") != uid:
        raise HTTPException(status_code=403, detail="Acesso negado")
    ref.delete()
