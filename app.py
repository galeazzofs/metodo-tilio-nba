import os
import sys
import threading
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from deps import init_firebase, require_auth
from bets.router import router as bets_router
from routers.analyses import router as analyses_router
from scheduler import init_scheduler, shutdown_scheduler, trigger_now

# ---------------------------------------------------------------------------
# Firebase init
# ---------------------------------------------------------------------------
init_firebase()
init_scheduler()

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    shutdown_scheduler()

app = FastAPI(lifespan=lifespan)

if os.environ.get("ENV") == "development":
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:8000"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(bets_router)
app.include_router(analyses_router)

# ---------------------------------------------------------------------------
# Single-user in-memory analysis state
# ---------------------------------------------------------------------------
analysis_state = {
    "status": "idle",   # idle | running | done | error
    "logs": [],
    "results": [],
    "error": None,
}
state_lock = threading.Lock()


class _LogStream:
    """Redirects print() output into analysis_state['logs']."""

    def write(self, text):
        if text and text.strip():
            with state_lock:
                analysis_state["logs"].append(text.rstrip())

    def flush(self):
        pass  # nothing to flush; logs are already in the list


def _run_analysis():
    log_stream = _LogStream()
    original_stdout = sys.stdout
    sys.stdout = log_stream

    try:
        from datetime import datetime
        from analysis.pipeline import run_pipeline
        from scrapers.nba import BRT

        stats, games = run_pipeline()
        today = datetime.now(BRT).date().isoformat()

        with state_lock:
            analysis_state["status"] = "done"
            analysis_state["results"] = stats if stats else {}

        # Salva no Firestore (histórico de análises)
        if stats:
            try:
                from scheduler import _save_analysis_to_firestore
                _save_analysis_to_firestore(today, stats, games)
                from firebase_admin import firestore as _fs
                _fs.client().collection("analyses").document(today).update(
                    {"triggered_by": "manual"}
                )
            except Exception as _e:
                print(f"  [firestore] Aviso ao salvar análise manual: {_e}")

        # Notifica Telegram (melhor esforço — falha silenciosa)
        try:
            from scrapers.telegram import send_analysis
            send_analysis(stats or {}, today, len(games) if games else 0)
            print("  [telegram] Notificação enviada ✓")
        except Exception as _te:
            print(f"  [telegram] Aviso: não foi possível enviar — {_te}")

    except Exception as e:
        with state_lock:
            analysis_state["status"] = "error"
            analysis_state["error"] = str(e)

    finally:
        sys.stdout = original_stdout


# ---------------------------------------------------------------------------
# Analysis routes (all protected)
# ---------------------------------------------------------------------------

@app.post("/api/run")
def start_analysis(uid: str = Depends(require_auth)):
    with state_lock:
        if analysis_state["status"] == "running":
            return JSONResponse({"error": "Análise já em andamento"}, status_code=400)
        analysis_state["status"] = "running"
        analysis_state["logs"] = []
        analysis_state["results"] = []
        analysis_state["error"] = None

    thread = threading.Thread(target=_run_analysis, daemon=True)
    thread.start()
    return {"status": "iniciado"}


@app.get("/api/status")
def get_status(uid: str = Depends(require_auth)):
    with state_lock:
        return {
            "status": analysis_state["status"],
            "logs": list(analysis_state["logs"]),
            "results": analysis_state["results"],
            "error": analysis_state["error"],
        }


@app.post("/api/reset")
def reset(uid: str = Depends(require_auth)):
    with state_lock:
        if analysis_state["status"] == "running":
            return JSONResponse({"error": "Não é possível resetar durante a análise"}, status_code=400)
        analysis_state["status"] = "idle"
        analysis_state["logs"] = []
        analysis_state["results"] = []
        analysis_state["error"] = None
    return {"status": "resetado"}


@app.post("/api/scheduler/trigger")
def manual_trigger(uid: str = Depends(require_auth)):
    """
    Trigger manual da análise automática (para testes e Render Cron Job externo).
    Chama daily_check em background — retorna imediatamente.
    """
    result = trigger_now()
    return result


# ---------------------------------------------------------------------------
# Static files + HTML
# ---------------------------------------------------------------------------
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def index():
    return FileResponse("static/index.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port, reload=False)
