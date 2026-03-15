import os
import sys
import threading
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

app = FastAPI()

# ---------------------------------------------------------------------------
# Single-user in-memory state
# ---------------------------------------------------------------------------

analysis_state = {
    "status": "idle",   # idle | running | done | error
    "logs": [],
    "results": [],
    "error": None,
}
state_lock = threading.Lock()


class _LogStream:
    """Redirects print() output into analysis_state["logs"]."""

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
        from analysis.engine import run_analysis

        print("Fetching today's games...")
        games = get_todays_games()

        if not games:
            print("No games today.")
            with state_lock:
                analysis_state["status"] = "done"
                analysis_state["results"] = []
            return

        print(f"  {len(games)} games tonight")

        print("Fetching projected lineups (RotoWire)...")
        lineups = get_projected_lineups()
        print(f"  {len(lineups)} teams loaded")

        print("Fetching Defense vs Position (FantasyPros)...")
        dvp = get_defense_vs_position()
        print("  Done")

        print("Running analysis...")
        candidates = run_analysis(games, lineups, dvp)
        print(f"  Found {len(candidates)} candidate(s)")

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
# API routes
# ---------------------------------------------------------------------------

@app.post("/api/run")
def start_analysis():
    with state_lock:
        if analysis_state["status"] == "running":
            return JSONResponse({"error": "Analysis already running"}, status_code=400)
        analysis_state["status"] = "running"
        analysis_state["logs"] = []
        analysis_state["results"] = []
        analysis_state["error"] = None

    thread = threading.Thread(target=_run_analysis, daemon=True)
    thread.start()
    return {"status": "started"}


@app.get("/api/status")
def get_status():
    with state_lock:
        return {
            "status": analysis_state["status"],
            "logs": list(analysis_state["logs"]),
            "results": analysis_state["results"],
            "error": analysis_state["error"],
        }


@app.post("/api/reset")
def reset():
    with state_lock:
        if analysis_state["status"] == "running":
            return JSONResponse({"error": "Cannot reset while running"}, status_code=400)
        analysis_state["status"] = "idle"
        analysis_state["logs"] = []
        analysis_state["results"] = []
        analysis_state["error"] = None
    return {"status": "reset"}


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
