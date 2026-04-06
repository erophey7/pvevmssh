import asyncio
import logging

from sshserver.session import CommandHistory, get_current_session
from helpers.globals import GlobalStore

logger = logging.getLogger(__name__)


class LineEditorCore:
    def __init__(self, terminal):
        self.terminal = terminal

        self._buffer: list[str] = []
        self._cursor: int = 0

        self._last_layout = None

        self._history_draft: list[str] | None = None
        self._history_navigation_active: bool = False

        self.history = None
        self.echo: bool = True

        self._lock = asyncio.Lock()

        self._quoted_insert: bool = False

        self.ensure()

    def _reset_state(self) -> None:
        self._buffer.clear()
        self._cursor = 0
        self._last_layout = None
        self._history_draft = None
        self._history_navigation_active = False
        self._quoted_insert = False
        self.history.reset_index()

    def current_line(self) -> str:
        return "".join(self._buffer)
    
    def ensure(self) -> None:
        session = get_current_session()
        config = GlobalStore.get().require("config")
        if session:
            self.history = session.extra.get(
                "history", 
                CommandHistory(
                    max_size=config.get("db.limits.history", 1000), 
                    session=session
                    )
            )