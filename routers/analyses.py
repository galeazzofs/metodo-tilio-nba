"""
routers/analyses.py — Histórico de análises automáticas e manuais.
Coleção Firestore: analyses/{date_str}
Acesso: apenas usuários autenticados (qualquer uid — análises são globais).
"""
from fastapi import APIRouter, Depends
from firebase_admin import firestore

from deps import require_auth

router = APIRouter(prefix="/api/analyses", tags=["analyses"])


@router.get("")
def list_analyses(uid: str = Depends(require_auth)):
    """
    Lista as análises salvas, ordenadas por data desc.
    Retorna apenas análises que tiveram ao menos 1 candidato (candidate_count > 0).
    """
    db = firestore.client()
    docs = (
        db.collection("analyses")
        .where("candidate_count", ">", 0)
        .order_by("candidate_count")           # Firestore exige order_by no campo do where
        .order_by("date", direction=firestore.Query.DESCENDING)
        .limit(60)                             # últimos ~2 meses
        .stream()
    )
    return [doc.to_dict() for doc in docs]


@router.get("/{date_str}")
def get_analysis(date_str: str, uid: str = Depends(require_auth)):
    """Retorna a análise de uma data específica (formato YYYY-MM-DD)."""
    db = firestore.client()
    doc = db.collection("analyses").document(date_str).get()
    if not doc.exists:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Análise não encontrada")
    return doc.to_dict()
