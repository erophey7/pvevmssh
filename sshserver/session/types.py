"""Core types and dataclasses for the session layer."""

from dataclasses import dataclass, field
from typing import Dict, Any
import uuid
import time


@dataclass
class SessionInfo:
    """
    Represents an active SSH session.
    """
    uuid: str = field(default_factory=lambda: str(uuid.uuid4()))
    username: str = ""
    client_addr: str = ""
    term_type: str = ""
    term_width: int = 80
    term_height: int = 24
    start_time: float = field(default_factory=time.time)
    extra: Dict[str, Any] = field(default_factory=dict)