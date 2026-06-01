"""
Session memory for the AI Data Analyst Agent.

Thread-safe in-memory session store with TTL. For production, swap with
Redis / DynamoDB / a Cloudflare Durable Object.

A session holds:
  - Conversation history (turns of {role, content, sql, rows})
  - Dataset context (last N SQL queries + their results, for context)
  - User preferences (style, model)

TTL: sessions expire 1 hour after the last activity.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


SESSION_TTL_SECONDS = 60 * 60  # 1 hour
MAX_HISTORY_TURNS = 20        # rolling window
MAX_CONTEXT_SQL = 10          # last N SQL queries remembered


@dataclass
class Turn:
    role: str  # "user" | "assistant"
    content: str
    sql: Optional[str] = None
    rows: Optional[List[Dict[str, Any]]] = None
    ts: float = field(default_factory=time.time)


@dataclass
class Session:
    session_id: str
    turns: List[Turn] = field(default_factory=list)
    recent_sql: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_activity_at: float = field(default_factory=time.time)

    def touch(self) -> None:
        self.last_activity_at = time.time()

    def add_turn(self, turn: Turn) -> None:
        self.turns.append(turn)
        if len(self.turns) > MAX_HISTORY_TURNS:
            self.turns = self.turns[-MAX_HISTORY_TURNS:]
        if turn.sql:
            self.recent_sql.append(turn.sql)
            if len(self.recent_sql) > MAX_CONTEXT_SQL:
                self.recent_sql = self.recent_sql[-MAX_CONTEXT_SQL:]
        self.touch()

    def to_prompt_context(self) -> str:
        """Build a context string for the LLM to understand the conversation."""
        lines = []
        for t in self.turns[-MAX_HISTORY_TURNS:]:
            prefix = "USER" if t.role == "user" else "ASSISTANT"
            if t.sql:
                lines.append(f"{prefix}: {t.content}\n  SQL: {t.sql}")
            else:
                lines.append(f"{prefix}: {t.content}")
        return "\n".join(lines)


class SessionStore:
    """Thread-safe in-memory session store with TTL eviction."""

    def __init__(self, ttl_seconds: int = SESSION_TTL_SECONDS):
        self._sessions: Dict[str, Session] = {}
        self._lock = threading.Lock()
        self._ttl = ttl_seconds

    def get_or_create(self, session_id: str) -> Session:
        with self._lock:
            self._evict_expired()
            if session_id in self._sessions:
                sess = self._sessions[session_id]
                sess.touch()
                return sess
            sess = Session(session_id=session_id)
            self._sessions[session_id] = sess
            return sess

    def get(self, session_id: str) -> Optional[Session]:
        with self._lock:
            self._evict_expired()
            return self._sessions.get(session_id)

    def delete(self, session_id: str) -> bool:
        with self._lock:
            return self._sessions.pop(session_id, None) is not None

    def _evict_expired(self) -> None:
        cutoff = time.time() - self._ttl
        expired = [sid for sid, s in self._sessions.items() if s.last_activity_at < cutoff]
        for sid in expired:
            del self._sessions[sid]

    def stats(self) -> Dict[str, int]:
        with self._lock:
            return {
                "active_sessions": len(self._sessions),
                "ttl_seconds": self._ttl,
                "max_history_turns": MAX_HISTORY_TURNS,
            }


# Module-level singleton
store = SessionStore()
