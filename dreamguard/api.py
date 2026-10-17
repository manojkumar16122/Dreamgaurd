"""FastAPI backend + static dashboard. Run: uvicorn dreamguard.api:app --reload"""
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .benchmark import run_benchmark
from .compiler import get_compressor
from .engine import MemoryEngine
from .live import LiveDemo

load_dotenv()
STATIC = Path(__file__).resolve().parent / "static"

app = FastAPI(title="DreamGuard", version="0.1.0")
app.mount("/static", StaticFiles(directory=STATIC), name="static")

_state = {"engine": None, "turn": 0}


def _engine() -> MemoryEngine:
    if _state["engine"] is None:
        _state["engine"] = MemoryEngine(get_compressor(), destructive=False)
    return _state["engine"]


class Episode(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.post("/api/record")
def record(ep: Episode):
    _state["turn"] += 1
    _engine().record(_state["turn"], ep.content)
    return {"turn": _state["turn"]}


@app.post("/api/dream")
def dream():
    try:
        fact = _engine().dream()
    except Exception as e:  # e.g. missing GROQ key / network error
        raise HTTPException(500, f"Compression failed: {e}")
    return {"fact": fact}


@app.post("/api/rollback")
def rollback():
    return {"rolled_back": _engine().rollback()}


@app.post("/api/reset")
def reset():
    _state.update(engine=None, turn=0)
    return {"ok": True}


@app.post("/api/demo/seed")
def seed(n: int = 10):
    eng = _engine()
    for _ in range(n):
        _state["turn"] += 1
        t = _state["turn"]
        eng.record(t, f"param_{t}={(t * 7919) % 90000 + 10000}")
    return {"turn": _state["turn"]}


@app.get("/api/memory")
def memory():
    return _engine().snapshot()


@app.get("/api/benchmark")
def benchmark(seed: int = 42, retention: float = 0.7, auto_rollback: bool = False,
              rollback_at: int | None = 40):
    return run_benchmark(seed=seed, retention=retention, auto_rollback=auto_rollback,
                         rollback_at=None if auto_rollback else rollback_at)


# ---- live demo (real Groq compression + Groq question answering) ----------
_live: dict = {"demo": None}


def _demo() -> LiveDemo:
    if _live["demo"] is None:
        raise HTTPException(400, "Click 'Load scenario' first.")
    return _live["demo"]


def _guard(fn):
    try:
        return fn()
    except HTTPException:
        raise
    except Exception as e:  # missing key, rate limit, network, bad JSON...
        raise HTTPException(502, f"Groq error: {e}")


@app.get("/live")
def live_page():
    return FileResponse(STATIC / "live.html")


@app.post("/api/live/start")
def live_start():
    _live["demo"] = _guard(LiveDemo)
    return _live["demo"].state()


@app.post("/api/live/dream")
def live_dream():
    d = _demo()
    _guard(d.dream)
    return d.state()


@app.post("/api/live/rollback")
def live_rollback():
    d = _demo()
    d.rollback()
    return d.state()


@app.post("/api/live/evaluate")
def live_evaluate(label: str = "check"):
    d = _demo()
    _guard(lambda: d.evaluate(label[:40]))
    return d.state()


@app.get("/api/live/state")
def live_state():
    return _demo().state()
