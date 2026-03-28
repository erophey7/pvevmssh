import typing as t
import logging

from wcwidth import wcswidth
from sshserver.session import CommandHistory
from .types import EOF

logger = logging.getLogger(__name__)


class LineEditor:
    """
    Full line editor with history, word navigation, and shell‑like word classes.
    """

    def __init__(self, session_io):
        self.session_io = session_io

        self._chars: list[str] = []
        self._cursor: int = 0
        self.history = CommandHistory()

    ########## Public Methods ##########
    def reset(self) -> None:
        self._chars.clear()
        self._cursor = 0
        self.history.reset_index()

    async def feed_char(self, char: str) -> None:
        self._chars.insert(self._cursor, char)
        self._cursor += 1
        await self._redraw_line()

    async def enter(self) -> str:
        await self.session_io.output.output_bytes(b"\r\n")
        line = "".join(self._chars)

        if line.strip():
            self.history.add(line)

        return line

    async def ctrl_c(self) -> str:
        self._chars.clear()
        self._cursor = 0
        await self.session_io.output.output_bytes(b"^C\r\n")
        return ""

    async def ctrl_d(self) -> t.Optional[str]:
        if not self._chars:
            return EOF
        return None

    async def backspace(self) -> None:
        if self._cursor <= 0:
            return
        self._cursor -= 1
        self._chars.pop(self._cursor)
        await self._redraw_line()

    async def ctrl_backspace(self) -> None:
        """Delete word to the left (Ctrl+W)."""
        if self._cursor <= 0:
            return

        # Skip whitespace
        while self._cursor > 0 and self._char_class(self._chars[self._cursor - 1]) == "ws":
            self._cursor -= 1
            self._chars.pop(self._cursor)

        if self._cursor <= 0:
            await self._redraw_line()
            return

        # Delete contiguous block of same class
        cls = self._char_class(self._chars[self._cursor - 1])
        while self._cursor > 0 and self._char_class(self._chars[self._cursor - 1]) == cls:
            self._cursor -= 1
            self._chars.pop(self._cursor)

        await self._redraw_line()

    async def delete(self) -> None:
        if self._cursor >= len(self._chars):
            return
        self._chars.pop(self._cursor)
        await self._redraw_line()

    async def ctrl_delete(self) -> None:
        """Delete word to the right (Ctrl+Delete)."""
        if self._cursor >= len(self._chars):
            return

        # Skip whitespace
        while self._cursor < len(self._chars) and self._char_class(self._chars[self._cursor]) == "ws":
            self._chars.pop(self._cursor)

        if self._cursor >= len(self._chars):
            await self._redraw_line()
            return

        # Delete contiguous block of same class
        cls = self._char_class(self._chars[self._cursor])
        while self._cursor < len(self._chars) and self._char_class(self._chars[self._cursor]) == cls:
            self._chars.pop(self._cursor)

        await self._redraw_line()

    ########## Cursor Movement ##########
    async def cursor_left(self) -> None:
        if self._cursor <= 0:
            return
        self._cursor -= 1
        width = self._char_width(self._chars[self._cursor])
        await self.session_io.output.output_bytes(b"\b" * width)

    async def cursor_right(self) -> None:
        if self._cursor >= len(self._chars):
            return
        ch = self._chars[self._cursor]
        await self.session_io.output.output_str(ch)
        self._cursor += 1

    async def cursor_word_left(self) -> None:
        if self._cursor <= 0:
            return

        # Skip whitespace
        while self._cursor > 0 and self._char_class(self._chars[self._cursor - 1]) == "ws":
            self._cursor -= 1

        if self._cursor <= 0:
            await self._redraw_line()
            return

        cls = self._char_class(self._chars[self._cursor - 1])
        while self._cursor > 0 and self._char_class(self._chars[self._cursor - 1]) == cls:
            self._cursor -= 1

        await self._redraw_line()

    async def cursor_word_right(self) -> None:
        if self._cursor >= len(self._chars):
            return

        # Skip whitespace
        while self._cursor < len(self._chars) and self._char_class(self._chars[self._cursor]) == "ws":
            self._cursor += 1

        if self._cursor >= len(self._chars):
            await self._redraw_line()
            return

        cls = self._char_class(self._chars[self._cursor])
        while self._cursor < len(self._chars) and self._char_class(self._chars[self._cursor]) == cls:
            self._cursor += 1

        await self._redraw_line()

    async def cursor_home(self) -> None:
        if self._cursor == 0:
            return
        self._cursor = 0
        await self._redraw_line()

    async def cursor_end(self) -> None:
        if self._cursor == len(self._chars):
            return
        self._cursor = len(self._chars)
        await self._redraw_line()

    ########## History ##########
    async def history_up(self) -> None:
        prev = self.history.previous()
        if prev is None:
            return
        self._chars = list(prev)
        self._cursor = len(self._chars)
        await self._redraw_line()

    async def history_down(self) -> None:
        nxt = self.history.next()
        if nxt is None:
            return
        self._chars = list(nxt)
        self._cursor = len(self._chars)
        await self._redraw_line()

    def current_line(self) -> str:
        return "".join(self._chars)

    ########## Rendering ##########
    async def _redraw_line(self) -> None:
        prompt = self._get_prompt()
        line = "".join(self._chars)
        left = "".join(self._chars[:self._cursor])

        out = b"\r"
        out += (prompt + line).encode("utf-8", errors="replace")
        out += b"\x1b[K"

        total_width = self._text_width(line)
        left_width = self._text_width(left)
        move_left = total_width - left_width

        if move_left > 0:
            out += b"\b" * move_left

        await self.session_io.output.output_bytes(out)

    def _get_prompt(self) -> str:
        session = getattr(self.session_io, "session", None)
        if session:
            env = session.extra.get("env", {})
            return env.get("PS1", ">>> ")
        return ">>> "

    ########## Character Utilities ##########
    def _char_width(self, ch: str) -> int:
        width = wcswidth(ch)
        return width if width > 0 else 1

    def _text_width(self, text: str) -> int:
        width = wcswidth(text)
        return width if width > 0 else len(text)

    def _char_class(self, ch: str) -> str:
        if ch.isspace():
            return "ws"
        if ch.isalnum() or ch == "_":
            return "word"
        return "punct"