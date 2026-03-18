import os
import sys
import threading
import uvicorn
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from deps import init_firebase, require_auth
from bets.router import router as bets_router

# ---------------------------------------------------------------------------
# Firebase init
# ---------------------------------------------------------------------------
init_firebase()

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI()

if os.environ.get("ENV") == "development":
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:8000"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(bets_router)

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
        pass


def _run_analysis():
    log_stream = _LogStream()
    original_stdout = sys.stdout
    sys.stdout = log_stream

    try:
        from scrapers.nba import get_todays_games
        from scrapers.rotowire import get_projected_lineups
        from scrapers.fantasypros import get_defense_vs_position
        from scrapers.odds import get_event_ids, get_player_lines
        from analysis.engine import run_analysis

        print("Buscando jogos de hoje...")
        games = get_todays_games()

        if not games:
            print("Nenhum jogo hoje.")
            with state_lock:
                analysis_state["status"] = "done"
                analysis_state["results"] = []
            return

        print(f"  {len(games)} jogos esta noite")

        print("Buscando lineups projetados (RotoWire)...")
        lineups = get_projected_lineups()
        print(f"  {len(lineups)} times carregados")

        print("Buscando Defesa por Posição (FantasyPros)...")
        dvp = get_defense_vs_position()
        print("  Concluído")

        print("Rodando análise...")
        candidates = run_analysis(games, lineups, dvp)
        print(f"  {len(candidates)} candidato(s) encontrado(s)")

        print("Buscando linhas de apostas (The Odds API)...")
        event_ids = get_event_ids(games)
        lines = get_player_lines(candidates, event_ids)
        for c in candidates:
            c["line"] = lines.get(c["player"])

        with state_lock:
            analysis_state["status"] = "done"
            analysis_state["results"] = candidates

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
