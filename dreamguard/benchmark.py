"""Synthetic detail-retention benchmark.

Each turn the agent records an episode containing one exact detail
(`param_7=48213`). Every `dream_every` turns the memory is compressed. After
each turn we probe recall of ALL details seen so far (exact match against the
agent's visible context). No LLM is involved, so results are deterministic.

Systems compared:
  raw         - never compresses (accuracy reference; context grows unbounded)
  in_place    - compresses by rewriting memory, raw data deleted
  dreamguard  - same compressor, raw data kept. Rolls back either manually at
                `rollback_at` (default: turn 40, for a visible drop-and-recovery
                demo) or automatically when probe accuracy < threshold
                (`auto_rollback=True`). Dreaming then pauses for `cooldown` turns.
"""
import json
import random
import sys

from .compiler import HeuristicCompressor
from .engine import MemoryEngine


def run_benchmark(turns: int = 50, dream_every: int = 10, retention: float = 0.7,
                  threshold: float = 0.85, cooldown: int = 15, seed: int = 42,
                  auto_rollback: bool = False, rollback_at: int | None = 40) -> dict:
    rng = random.Random(seed)
    mk = lambda destructive: MemoryEngine(HeuristicCompressor(retention, seed), destructive)
    systems = {"raw": mk(False), "in_place": mk(True), "dreamguard": mk(False)}
    truth: dict[str, str] = {}
    rows, events = [], []
    paused_until = 0

    for t in range(1, turns + 1):
        key, val = f"param_{t}", str(rng.randint(10000, 99999))
        truth[key] = val
        for eng in systems.values():
            eng.record(t, f"{key}={val}")

        if t % dream_every == 0:
            systems["in_place"].dream()
            if t >= paused_until:
                systems["dreamguard"].dream()
                events.append({"turn": t, "type": "dream"})

        dg = systems["dreamguard"]
        manual = rollback_at is not None and t == rollback_at
        auto = auto_rollback and t >= paused_until and dg.evaluate(truth) < threshold
        if manual or auto:
            dg.rollback()
            paused_until = t + cooldown
            events.append({"turn": t, "type": "rollback"})

        rows.append({
            "turn": t,
            **{f"{n}_acc": round(100 * e.evaluate(truth), 1) for n, e in systems.items()},
            **{f"{n}_chars": len(e.context()) for n, e in systems.items()},
        })

    return {"config": {"turns": turns, "dream_every": dream_every, "retention": retention,
                       "threshold": threshold, "cooldown": cooldown, "seed": seed,
                       "auto_rollback": auto_rollback, "rollback_at": rollback_at},
            "rows": rows, "events": events}


if __name__ == "__main__":
    auto = "--auto" in sys.argv
    res = run_benchmark(auto_rollback=auto, rollback_at=None if auto else 40)
    print(f"{'turn':>4} {'raw':>6} {'in_place':>9} {'dreamguard':>11}")
    for r in res["rows"]:
        if r["turn"] % 5 == 0:
            print(f"{r['turn']:>4} {r['raw_acc']:>5}% {r['in_place_acc']:>8}% {r['dreamguard_acc']:>10}%")
    print("events:", res["events"])
    if "--json" in sys.argv:
        with open("benchmark_results.json", "w") as f:
            json.dump(res, f, indent=2)
