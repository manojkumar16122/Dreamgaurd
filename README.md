# 🛡️ DreamGuard

**Reversible memory compilation for AI agents.**

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](#) [![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE) [![Tests](https://img.shields.io/badge/tests-pytest-brightgreen)](#testing)

Long-running agents need to compress their memory ("dreaming" / consolidation) or the context window bloats. The common approach rewrites memory **in place**: once a detail is summarised away, it is gone for good.

DreamGuard compiles raw *episodic* memory into compact *semantic* memory like a build step: **the raw episodes are never deleted**, and every compressed fact is linked back to its source episodes. If recall quality drops, you **roll back** and the exact raw context is restored.

```
 record() ──► episodes (immutable)
                 │  dream()
                 ▼
         semantic_memories ──provenance──► episodes
                 │  rollback()
                 ▼
     compressed facts deactivated, raw context restored
```

## Demo

Run the dashboard and open <http://localhost:8000>. It plots detail-recall accuracy over 50 turns for three systems and lets you trigger a rollback:

| System | What it does | Behaviour in the demo |
|---|---|---|
| Full raw context (reference) | Never compresses | 100%, but context grows without bound |
| In-place dreaming | Rewrites memory, deletes raw data | Loss compounds, cannot recover |
| **DreamGuard** | Compresses, keeps raw + provenance | Same loss as in-place, then **recovers to 100%** on rollback |

> 📸 Demo Video `docs/DreamGaurd.mp4`

## Install

```bash
pip install dreamguard                 # core library, zero dependencies
pip install "dreamguard[server]"       # + dashboard, API and Groq support
pip install "dreamguard[groq]"         # + Groq compressor only
```

## Quick start

```bash
pip install "dreamguard[server]"
echo "GROQ_API_KEY=gsk_..." > .env     # only needed for the /live demo
dreamguard serve                       # open http://localhost:8000
dreamguard benchmark                   # offline simulation in the terminal
```

Development setup: `git clone ... && pip install -e ".[dev,server]" && pytest`.

### Use it as a library

```python
from dreamguard import MemoryEngine, HeuristicCompressor

mem = MemoryEngine(HeuristicCompressor(retention=0.7), destructive=False)
mem.record(1, "api_port=8421")
mem.record(2, "region=ap-south-1")

mem.dream()              # compress; raw episodes + provenance are kept
print(mem.context())     # what your agent would see (digest)
mem.rollback()           # back to exact raw episodes
print(mem.context())
```

### Live demo with a real LLM (Groq)

```bash
# .env
GROQ_API_KEY=gsk_...
```
Run `uvicorn dreamguard.api:app --reload`, open <http://localhost:8000/live>, then click:
**1 Load scenario → 2 Evaluate → 3 Dream → 2 Evaluate → 4 Rollback → 2 Evaluate.**

Groq compresses 12 engineering-log episodes into a short digest, then answers 8 factual questions (ports, ticket owners, hosts...) using *only* each system's remaining memory. Answers are graded against known ground truth. Both the in-place and DreamGuard engines get the same input; only DreamGuard can roll back. Set `GROQ_MODEL` to change the model (default `llama-3.1-8b-instant`).

Results are real LLM output, so they vary by model and run: a strong model may retain some details after compression. The rollback guarantee does not vary, because it restores the raw text.

### Real LLM compression (optional)

```bash
# .env
COMPRESSOR=groq
GROQ_API_KEY=gsk_...
```

Uses Groq's `llama-3.1-8b-instant` to produce the digest. Note: the built-in **benchmark** always uses the heuristic compressor so that its results are reproducible.

## How it works

| Table | Purpose |
|---|---|
| `episodes` | Raw, append-only memory (`turn`, `content`) |
| `semantic_memories` | Compressed digests, with an `active` flag |
| `provenance` | `memory_id → episode_id` links from each digest to its sources |

- `record(turn, content)` appends an episode.
- `dream()` compresses episodes not yet covered by an active digest.
- `rollback()` sets all digests to inactive. Their episodes become "uncovered" again, so `context()` returns the raw text.
- `context()` is what an agent reads: active digests plus any uncovered raw episodes.
- With `destructive=True` the engine mimics in-place dreaming: it deletes raw data and re-compresses digests together with new episodes, so loss compounds.

## Benchmark methodology (read this before quoting numbers)

The benchmark is a **synthetic simulation**, not a measurement of any production system:

1. Each turn records one exact detail, e.g. `param_7=48213`.
2. Every 10 turns the memory is compressed with a seeded lossy compressor that keeps each value with probability 0.7 and otherwise keeps only the key.
3. After every turn, **recall** = fraction of all details seen so far that appear verbatim (`key=value`) in the agent's visible context.

What this shows: *if* compression is lossy, an irreversible design loses information permanently, while a design that keeps raw data can restore it. What it does **not** show: how any specific LLM, product, or published system behaves. The absolute accuracy numbers come from the chosen retention parameter, not from real-world measurement.

**Known trade-off:** after a rollback, the agent context is raw again and therefore larger. The benefit of compression (smaller context) is traded for recall until the next dream.

## API

| Method | Path | Description |
|---|---|---|
| POST | `/api/record` | `{"content": "..."}` record an episode |
| POST | `/api/dream` | Compress uncovered episodes |
| POST | `/api/rollback` | Deactivate compressed memory |
| POST | `/api/reset` | Clear the live engine |
| POST | `/api/demo/seed?n=10` | Add demo episodes |
| GET | `/api/memory` | Episodes, facts, provenance, context size |
| GET | `/api/benchmark` | Run benchmark (`seed`, `retention`, `auto_rollback`, `rollback_at`) |

Interactive docs at `/docs`.

## Project layout

```
dreamguard/
├── dreamguard/
│   ├── db.py          # SQLite schema
│   ├── compiler.py    # Heuristic + Groq compressors
│   ├── engine.py      # record / dream / rollback / evaluate
│   ├── benchmark.py   # reproducible simulation
│   ├── live.py        # live demo: Groq compression + Groq QA grading
│   ├── api.py         # FastAPI app
│   ├── cli.py         # `dreamguard` command
│   └── static/        # dashboard (HTML + CSS + Chart.js, no build step)
├── tests/
└── pyproject.toml
```

## Testing

```bash
pip install -e ".[dev,server]"
pytest
```

## Roadmap

- [ ] Selective rollback (restore only the episodes behind a specific fact)
- [ ] Benchmark with real LLM compression and an LLM-answered QA task
- [ ] Pluggable storage backends (Postgres, vector DBs)
- [ ] Rollback triggers driven by task-level eval signals

## Contributing

Issues and PRs are welcome. Please run `pytest` before submitting.

## License

MIT, see [LICENSE](LICENSE). Built by [Manojkumar V](https://github.com/manojkumar16122).
