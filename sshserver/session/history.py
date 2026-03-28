"""Command history for line editor."""

import collections
from typing import List, Optional


class CommandHistory:
    """
    Ring buffer for command history with up/down navigation.
    """

    def __init__(self, max_size: int = 100):
        self._history: List[str] = []
        self._max_size = max_size
        self._index: Optional[int] = None

    def add(self, command: str):
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