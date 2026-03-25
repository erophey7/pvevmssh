import contextvars
import uuid
from dataclasses import dataclass, field
from typing import Optional, Dict
import time

@dataclass
class SessionInfo:
    uuid: str = field(default_factory=lambda: str(uuid.uuid4()))
    username: str = ""
    client_addr: str = ""
    term_type: str = ""
    term_width: int = 0
    term_height: int = 0
    start_time: float = field(default_factory=time.time)
    extra: Dict = field(default_factory=dict)

current_session: contextvars.ContextVar[Optional[SessionInfo]] = contextvars.ContextVar('current_session', default=None)

def get_current_session() -> Optional[SessionInfo]:
    return current_session.get()

class SessionStore:
    _instance = None

    def __new__(cls):
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

    def list_all(self) -> list:
        return list(self._sessions.values())

    def count(self) -> int:
        return len(self._sessions)