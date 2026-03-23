"""
scrapers/telegram.py — Envia notificacao de analise para grupo do Telegram.

Usa Telegram Bot API (HTTP puro, sem SDK).
Requer env vars: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
"""
import os
import requests

TELEGRAM_API = "https://api.telegram.org"

RATING_EMOJI = {
    "BEST OF THE NIGHT": "\U0001f525",
    "VERY FAVORABLE":    "\u26a1",
    "FAVORABLE":         "\u2705",
}

STAT_SECTIONS = [
    ("pts",      "\U0001f4ca PONTOS (PTS)"),
    ("ast",      "\U0001f3af ASSIST\u00caNCIAS (AST)"),
    ("reb",      "\U0001f3c0 REBOTES (REB)"),
    ("three_pt", "\U0001f4a7 CESTAS DE 3 (3PT)"),
]


def _get_config():
    token   = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID devem estar configurados. "
            "Crie um bot via @BotFather e adicione ao grupo."
        )
    return token, chat_id


def _send_message(token: str, chat_id: str, text: str) -> None:
    """Envia uma unica mensagem via Telegram Bot API."""
    resp = requests.post(
        f"{TELEGRAM_API}/bot{token}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=10,
    )
    resp.raise_for_status()


def send_analysis(stats: dict, date_str: str, game_count: int) -> bool:
    """
    Envia resumo da analise do dia para o grupo do Telegram.

    Args:
        stats:      dict com keys pts, ast, reb, three_pt — cada uma uma lista
                    de candidates retornada por run_analysis().
        date_str:   string da data no formato YYYY-MM-DD
        game_count: numero de jogos na noite

    Returns:
        True se enviado com sucesso, False caso contrario.
    """
    try:
        token, chat_id = _get_config()
    except RuntimeError as e:
        print(f"  [telegram] {e}")
        return False

    msg = _format_message(stats, date_str, game_count)

    try:
        if len(msg) <= 4000:
            _send_message(token, chat_id, msg)
        else:
            # Split: header first, then one message per non-empty section
            header = _format_header(date_str, game_count)
            _send_message(token, chat_id, header)
            for key, title in STAT_SECTIONS:
                candidates = stats.get(key, [])
                if not candidates:
                    continue
                section_text = _format_section(title, candidates)
                _send_message(token, chat_id, section_text)

        print("  [telegram] Mensagem enviada para o grupo")
        return True
    except requests.exceptions.RequestException as e:
        print(f"  [telegram] AVISO: falha ao enviar mensagem -- {e}")
        return False


def _format_header(date_str: str, game_count: int) -> str:
    day_fmt = _fmt_date(date_str)
    return f"\U0001f3c0 <b>SCOUT</b> \u00b7 {day_fmt}\n{game_count} jogos"


def _format_player(rank: int, c: dict) -> str:
    emoji  = RATING_EMOJI.get(c.get("rating", ""), "\u2022")
    player = c.get("player_name", c.get("player", ""))
    pos    = c.get("position", "")
    team   = c.get("team", "")
    game   = c.get("game", "")
    rating = c.get("rating", "")

    # Line: dict with "value" (new format) or plain number (old format)
    raw_line = c.get("line", {})
    if isinstance(raw_line, dict):
        line_val = raw_line.get("value")
    else:
        line_val = raw_line
    line_str = str(line_val) if line_val is not None else "N/A"

    parts = [
        f"{emoji} <b>#{rank} {player}</b> ({pos}) \u2014 {team}",
        f"   <code>{rating}</code>",
        f"   Jogo: {game} \u00b7 Linha: <b>{line_str}</b>",
    ]

    # Signals: new format (context.signal_descriptions) or old (signals list)
    signals = c.get("context", {}).get(
        "signal_descriptions", c.get("signals", [])
    )
    for sig in signals[:2]:
        parts.append(f"   \u203a {_truncate(sig, 80)}")

    return "\n".join(parts)


def _format_section(title: str, candidates: list) -> str:
    lines = [f"<b>{title}</b>", ""]
    for i, c in enumerate(candidates, start=1):
        lines.append(_format_player(i, c))
        lines.append("")
    return "\n".join(lines)


def _format_message(stats: dict, date_str: str, game_count: int) -> str:
    """Formata a mensagem HTML para o Telegram."""
    parts = [_format_header(date_str, game_count)]

    has_any = False
    for key, title in STAT_SECTIONS:
        candidates = stats.get(key, [])
        if not candidates:
            continue
        has_any = True
        parts.append("")
        parts.append(_format_section(title, candidates))

    if not has_any:
        parts.append("")
        parts.append("Nenhuma jogada favoravel encontrada hoje.")

    parts.append("")
    parts.append("<i>Analise gerada automaticamente pelo SCOUT.</i>")
    return "\n".join(parts)


def _fmt_date(date_str: str) -> str:
    """'2026-03-18' -> '18/03/2026'"""
    try:
        from datetime import datetime
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        return date_str


def _truncate(text: str, max_len: int) -> str:
    return text if len(text) <= max_len else text[:max_len - 1] + "\u2026"


def send_error(error_msg: str, date_str: str) -> None:
    """Envia aviso de erro para o grupo (opcional -- falha silenciosa)."""
    try:
        token, chat_id = _get_config()
    except RuntimeError:
        return

    msg = (
        f"\u26a0\ufe0f <b>SCOUT \u00b7 Erro na analise de {_fmt_date(date_str)}</b>\n\n"
        f"<code>{_truncate(error_msg, 200)}</code>"
    )

    try:
        _send_message(token, chat_id, msg)
    except Exception:
        pass  # erro no erro: silencioso
