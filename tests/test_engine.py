from fastapi.testclient import TestClient

from dreamguard import HeuristicCompressor, MemoryEngine
from dreamguard.api import app
from dreamguard.benchmark import run_benchmark


def make(destructive=False, retention=0.0):
    return MemoryEngine(HeuristicCompressor(retention=retention, seed=1), destructive)


def test_dream_keeps_raw_and_links_provenance():
    e = make()
    e.record(1, "a=111"); e.record(2, "b=222")
    e.dream()
    s = e.snapshot()
    assert len(s["episodes"]) == 2 and len(s["facts"]) == 1
    assert len(s["provenance"]) == 2


def test_rollback_restores_exact_raw_context():
    e = make(retention=0.0)  # compression drops every value
    e.record(1, "a=111"); e.record(2, "b=222")
    truth = {"a": "111", "b": "222"}
    e.dream()
    assert e.evaluate(truth) == 0.0
    assert e.rollback() == 1
    assert e.evaluate(truth) == 1.0


def test_in_place_is_irreversible():
    e = make(destructive=True, retention=0.0)
    e.record(1, "a=111")
    e.dream()
    assert e.snapshot()["episodes"] == []
    assert e.rollback() == 0
    assert e.evaluate({"a": "111"}) == 0.0


def test_benchmark_shape_and_recovery():
    r = run_benchmark(seed=7)
    last = r["rows"][-1]
    assert len(r["rows"]) == 50
    assert last["raw_acc"] == 100.0
    assert last["dreamguard_acc"] == 100.0       # rolled back at turn 40
    assert last["in_place_acc"] < 100.0          # irreversible loss
    assert any(ev["type"] == "rollback" for ev in r["events"])


def test_benchmark_is_deterministic():
    assert run_benchmark(seed=3) == run_benchmark(seed=3)


def test_api_roundtrip():
    c = TestClient(app)
    c.post("/api/reset")
    c.post("/api/demo/seed?n=5")
    assert c.post("/api/dream").json()["fact"]
    assert c.post("/api/rollback").json()["rolled_back"] == 1
    assert len(c.get("/api/memory").json()["episodes"]) == 5
    assert c.get("/api/benchmark").json()["rows"]


# ---- live demo logic, with fake LLM calls (no network) ----------------------
from dreamguard.live import LiveDemo, QUESTIONS


class FakeCompressor:
    def compress(self, lines):  # lossy: keeps no specifics
        return "Agent did deploys, migrations and incident work."


def fake_answerer(memory, questions):
    # "LLM" that can only answer if the expected string is in its memory
    return [e if e in memory.lower() else "UNKNOWN" for _, e in QUESTIONS]


def test_live_demo_drop_and_recovery():
    d = LiveDemo(FakeCompressor(), fake_answerer)
    assert d.evaluate("baseline")["dreamguard"]["accuracy"] == 100
    d.dream()
    after = d.evaluate("after dream")
    assert after["in_place"]["accuracy"] == 0 and after["dreamguard"]["accuracy"] == 0
    d.rollback()
    final = d.evaluate("after rollback")
    assert final["dreamguard"]["accuracy"] == 100
    assert final["in_place"]["accuracy"] == 0
