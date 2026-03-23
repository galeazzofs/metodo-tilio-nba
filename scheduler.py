"""
scheduler.py — APScheduler para análise automática diária.

Dois jobs:
  - daily_check: todo dia às 10h BRT, verifica se há jogos e agenda análise
  - run_scheduled_analysis: roda 1h antes do primeiro jogo, salva e notifica

Expõe trigger_now() para chamada via endpoint HTTP (escala para Render Cron / GitHub Actions).
"""
import threading
import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

logger = logging.getLogger(__name__)

# UTC-3 (Brasília — sem DST)
BRT = timezone(timedelta(hours=-3))

_scheduler: BackgroundScheduler | None = None
_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def init_scheduler():
    """Inicia o APScheduler. Deve ser chamado uma vez no startup do FastAPI."""
    global _scheduler
    if _scheduler and _scheduler.running:
        return

    _scheduler = BackgroundScheduler(timezone="America/Sao_Paulo")

    # Daily check: todo dia às 16h BRT
    _scheduler.add_job(
        daily_check,
        CronTrigger(hour=16, minute=0, timezone="America/Sao_Paulo"),
        id="daily_check",
        replace_existing=True,
        misfire_grace_time=3600,  # tolera até 1h de atraso (cold start do Render)
    )

    _scheduler.start()
    logger.info("[scheduler] APScheduler iniciado — daily_check às 16h BRT")


def trigger_now():
    """
    Trigger manual da análise (usado pelo endpoint /api/scheduler/trigger).
    Executa daily_check imediatamente em background.
    """
    t = threading.Thread(target=daily_check, daemon=True)
    t.start()
    return {"status": "triggered"}


def shutdown_scheduler():
    """Para o scheduler gracefully no shutdown do FastAPI."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

def daily_check():
    """
    Verifica jogos do dia. Se houver, agenda run_scheduled_analysis
    para 1 hora antes do primeiro tipoff.
    Chamado às 10h BRT ou via trigger manual.
    """
    from scrapers.nba import get_todays_games

    logger.info("[scheduler] daily_check iniciado")
    print("[scheduler] Verificando jogos de hoje...")

    try:
        games = get_todays_games()
    except Exception as e:
        logger.error(f"[scheduler] Erro ao buscar jogos: {e}")
        print(f"[scheduler] Erro ao buscar jogos: {e}")
        return

    if not games:
        print("[scheduler] Sem jogos hoje — nada a agendar.")
        return

    print(f"[scheduler] {len(games)} jogos encontrados.")

    # Pega horário do primeiro jogo (campo 'game_time_utc' se disponível)
    # Fallback: agenda para 1h a partir de agora se não conseguir extrair o horário
    tipoff_utc = _get_first_tipoff_utc(games)

    if tipoff_utc is None:
        # Fallback: roda imediatamente (útil para trigger manual)
        print("[scheduler] Horário do primeiro jogo não disponível — rodando agora.")
        _run_scheduled_analysis_thread(games)
        return

    run_at = tipoff_utc - timedelta(hours=1)
    now_utc = datetime.now(timezone.utc)

    if run_at <= now_utc:
        # Já passou da hora (checagem tardia ou trigger manual pós-deadline)
        print(f"[scheduler] T-60min já passou ({run_at.isoformat()}) — rodando agora.")
        _run_scheduled_analysis_thread(games)
        return

    print(f"[scheduler] Análise agendada para {run_at.astimezone(BRT).strftime('%H:%M')} BRT")

    if _scheduler and _scheduler.running:
        _scheduler.add_job(
            _run_scheduled_analysis_thread,
            DateTrigger(run_date=run_at),
            args=[games],
            id="scheduled_analysis",
            replace_existing=True,
        )


def _get_first_tipoff_utc(games: list) -> datetime | None:
    """
    Tenta extrair o horário UTC do primeiro jogo da lista.
    Usa scoreboardv2 com a data explícita de BRT para evitar puxar jogos
    do dia anterior após a meia-noite.
    Retorna None se não conseguir parsear.
    """
    try:
        from nba_api.stats.endpoints import scoreboardv2
        today_brt = datetime.now(BRT).strftime("%m/%d/%Y")
        board = scoreboardv2.ScoreboardV2(game_date=today_brt)
        header = board.game_header.get_data_frame()

        if header.empty:
            return None

        # GAME_DATE_EST is in format "2026-03-23T00:00:00" — use with game start time
        # The header has GAME_STATUS_TEXT with start time like "7:00 pm ET"
        # Fallback: use the game_date + a reasonable default (7pm ET = midnight UTC)
        for _, row in header.iterrows():
            status_text = str(row.get("GAME_STATUS_TEXT", ""))
            if "pm" in status_text.lower() or "am" in status_text.lower():
                try:
                    time_str = status_text.strip().upper().replace(" ET", "")
                    game_date = datetime.now(BRT).date()
                    from datetime import time as dt_time
                    t = datetime.strptime(time_str, "%I:%M %p").time()
                    # ET = UTC-5 (EST) or UTC-4 (EDT). Use UTC-4 during NBA season (March-April)
                    et = timezone(timedelta(hours=-4))
                    dt = datetime.combine(game_date, t, tzinfo=et)
                    return dt.astimezone(timezone.utc)
                except (ValueError, TypeError):
                    continue

        # Fallback: assume first game at 7pm ET
        game_date = datetime.now(BRT).date()
        from datetime import time as dt_time
        et = timezone(timedelta(hours=-4))
        return datetime.combine(game_date, dt_time(19, 0), tzinfo=et).astimezone(timezone.utc)

    except Exception as e:
        logger.warning(f"[scheduler] Não foi possível extrair tipoff: {e}")

    return None


def _run_scheduled_analysis_thread(games=None):
    """Wrapper para rodar a análise em thread separada (não bloqueia o scheduler)."""
    t = threading.Thread(
        target=run_scheduled_analysis,
        args=(games,),
        daemon=True,
    )
    t.start()


def run_scheduled_analysis(games=None):
    """
    Pipeline completo:
      1. Busca dados (lineups, DvP, análise, linhas)
      2. Salva resultado no Firestore (coleção 'analyses')
      3. Envia notificação no Telegram
    """
    import sys
    from datetime import date

    today = date.today().isoformat()
    print(f"[scheduler] Iniciando análise automática — {today}")

    try:
        from scrapers.nba import get_todays_games
        from scrapers.rotowire import get_projected_lineups
        from scrapers.fantasypros import get_defense_vs_position
        from scrapers.odds import get_event_ids, get_player_lines
        from scrapers.telegram import send_analysis, send_error
        from analysis.engine import run_analysis

        if games is None:
            games = get_todays_games()

        if not games:
            print("[scheduler] Sem jogos — análise cancelada.")
            return

        print(f"  {len(games)} jogos esta noite")

        lineups = get_projected_lineups()
        print(f"  {len(lineups)} times carregados")

        dvp = get_defense_vs_position()
        print("  DvP carregado")

        candidates = run_analysis(games, lineups, dvp)
        print(f"  {len(candidates)} candidato(s) encontrado(s)")

        event_ids = get_event_ids(games)
        lines = get_player_lines(candidates, event_ids)
        for c in candidates:
            c["line"] = lines.get(c["player"])

        # Salva no Firestore
        _save_analysis_to_firestore(today, candidates, games)

        # Notifica Telegram
        send_analysis(candidates, today, len(games))

        print(f"[scheduler] Análise de {today} concluída e enviada ✓")

    except Exception as e:
        logger.error(f"[scheduler] Erro na análise automática: {e}")
        print(f"[scheduler] ERRO: {e}")
        try:
            from scrapers.telegram import send_error
            send_error(str(e), today)
        except Exception:
            pass


def _save_analysis_to_firestore(date_str: str, candidates: list, games: list):
    """Salva o resultado da análise no Firestore em analyses/{date_str}."""
    try:
        from firebase_admin import firestore
        db = firestore.client()
        doc = {
            "date": date_str,
            "ran_at": datetime.now(timezone.utc).isoformat(),
            "triggered_by": "scheduler",
            "game_count": len(games),
            "candidate_count": len(candidates),
            "results": candidates,
        }
        db.collection("analyses").document(date_str).set(doc)
        print(f"  [firestore] Análise de {date_str} salva ✓")
    except Exception as e:
        logger.warning(f"[scheduler] Falha ao salvar no Firestore: {e}")
        print(f"  [firestore] AVISO: não foi possível salvar — {e}")
