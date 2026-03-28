"""
PVE SSH Server Core Package

Exposes public API for the server, session, and terminal layers.
"""

from .server import PVESSHServer, SSHServerRunner
from .auth import authenticate
from .handlers import handle_client
from .dispatcher import CommandDispatcher

# Session layer
from .session import (
    SessionInfo,
    SessionStore,
    get_current_session,
    current_session,
    UserEnvironment,
    CommandHistory,
    create_session,
    run_session,
)

# Terminal layer
from .terminal import (
    Terminal,
    InputHandler,
    OutputHandler,
    PTYHandler,
    LineEditor,
    MouseEvent,
    MouseHandler
)

__all__ = [
    # Core server
    "PVESSHServer",
    "SSHServerRunner",
    "authenticate",
    "handle_client",
    "CommandDispatcher",

    # Session
    "SessionInfo",
    "SessionStore",
    "get_current_session",
    "current_session",
    "UserEnvironment",
    "CommandHistory",
    "create_session",
    "run_session",

    # Terminal
    "Terminal",
    "InputHandler",
    "OutputHandler",
    "PTYHandler",
    "LineEditor",
    "MouseEvent",
    "MouseHandler"
]