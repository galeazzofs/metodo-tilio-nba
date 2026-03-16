"""
Gemini Vision parser — interpreta prints de histórico de apostas (ex: bet365)
e retorna uma lista estruturada de apostas.

Requer a variável de ambiente GEMINI_API_KEY.
Usa o modelo gemini-1.5-flash (gratuito: 1500 req/dia).
"""
import os
import uuid
import json
import re
from datetime import datetime, timezone

import google.generativeai as genai

_PROMPT = """
Você vai receber uma imagem de um histórico de apostas esportivas (pode ser da bet365 ou outra casa).
Extraia TODAS as apostas visíveis e retorne um JSON válido (somente JSON, sem markdown, sem texto extra).

Formato esperado — um array de objetos:
[
  {
    "partida":     "Time A vs Time B",
    "descricao":   "Vencedor - Time A",
    "tipo_aposta": "Vencedor",
    "odds":        1.85,
    "stake":       50.00,
    "data":        "2024-03-15",
    "resultado":   "ganhou"
  },
  ...
]

Regras:
- "tipo_aposta" deve ser um dos: Vencedor, Handicap, Totais, Jogador, Outro
- "resultado" deve ser um dos: ganhou, perdeu, pendente, void
- Se a imagem mostrar termos em inglês como "Won" → "ganhou", "Lost" → "perdeu", "Open" → "pendente", "Void" → "void"
- "data" deve ser no formato YYYY-MM-DD; se aparecer apenas dia/mês, use o ano atual
- "odds" e "stake" devem ser números decimais (ponto como separador)
- Se algum campo não estiver visível, use valores padrão: tipo_aposta="Outro", resultado="pendente"
- Retorne [] se não encontrar nenhuma aposta
"""


def parse_screenshot(image_bytes: bytes, mime_type: str = "image/jpeg") -> dict:
    """
    Envia a imagem para o Gemini 1.5 Flash e retorna:
    {
        "bets": [...],   # lista de dicts prontos para salvar
        "erros": [...]   # mensagens de erro/avisos
    }
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return {"bets": [], "erros": ["GEMINI_API_KEY não configurada no servidor."]}

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")

    img_part = {"mime_type": mime_type, "data": image_bytes}

    try:
        response = model.generate_content([_PROMPT, img_part])
        raw = response.text.strip()
    except Exception as e:
        return {"bets": [], "erros": [f"Erro ao chamar Gemini API: {e}"]}

    # Tenta extrair JSON mesmo que venha dentro de ```json ... ```
    json_match = re.search(r"\[[\s\S]*\]", raw)
    if not json_match:
        return {"bets": [], "erros": [f"Resposta inesperada do Gemini: {raw[:300]}"]}

    try:
        items = json.loads(json_match.group())
    except json.JSONDecodeError as e:
        return {"bets": [], "erros": [f"JSON inválido retornado pelo Gemini: {e}"]}

    bets = []
    erros = []
    now = datetime.now(timezone.utc).isoformat()
    ano_atual = datetime.now().year

    for i, item in enumerate(items):
        try:
            odds  = float(item.get("odds", 1.0))
            stake = float(item.get("stake", 0.0))
            resultado = str(item.get("resultado", "pendente")).lower()

            # Calcula lucro/prejuízo
            if resultado == "ganhou":
                lp = round((odds - 1) * stake, 2)
            elif resultado == "perdeu":
                lp = round(-stake, 2)
            elif resultado == "void":
                lp = 0.0
            else:
                lp = None

            # Normaliza data
            data_raw = str(item.get("data", ""))
            # Se formato for DD/MM ou DD/MM/AAAA, converte
            if re.match(r"\d{2}/\d{2}$", data_raw):
                data_raw = f"{ano_atual}-{data_raw[3:5]}-{data_raw[:2]}"
            elif re.match(r"\d{2}/\d{2}/\d{4}$", data_raw):
                data_raw = f"{data_raw[6:]}-{data_raw[3:5]}-{data_raw[:2]}"
            elif re.match(r"\d{2}/\d{2}/\d{2}$", data_raw):
                data_raw = f"20{data_raw[6:]}-{data_raw[3:5]}-{data_raw[:2]}"

            bet_id = str(uuid.uuid4())
            bets.append({
                "bet_id":       bet_id,
                "uid":          "",           # será preenchido pelo router
                "partida":      str(item.get("partida", "Desconhecido")),
                "descricao":    str(item.get("descricao", "")),
                "tipo_aposta":  str(item.get("tipo_aposta", "Outro")),
                "odds":         odds,
                "stake":        stake,
                "data":         data_raw or datetime.now().strftime("%Y-%m-%d"),
                "resultado":    resultado,
                "lucro_prejuizo": lp,
                "importado_de": "screenshot",
                "criado_em":    now,
            })
        except Exception as e:
            erros.append(f"Aposta {i+1}: {e}")

    return {"bets": bets, "erros": erros}
