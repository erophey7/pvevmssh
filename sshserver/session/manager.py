"""Session storage and context management."""

import contextvars
from typing import Optional, Dict

from .types import SessionInfo

current_session: contextvars.ContextVar[Optional[SessionInfo]] = contextvars.ContextVar(
    'current_session', default=None
)


def get_current_session() -> Optional[SessionInfo]:
    """Return the current session from context."""
    return current_session.get()


class SessionStore:
    """
    Singleton store of all active sessions.
    """

    _instance: Optional["SessionStore"] = None
    _sessions: Dict[str, SessionInfo]

    def __new__(cls) -> "SessionStore":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._sessions = {}
        return cls._instance

    def add(self, session: SessionInfo) -> None:
        self._sessions[session.uuid] = session

    def remove(self, uuid: str) -> None:
        self._sessions.pop(uuid, None)

    def get(self, uuid: str) -> Optional[SessionInfo]:
        return self._sessions.get(uuid)

    def list_all(self) -> list[SessionInfo]:
        return list(self._sessions.values())

    def count(self) -> int:
        return len(self._sessions)