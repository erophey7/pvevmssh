import asyncio
import logging

from sshserver.session import CommandHistory

logger = logging.getLogger(__name__)


class LineEditorCore:
    def __init__(self, terminal):
        self.terminal = terminal

        self._buffer: list[str] = []
        self._cursor: int = 0

        self._last_layout = None

        self._history_draft: list[str] | None = None
        self._history_navigation_active: bool = False

        self.history = CommandHistory()
        self.echo: bool = True

        self._lock = asyncio.Lock()

        self._quoted_insert: bool = False

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