"""
scrapers/telegram.py — Envia notificação de análise para grupo do Telegram.

Usa Telegram Bot API (HTTP puro, sem SDK).
Requer env vars: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
"""
import os
import requests

TELEGRAM_API = "https://api.telegram.org"

RATING_EMOJI = {
    "BEST OF THE NIGHT": "🔥",
    "VERY FAVORABLE":    "⚡",
    "FAVORABLE":         "✅",
}


def _get_config():
    token   = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID devem estar configurados. "
            "Crie um bot via @BotFather e adicione ao grupo."
        )
    return token, chat_id


def send_analysis(candidates: list, date_str: str, game_count: int) -> bool:
    """
    Envia resumo da análise do dia para o grupo do Telegram.

    Args:
        candidates: lista de dicts retornada por run_analysis() (já com 'line')
        date_str:   string da data no formato YYYY-MM-DD
        game_count: número de jogos na noite

    Returns:
        True se enviado com sucesso, False caso contrário.
    """
    try:
        token, chat_id = _get_config()
    except RuntimeError as e:
        print(f"  [telegram] {e}")
        return False

    msg = _format_message(candidates, date_str, game_count)

    try:
        resp = requests.post(
            f"{TELEGRAM_API}/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": msg,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=10,
        )
        resp.raise_for_status()
        print(f"  [telegram] Mensagem enviada para o grupo ✓")
        return True
    except requests.exceptions.RequestException as e:
        print(f"  [telegram] AVISO: falha ao enviar mensagem — {e}")
        return False


def _format_message(candidates: list, date_str: str, game_count: int) -> str:
    """Formata a mensagem HTML para o Telegram."""
    day_fmt = _fmt_date(date_str)

    if not candidates:
        return (
            f"🏀 <b>SCOUT · {day_fmt}</b>\n"
            f"<i>{game_count} jogos esta noite</i>\n\n"
            f"Nenhuma jogada favorável encontrada hoje."
        )

    lines = [
        f"🏀 <b>SCOUT · {day_fmt}</b>",
        f"<i>{game_count} jogos · {len(candidates)} jogada(s) destacada(s)</i>",
        "",
    ]

    for i, p in enumerate(candidates, start=1):
        emoji  = RATING_EMOJI.get(p.get("rating", ""), "•")
        rating = p.get("rating", "")
        player = p.get("player", "?")
        pos    = p.get("position", "")
        team   = p.get("team", "")
        game   = p.get("game", "")
        line   = p.get("line")
        line_str = f"{line} pts" if line is not None else "N/A"

        lines.append(f"{emoji} <b>#{i} {player}</b> ({pos}) — {team}")
        lines.append(f"   <code>{rating}</code>")
        lines.append(f"   Jogo: {game} · Linha: <b>{line_str}</b>")

        # Até 2 sinais por jogador para não ficar longo demais
        signals = p.get("signals", [])
        for sig in signals[:2]:
            lines.append(f"   › {_truncate(sig, 80)}")

        lines.append("")

    lines.append("<i>Análise gerada automaticamente pelo SCOUT.</i>")
    return "\n".join(lines)


def _fmt_date(date_str: str) -> str:
    """'2026-03-18' → '18/03/2026'"""
    try:
        from datetime import datetime
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        return date_str


def _truncate(text: str, max_len: int) -> str:
    return text if len(text) <= max_len else text[:max_len - 1] + "…"


def send_error(error_msg: str, date_str: str) -> None:
    """Envia aviso de erro para o grupo (opcional — falha silenciosa)."""
    try:
        token, chat_id = _get_config()
    except RuntimeError:
        return

    msg = (
        f"⚠️ <b>SCOUT · Erro na análise de {_fmt_date(date_str)}</b>\n\n"
        f"<code>{_truncate(error_msg, 200)}</code>"
    )

    try:
        requests.post(
            f"{TELEGRAM_API}/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"},
            timeout=10,
        )
    except Exception:
        pass  # erro no erro: silencioso
