"""
Gemini Vision parser — interpreta prints de histórico de apostas (ex: bet365)
e retorna uma lista estruturada de apostas.

Requer a variável de ambiente GEMINI_API_KEY.

Usa o tier gratuito da Gemini API com fallback entre modelos: cada modelo tem
cota diária própria, então a cadeia multiplica o limite gratuito total.
"""
import os
import uuid
import json
from datetime import datetime, timezone
from typing import Literal, Optional

from google import genai
from google.genai import types, errors
from pydantic import BaseModel

# Ordem: melhor qualidade primeiro; ao estourar cota (429), tenta o próximo.
_MODEL_CHAIN = [
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
]

_PROMPT = """
Você vai receber uma imagem de um histórico de apostas esportivas (pode ser da bet365 ou outra casa).
Extraia TODAS as apostas visíveis e retorne a lista estruturada.

Regras:
- "stake" é o valor APOSTADO (rótulos como "Aposta", "Stake", "Valor"). NUNCA use o valor de
  "Retorno"/"Return"/"Ganhos" como stake — retorno é o pagamento, não o valor apostado.
- Aposta múltipla/acumulada/parlay: trate o bilhete inteiro como UMA aposta, com a odd combinada
  do bilhete e "descricao" listando as seleções separadas por " + ".
- "tipo_aposta": props de jogador classifique pelo tipo específico — Pontos (points/pts),
  Assistências (assists/ast), Rebotes (rebounds/reb), 3 Pontos (three pointers/3pt/threes).
  Múltiplas com seleções de tipos diferentes → "Outro".
- "resultado": "Won"/"Ganha" → ganhou, "Lost"/"Perdida" → perdeu, "Open"/"Em aberto" → pendente,
  "Void"/"Anulada"/"Cancelada" → void. Cash out com retorno > 0 → ganhou; cash out com retorno 0 → perdeu.
- Risco/meio (half win/half loss) ou push em handicap asiático sem indicação clara → void.
- "data" no formato YYYY-MM-DD; se aparecer apenas dia/mês, use o ano atual.
- "odds" no formato decimal (ex.: 1.85). Se a casa mostrar formato americano (+150/-110), converta para decimal.
- Se algum campo não estiver visível: tipo_aposta="Outro", resultado="pendente", stake=0.
- Não invente apostas: extraia somente o que está legível na imagem. Se não houver apostas, retorne lista vazia.
"""


class _BetItem(BaseModel):
    partida: str
    descricao: str
    tipo_aposta: Literal[
        "Vencedor", "Handicap", "Totais", "Jogador", "Pontos",
        "Assistências", "Rebotes", "3 Pontos", "Outro",
    ]
    odds: float
    stake: float
    data: Optional[str] = None
    resultado: Literal["ganhou", "perdeu", "pendente", "void"]


def _generate(client: genai.Client, image_bytes: bytes, mime_type: str):
    """Tenta cada modelo da cadeia; só propaga erro se todos falharem."""
    last_err = None
    for model_name in _MODEL_CHAIN:
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=list[_BetItem],
        )
        if model_name.startswith("gemini-3"):
            # Resolução alta melhora OCR de prints densos (suportado no Gemini 3+)
            config.media_resolution = types.MediaResolution.MEDIA_RESOLUTION_HIGH
        try:
            return client.models.generate_content(
                model=model_name,
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                    _PROMPT,
                ],
                config=config,
            )
        except errors.APIError as e:
            # 429 = cota do modelo esgotada; 404/400 = modelo indisponível neste projeto;
            # 503 = sobrecarga temporária — em todos os casos vale tentar o próximo modelo.
            last_err = e
            if e.code not in (429, 404, 400, 503):
                raise
    raise last_err


def parse_screenshot(image_bytes: bytes, mime_type: str = "image/jpeg") -> dict:
    """
    Envia a imagem para a Gemini API e retorna:
    {
        "bets": [...],   # lista de dicts prontos para salvar
        "erros": [...]   # mensagens de erro/avisos
    }
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return {"bets": [], "erros": ["GEMINI_API_KEY não configurada no servidor."]}

    client = genai.Client(api_key=api_key)

    try:
        response = _generate(client, image_bytes, mime_type)
    except Exception as e:
        return {"bets": [], "erros": [f"Erro ao chamar Gemini API: {e}"]}

    # Com response_schema o SDK já devolve os objetos validados em .parsed;
    # fallback para o texto bruto caso a validação falhe.
    items = response.parsed
    if items is None:
        try:
            items = [_BetItem(**d) for d in json.loads(response.text)]
        except Exception:
            return {"bets": [], "erros": [f"Resposta inesperada do Gemini: {str(response.text)[:300]}"]}

    bets = []
    erros = []
    now = datetime.now(timezone.utc).isoformat()

    for i, item in enumerate(items):
        try:
            odds = float(item.odds)
            stake = float(item.stake)
            resultado = item.resultado

            # Calcula lucro/prejuízo
            if resultado == "ganhou":
                lp = round((odds - 1) * stake, 2)
            elif resultado == "perdeu":
                lp = round(-stake, 2)
            elif resultado == "void":
                lp = 0.0
            else:
                lp = None

            # Data sempre = dia do upload (não a data da aposta na imagem)
            data_raw = datetime.now().strftime("%Y-%m-%d")

            bet_id = str(uuid.uuid4())
            bets.append({
                "bet_id":       bet_id,
                "uid":          "",           # será preenchido pelo router
                "partida":      item.partida or "Desconhecido",
                "descricao":    item.descricao,
                "tipo_aposta":  item.tipo_aposta,
                "odds":         odds,
                "stake":        stake,
                "data":         data_raw,
                "resultado":    resultado,
                "lucro_prejuizo": lp,
                "importado_de": "screenshot",
                "criado_em":    now,
            })
        except Exception as e:
            erros.append(f"Aposta {i+1}: {e}")

    return {"bets": bets, "erros": erros}
