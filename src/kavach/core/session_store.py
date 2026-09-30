"""Bounded in-memory storage for redaction token maps."""

from __future__ import annotations

import secrets
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field


class SessionLimitError(ValueError):
    """Raised when a token map exceeds the configured memory limit."""


class SessionNotFoundError(KeyError):
    """Raised when a session is missing or expired."""


@dataclass
class _Session:
    token_map: dict[str, str]
    expires_at: float
    timer: threading.Timer | None = field(default=None, repr=False)


class SessionStore:
    """Store token maps in memory with fixed TTL and least-recently-used eviction."""

    def __init__(self, max_sessions: int, max_session_bytes: int, ttl_seconds: int) -> None:
        if max_sessions < 1 or max_session_bytes < 1 or ttl_seconds < 1:
            raise ValueError("Session limits must be positive")
        self.max_sessions = max_sessions
        self.max_session_bytes = max_session_bytes
        self.ttl_seconds = ttl_seconds
        self._sessions: OrderedDict[str, _Session] = OrderedDict()
        self._lock = threading.RLock()

    def create(self, token_map: dict[str, str]) -> str:
        size_bytes = sum(
            len(token.encode("utf-8")) + len(value.encode("utf-8"))
            for token, value in token_map.items()
        )
        if size_bytes > self.max_session_bytes:
            raise SessionLimitError("Token map exceeds the per-session memory limit")

        with self._lock:
            self._remove_expired_locked()
            while len(self._sessions) >= self.max_sessions:
                oldest_id = next(iter(self._sessions))
                self._remove_locked(oldest_id)

            session_id = secrets.token_urlsafe(32)
            while session_id in self._sessions:
                session_id = secrets.token_urlsafe(32)

            expires_at = time.monotonic() + self.ttl_seconds
            session = _Session(token_map=dict(token_map), expires_at=expires_at)
            timer = threading.Timer(self.ttl_seconds, self._expire, args=(session_id, expires_at))
            timer.daemon = True
            session.timer = timer
            self._sessions[session_id] = session
            timer.start()
            return session_id

    def get(self, session_id: str) -> dict[str, str]:
        with self._lock:
            self._remove_expired_locked()
            session = self._sessions.get(session_id)
            if session is None:
                raise SessionNotFoundError(session_id)
            self._sessions.move_to_end(session_id)
            return dict(session.token_map)

    def delete(self, session_id: str) -> bool:
        with self._lock:
            return self._remove_locked(session_id)

    def clear(self) -> None:
        with self._lock:
            for session_id in list(self._sessions):
                self._remove_locked(session_id)

    def _expire(self, session_id: str, expires_at: float) -> None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None or session.expires_at != expires_at:
                return
            remaining = expires_at - time.monotonic()
            if remaining > 0:
                timer = threading.Timer(remaining, self._expire, args=(session_id, expires_at))
                timer.daemon = True
                session.timer = timer
                timer.start()
                return
            self._remove_locked(session_id)

    def _remove_expired_locked(self) -> None:
        now = time.monotonic()
        expired = [
            session_id
            for session_id, session in self._sessions.items()
            if session.expires_at <= now
        ]
        for session_id in expired:
            self._remove_locked(session_id)

    def _remove_locked(self, session_id: str) -> bool:
        session = self._sessions.pop(session_id, None)
        if session is None:
            return False
        if session.timer is not None:
            session.timer.cancel()
        session.token_map.clear()
        return True
