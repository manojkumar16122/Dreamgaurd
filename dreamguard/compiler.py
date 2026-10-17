"""Memory compressors ("dream" step).

A compressor turns a list of text lines (raw episodes and/or earlier digests)
into ONE compact digest string.

* HeuristicCompressor - offline, deterministic, intentionally lossy. Lets you
  reproduce the benchmark with no API key.
* GroqCompressor      - real LLM compression (optional, needs GROQ_API_KEY).
"""
import json
import os
import random
import re

_KV = re.compile(r"([A-Za-z_][\w]*)=([^\s;,]+)")


class HeuristicCompressor:
    """Keeps each `key=value` detail with probability `retention`; otherwise
    keeps only the key (the "gist"). Models the loss that happens when details
    are summarised away. Seeded, so runs are reproducible."""

    def __init__(self, retention: float = 0.7, seed: int = 0):
        self.retention = retention
        self.rng = random.Random(seed)

    def compress(self, lines: list[str]) -> str:
        entries: list[str] = []
        for line in lines:
            for token in re.split(r";\s*", line):
                matches = list(_KV.finditer(token))
                for m in matches:
                    key, value = m.groups()
                    keep = self.rng.random() < self.retention
                    entries.append(f"{key}={value}" if keep else key)
                if not matches:
                    bare = re.sub(r"^Turn \d+:\s*", "", token).strip()
                    if bare and re.fullmatch(r"[A-Za-z_]\w*", bare):
                        entries.append(bare)  # key already stripped in an earlier pass
        return "; ".join(entries)


class GroqCompressor:
    """LLM-based compression via Groq (llama-3.1-8b-instant by default)."""

    PROMPT = (
        "You are a memory consolidation engine for an AI agent. Compress the "
        "following memories into ONE short digest of at most {max_words} words, "
        "keeping the overall gist. Return ONLY JSON: {{\"fact\": \"...\"}}"
    )

    def __init__(self, model: str | None = None, max_words: int = 40):
        self.max_words = max_words
        model = model or os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")
        from groq import Groq  # lazy import so the package works without it

        key = os.environ.get("GROQ_API_KEY")
        if not key:
            raise RuntimeError("GROQ_API_KEY is not set")
        self.client = Groq(api_key=key)
        self.model = model

    def compress(self, lines: list[str]) -> str:
        res = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.PROMPT.format(max_words=self.max_words)},
                {"role": "user", "content": "\n".join(lines)},
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        return json.loads(res.choices[0].message.content)["fact"]


def get_compressor(kind: str | None = None):
    """kind: 'heuristic' (default) or 'groq'. Falls back to env COMPRESSOR."""
    kind = (kind or os.environ.get("COMPRESSOR", "heuristic")).lower()
    return GroqCompressor() if kind == "groq" else HeuristicCompressor()
