"""MemoryEngine: record -> dream -> rollback.

Two modes:
  destructive=False (DreamGuard): raw episodes are never deleted. Every compressed
      fact keeps provenance links to its source episodes, so `rollback()` can
      deactivate the compressed memory and restore the exact raw context.
  destructive=True  (in-place baseline): episodes and old digests are deleted and
      re-compressed together on every dream, so loss compounds and cannot be undone.
"""
from .db import connect


class MemoryEngine:
    def __init__(self, compressor, destructive: bool = False, db_path: str = ":memory:"):
        self.compressor = compressor
        self.destructive = destructive
        self.conn = connect(db_path)

    # ---- write path -------------------------------------------------
    def record(self, turn: int, content: str) -> int:
        cur = self.conn.execute(
            "INSERT INTO episodes (turn, content) VALUES (?, ?)", (turn, content)
        )
        self.conn.commit()
        return cur.lastrowid

    def _uncovered_episodes(self):
        return self.conn.execute(
            """SELECT * FROM episodes WHERE id NOT IN (
                   SELECT p.episode_id FROM provenance p
                   JOIN semantic_memories m ON m.id = p.memory_id WHERE m.active = 1
               ) ORDER BY turn, id"""
        ).fetchall()

    def dream(self) -> str | None:
        """Compress uncovered episodes into a semantic fact."""
        episodes = self._uncovered_episodes()
        if not episodes:
            return None
        lines = [e["content"] for e in episodes]
        c = self.conn
        if self.destructive:
            old = [r["fact"] for r in c.execute("SELECT fact FROM semantic_memories WHERE active=1")]
            fact = self.compressor.compress(old + lines)
            c.execute("DELETE FROM semantic_memories")
            c.execute("DELETE FROM provenance")
            c.execute("DELETE FROM episodes")  # raw data is gone for good
            c.execute("INSERT INTO semantic_memories (fact) VALUES (?)", (fact,))
        else:
            fact = self.compressor.compress(lines)
            mem_id = c.execute("INSERT INTO semantic_memories (fact) VALUES (?)", (fact,)).lastrowid
            c.executemany(
                "INSERT INTO provenance (memory_id, episode_id) VALUES (?, ?)",
                [(mem_id, e["id"]) for e in episodes],
            )
        c.commit()
        return fact

    def rollback(self) -> int:
        """Deactivate compressed memory; raw episodes become the context again.
        Returns the number of facts rolled back. (No-op in destructive mode:
        the raw data no longer exists.)"""
        if self.destructive:
            return 0
        n = self.conn.execute("UPDATE semantic_memories SET active = 0 WHERE active = 1").rowcount
        self.conn.commit()
        return n

    # ---- read path --------------------------------------------------
    def context(self) -> str:
        """What the agent actually sees: active digests + not-yet-compressed raw episodes."""
        facts = [r["fact"] for r in self.conn.execute(
            "SELECT fact FROM semantic_memories WHERE active=1 ORDER BY id")]
        raw = [r["content"] for r in self._uncovered_episodes()]
        return "\n".join(facts + raw)

    def snapshot(self) -> dict:
        q = self.conn.execute
        return {
            "episodes": [dict(r) for r in q("SELECT id, turn, content FROM episodes ORDER BY turn, id")],
            "facts": [dict(r) for r in q("SELECT id, fact, active FROM semantic_memories ORDER BY id")],
            "provenance": [dict(r) for r in q("SELECT memory_id, episode_id FROM provenance")],
            "context_chars": len(self.context()),
        }

    def evaluate(self, truth: dict[str, str]) -> float:
        """Fraction of ground-truth `key=value` details recoverable from the context."""
        if not truth:
            return 1.0
        ctx = self.context()
        return sum(f"{k}={v}" in ctx for k, v in truth.items()) / len(truth)
