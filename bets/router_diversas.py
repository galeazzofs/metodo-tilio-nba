"""
Apostas Diversas (não-NBA) — CRUD + importação CSV/print.
Espelha bets/router.py, mas grava numa coleção separada e adiciona o campo `esporte`.
Firestore collection: users/{uid}/bets_diversas/{bet_id}
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from firebase_admin import firestore

from deps import require_auth
from bets.router import _compute_lucro
from bets.csv_parser import parse_bet365_csv
from bets.gemini_parser import parse_screenshot

router = APIRouter(prefix="/api/bets-diversas", tags=["bets-diversas"])

COLLECTION = "bets_diversas"


def _db():
    return firestore.client()


def _col(uid: str):
    return _db().collection("users").document(uid).collection(COLLECTION)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class BetIn(BaseModel):
    partida: str
    descricao: str
    esporte: str = "Outro"
    tipo_aposta: str = "Outro"
    odds: float
    stake: float
    data: str           # YYYY-MM-DD
    resultado: str = "pendente"


class BetUpdate(BaseModel):
    partida: Optional[str] = None
    descricao: Optional[str] = None
    esporte: Optional[str] = None
    tipo_aposta: Optional[str] = None
    odds: Optional[float] = None
    stake: Optional[float] = None
    data: Optional[str] = None
    resultado: Optional[str] = None
    lucro_prejuizo: Optional[float] = None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("")
def list_bets(uid: str = Depends(require_auth)):
    """Retorna todas as apostas diversas do usuário autenticado."""
    return [doc.to_dict() for doc in _col(uid).stream()]


@router.post("", status_code=201)
def add_bet(bet: BetIn, uid: str = Depends(require_auth)):
    """Adiciona uma aposta diversa manualmente."""
    bet_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    data = {
        "bet_id": bet_id,
        "uid": uid,
        "data": bet.data,
        "partida": bet.partida,
        "esporte": bet.esporte,
        "tipo_aposta": bet.tipo_aposta,
        "descricao": bet.descricao,
        "odds": bet.odds,
        "stake": bet.stake,
        "resultado": bet.resultado,
        "lucro_prejuizo": _compute_lucro(bet.resultado, bet.odds, bet.stake),
        "importado_de": "manual",
        "criado_em": now,
    }
    _col(uid).document(bet_id).set(data)
    return data


@router.post("/import")
async def import_bets(
    file: UploadFile = File(...),
    uid: str = Depends(require_auth),
):
    """Importa apostas diversas de um arquivo CSV do bet365."""
    content = await file.read()
    parsed = parse_bet365_csv(content, uid)

    user_bets_ref = _col(uid)

    existing = {
        (d.get("data"), d.get("descricao"), d.get("odds"), d.get("stake"))
        for doc in user_bets_ref.stream()
        for d in [doc.to_dict()]
    }

    importadas = 0
    ignoradas = len(parsed["erros"])

    for bet in parsed["bets"]:
        bet.setdefault("esporte", "Outro")
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


@router.post("/import-screenshot")
async def import_screenshot(
    file: UploadFile = File(...),
    uid: str = Depends(require_auth),
):
    """Importa apostas diversas a partir de um print (imagem) usando Gemini Vision."""
    content = await file.read()
    mime = file.content_type or "image/jpeg"
    parsed = parse_screenshot(content, mime)

    user_bets_ref = _col(uid)

    existing = {
        (d.get("data"), d.get("descricao"), d.get("odds"), d.get("stake"))
        for doc in user_bets_ref.stream()
        for d in [doc.to_dict()]
    }

    importadas = 0
    ignoradas = len(parsed["erros"])

    for bet in parsed["bets"]:
        bet["uid"] = uid  # preenche uid
        bet.setdefault("esporte", "Outro")
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
    """Atualiza uma aposta diversa. Recalcula lucro_prejuizo automaticamente."""
    ref = _col(uid).document(bet_id)
    doc = ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Aposta não encontrada")

    current = doc.to_dict()
    if current.get("uid") != uid:
        raise HTTPException(status_code=403, detail="Acesso negado")

    changes = {k: v for k, v in update.model_dump().items() if v is not None}
    merged = {**current, **changes}
    # Se o user enviou lucro_prejuizo manual, usa. Senão, calcula automaticamente.
    if update.lucro_prejuizo is None:
        merged["lucro_prejuizo"] = _compute_lucro(
            merged["resultado"], merged["odds"], merged["stake"]
        )
    ref.set(merged)
    return merged


@router.delete("/{bet_id}", status_code=204)
def delete_bet(bet_id: str, uid: str = Depends(require_auth)):
    """Exclui uma aposta diversa."""
    ref = _col(uid).document(bet_id)
    doc = ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Aposta não encontrada")
    if doc.to_dict().get("uid") != uid:
        raise HTTPException(status_code=403, detail="Acesso negado")
    ref.delete()
