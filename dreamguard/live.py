"""Live demo: real LLM compression + real LLM question answering.

Two engines receive the same episodes:
  * in-place  (destructive)  - what many agent frameworks do
  * dreamguard (reversible)  - raw episodes + provenance kept
After every step, an LLM answers a fixed question set using ONLY each engine's
current memory context, and answers are graded against known ground truth.
"""
import json
import os
from typing import Callable

from .compiler import GroqCompressor
from .engine import MemoryEngine

EPISODES = [
    "Deployed service billing-api v2.4.1 to cluster eu-west-3 at 14:20.",
    "Customer ticket #88213 was escalated by Priya Nair to the payments team.",
    "Database migration 0047_add_invoice_index took 312 seconds on host db-prod-07.",
    "The rate limit for the /v2/refunds endpoint was set to 450 requests per minute.",
    "Rollback of release r-1093 was approved by Tomas Berg after the error rate hit 6.8 percent.",
    "Staging redis cache runs on port 6391 with a 90 second TTL.",
    "Feature flag new_checkout_flow was enabled for 15 percent of users in Brazil.",
    "Incident INC-5521 root cause: expired TLS certificate on gateway-edge-02.",
    "Nightly backup job finished in 41 minutes and uploaded 118 GB to bucket acme-backups-eu.",
    "Load test peaked at 2,350 requests per second before p99 latency exceeded 900 ms.",
    "On-call engineer Lena Okafor acknowledged the PagerDuty alert in 3 minutes.",
    "Sprint 38 closed with 27 of 31 story points completed.",
]

QUESTIONS = [
    ("Which cluster was billing-api deployed to?", "eu-west-3"),
    ("Who escalated ticket #88213?", "priya nair"),
    ("How many seconds did migration 0047 take?", "312"),
    ("What is the rate limit (requests per minute) for /v2/refunds?", "450"),
    ("Who approved the rollback of release r-1093?", "tomas berg"),
    ("What port does the staging redis cache use?", "6391"),
    ("What percent of users in Brazil have new_checkout_flow enabled?", "15"),
    ("Which host had the expired TLS certificate in INC-5521?", "gateway-edge-02"),
]

ANSWER_PROMPT = (
    "You answer questions about an agent's past work using ONLY the MEMORY below. "
    "If the memory does not contain the exact answer, answer \"UNKNOWN\". Never guess. "
    "Reply ONLY with JSON: {{\"answers\": [\"...\", ...]}} with one short answer per "
    "question, in order.\n\nMEMORY:\n{memory}"
)


def groq_answerer() -> Callable[[str, list[str]], list[str]]:
    from groq import Groq

    key = os.environ.get("GROQ_API_KEY")
    if not key:
        raise RuntimeError("GROQ_API_KEY is not set (add it to .env)")
    client = Groq(api_key=key)
    model = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")

    def answer(memory: str, questions: list[str]) -> list[str]:
        res = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": ANSWER_PROMPT.format(memory=memory or "(empty)")},
                {"role": "user", "content": "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions))},
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )
        return [str(a) for a in json.loads(res.choices[0].message.content).get("answers", [])]

    return answer


class LiveDemo:
    def __init__(self, compressor=None, answerer=None):
        self.compressor = compressor or GroqCompressor()
        self.answerer = answerer or groq_answerer()
        self.in_place = MemoryEngine(self.compressor, destructive=True)
        self.guard = MemoryEngine(self.compressor, destructive=False)
        self.history: list[dict] = []
        for i, text in enumerate(EPISODES, 1):
            self.in_place.record(i, text)
            self.guard.record(i, text)

    def dream(self):
        self.in_place.dream()
        self.guard.dream()

    def rollback(self) -> int:
        return self.guard.rollback()

    def _grade(self, engine: MemoryEngine) -> dict:
        answers = self.answerer(engine.context(), [q for q, _ in QUESTIONS])
        answers += ["(no answer)"] * (len(QUESTIONS) - len(answers))
        rows = [{"question": q, "expected": e, "answer": a, "correct": e in a.lower()}
                for (q, e), a in zip(QUESTIONS, answers)]
        return {"accuracy": round(100 * sum(r["correct"] for r in rows) / len(rows)),
                "rows": rows, "context_chars": len(engine.context())}

    def evaluate(self, label: str) -> dict:
        entry = {"label": label, "in_place": self._grade(self.in_place),
                 "dreamguard": self._grade(self.guard)}
        self.history.append(entry)
        return entry

    def state(self) -> dict:
        return {
            "history": self.history,
            "in_place": {"context": self.in_place.context()},
            "dreamguard": {"context": self.guard.context(), **{
                k: v for k, v in self.guard.snapshot().items() if k in ("facts", "episodes")}},
        }
