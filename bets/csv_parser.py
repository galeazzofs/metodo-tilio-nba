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

            tipo_aposta = row.get("Tipo", "Outro").strip() or "Outro"

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
