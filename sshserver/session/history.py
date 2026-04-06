"""Command history for line editor."""

import json
from typing import List, Optional, Literal

from helpers.globals import GlobalStore
from .manager import get_current_session
from .types import SessionInfo


ClearStore = Literal["runtime", "db", "all"]


class CommandHistory:
    """
    Ring buffer for command history with up/down navigation.
    Supports runtime + database sync with diff-save.
    """

    def __init__(self, max_size: int = 100, session: SessionInfo = None) -> None:
        self._history: List[str] = []
        self._max_size = max_size
        self._index: Optional[int] = None

        self._saved_in_db: List[str] = []

        self._session = session


    def add(self, command: str) -> None:
        command = command.strip()
        if command:
            self._history.append(command)

            if len(self._history) > self._max_size:
                self._history.pop(0)

        self._index = None

    def previous(self) -> Optional[str]:
        """Return previous command (↑)."""
        if not self._history:
            return None
        if self._index is None:
            self._index = len(self._history) - 1
        else:
            self._index = max(0, self._index - 1)
        return self._history[self._index]

    def next(self) -> Optional[str]:
        """Return next command (↓)."""
        if not self._history:
            return None
        if self._index is None:
            return None
        self._index += 1
        if self._index >= len(self._history):
            self._index = None
            return ""
        return self._history[self._index]

    def reset_index(self):
        self._index = None

    def all(self) -> List[str]:
        return list(self._history)

    # =========================================================
    # DB API
    # =========================================================

    async def load(self, username: str = None) -> None:
        """
        Load history from DB into runtime memory.
        """
        if username is None:
            if self._session is None:
                self._session = get_current_session()
            username = self._session.username

        db = GlobalStore.get().require("db")

        row = await db.fetch_one(
            """
            SELECT history
            FROM users
            WHERE username = ?
            """,
            (username,)
        )

        raw = "[]"
        if row:
            if isinstance(row, dict):
                raw = row.get("history", "[]") or "[]"
            else:
                raw = row[0] or "[]"

        try:
            data = json.loads(raw)
            if not isinstance(data, list):
                data = []
        except (json.JSONDecodeError, TypeError):
            data = []

        data = [str(x) for x in data if isinstance(x, str)]

        if len(data) > self._max_size:
            data = data[-self._max_size:]

        self._history = data.copy()
        self._saved_in_db = data.copy()
        self._index = None


    async def save(self, username: str = None) -> None:
        """
        Save runtime history to DB using diff strategy:
        - save full diff in one UPDATE if possible
        - full rewrite if history changed in a non-append way
        """
        db = GlobalStore.get().require("db")

        if username is None:
            if self._session is None:
                self._session = get_current_session()
            username = self._session.username

        current = self._history[-self._max_size:]
        saved = self._saved_in_db[-self._max_size:]

        if current == saved:
            return

        async with db.transaction():
            # saved является префиксом current -> можно сохранить diff одним запросом
            if self._is_prefix(saved, current):
                diff = current[len(saved):]

                if diff:
                    merged = saved + diff

                    # дополнительная защита по размеру
                    if len(merged) > self._max_size:
                        merged = merged[-self._max_size:]

                    await db.execute(
                        """
                        UPDATE users
                        SET history = ?
                        WHERE username = ?
                        """,
                        (json.dumps(merged, ensure_ascii=False), username)
                    )

            else:
                # история изменилась не только append-ом
                await self._rewrite_history(username, current)

        self._saved_in_db = current.copy()

    async def clear(self, username: str = None, store: ClearStore = "all") -> None:
        """
        Clear command history.

        store:
            - "runtime" -> clear only in-memory history
            - "db"      -> clear only database history
            - "all"     -> clear both
        """
        db = GlobalStore.get().require("db")

        if username is None:
            if self._session is None:
                self._session = get_current_session()
            username = self._session.username

        if store in ("runtime", "all"):
            self._history.clear()
            self._index = None

        if store in ("db", "all"):
            async with db.transaction():
                await db.execute(
                    """
                    UPDATE users
                    SET history = '[]'
                    WHERE username = ?
                    """,
                    (username,)
                )
            self._saved_in_db = []

    # =========================================================
    # Internal helpers
    # =========================================================

    async def _rewrite_history(self, username: str, history: List[str]) -> None:
        """
        Fully rewrite DB history JSON.
        """
        db = GlobalStore.get().require("db")

        payload = json.dumps(history, ensure_ascii=False)

        await db.execute(
            """
            UPDATE users
            SET history = ?
            WHERE username = ?
            """,
            (payload, username)
        )

    @staticmethod
    def _is_prefix(old: List[str], new: List[str]) -> bool:
        """
        True if old is a prefix of new.
        """
        if len(old) > len(new):
            return False
        return old == new[:len(old)]