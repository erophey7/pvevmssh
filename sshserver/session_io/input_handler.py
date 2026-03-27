import typing as t
import logging
import codecs

from wcwidth import wcswidth
from sshserver.session_env.history import CommandHistory

logger = logging.getLogger(__name__)


class InputHandler:
    """
    Полноценный line editor поверх raw SSH input.

    Поддержка:
    - UTF-8 / Unicode ввод
    - Enter
    - Backspace
    - Ctrl+Backspace
    - Delete
    - Ctrl+Delete
    - Ctrl+C / Ctrl+D
    - Стрелки ← ↑ → ↓
    - Ctrl+← / Ctrl+→ / Ctrl+↑ / Ctrl+↓
    - История команд
    """

    def __init__(self, session_io):
        self.session_io = session_io
        self._chars: list[str] = []
        self._cursor: int = 0
        self.history = CommandHistory()
        self._decoder_factory = codecs.getincrementaldecoder("utf-8")

    # ============================================================
    # Public API
    # ============================================================

    async def input_bytes(self, data: bytes):
        await self.session_io.input_queue.put(data)

    async def input_str(self, data: str, encoding="utf-8"):
        await self.session_io.input_queue.put(data.encode(encoding))

    async def read_bytes(self) -> t.Optional[bytes]:
        return await self.session_io.input_queue.get()

    async def read_str(self, encoding="utf-8") -> t.Optional[str]:
        """
        Чтение одной полноценной строки с локальной line discipline.
        """
        self._chars.clear()
        self._cursor = 0
        self.history.reset_index()
        decoder = self._decoder_factory()
        pending = bytearray()

        while True:
            chunk = await self.session_io.input_queue.get()
            if chunk is None:
                if self._chars:
                    return "".join(self._chars)
                return None
            pending.extend(chunk)
            while pending:
                consumed = await self._consume_pending(pending, decoder)
                if consumed == 0:
                    break
                del pending[:consumed]

    # ============================================================
    # Core parser
    # ============================================================

    async def _consume_pending(self, pending: bytearray, decoder) -> int:
        b0 = pending[0]

        # Ctrl+C
        if b0 == 0x03:
            self._chars.clear()
            self._cursor = 0
            await self.session_io.output.output_bytes(b"^C\r\n")
            raise _LineReady("")

        # Ctrl+D
        if b0 == 0x04:
            if not self._chars:
                raise _LineEOF()
            return 1

        # Enter
        if b0 in (0x0D, 0x0A):
            await self.session_io.output.output_bytes(b"\r\n")
            line = "".join(self._chars)
            if line.strip():
                self.history.add(line)
            raise _LineReady(line)

        # Backspace / DEL
        if b0 in (0x08, 0x7F):
            await self._handle_backspace()
            return 1

        # ANSI escape sequence
        if b0 == 0x1B:
            seq_len = self._try_parse_escape(pending)
            if seq_len is None:
                return 0
            seq = bytes(pending[:seq_len])
            await self._handle_escape(seq)
            return seq_len

        # UTF-8 printable char
        char_len = self._utf8_char_len(b0)
        if len(pending) < char_len:
            return 0
        raw = bytes(pending[:char_len])
        try:
            char = raw.decode("utf-8")
        except UnicodeDecodeError:
            logger.debug("Invalid UTF-8 byte sequence: %r", raw)
            return char_len
        await self._insert_char(char)
        return char_len

    # ============================================================
    # UTF-8 helpers
    # ============================================================

    def _utf8_char_len(self, b0: int) -> int:
        if b0 < 0x80:
            return 1
        if (b0 & 0xE0) == 0xC0:
            return 2
        if (b0 & 0xF0) == 0xE0:
            return 3
        if (b0 & 0xF8) == 0xF0:
            return 4
        return 1

    # ============================================================
    # Escape parsing
    # ============================================================

    def _try_parse_escape(self, pending: bytearray) -> t.Optional[int]:
        if len(pending) < 2:
            return None
        if pending[1] == ord("O"):
            return 3 if len(pending) >= 3 else None
        if pending[1] != ord("["):
            return 2
        for i in range(2, len(pending)):
            b = pending[i]
            if 0x40 <= b <= 0x7E:
                return i + 1
        return None

    async def _handle_escape(self, seq: bytes):
        text = seq.decode("ascii", errors="ignore")
        if text in ("\x1b[A", "\x1bOA"):
            await self._history_up()
        elif text in ("\x1b[B", "\x1bOB"):
            await self._history_down()
        elif text in ("\x1b[C", "\x1bOC"):
            await self._cursor_right()
        elif text in ("\x1b[D", "\x1bOD"):
            await self._cursor_left()
        elif text in ("\x1b[1;5D", "\x1b[5D"):
            await self._cursor_word_left()
        elif text in ("\x1b[1;5C", "\x1b[5C"):
            await self._cursor_word_right()
        elif text in ("\x1b[1;5A", "\x1b[5A"):
            await self._history_up()
        elif text in ("\x1b[1;5B", "\x1b[5B"):
            await self._history_down()
        elif text == "\x1b[3~":
            await self._handle_delete()
        elif text == "\x1b[3;5~":
            await self._handle_ctrl_delete()
        elif text in ("\x17", "\x1b\x7f", "\x1b[127;5u"):
            await self._handle_ctrl_backspace()
        else:
            logger.debug("Unhandled escape sequence: %r", text)

    # ============================================================
    # Editing operations
    # ============================================================

    async def _insert_char(self, char: str):
        self._chars.insert(self._cursor, char)
        self._cursor += 1
        await self._redraw_line()

    async def _handle_backspace(self):
        if self._cursor <= 0:
            return
        self._cursor -= 1
        self._chars.pop(self._cursor)
        await self._redraw_line()

    async def _handle_ctrl_backspace(self):
        if self._cursor <= 0:
            return
        while self._cursor > 0 and self._chars[self._cursor - 1].isspace():
            self._cursor -= 1
            self._chars.pop(self._cursor)
        while self._cursor > 0 and not self._chars[self._cursor - 1].isspace():
            self._cursor -= 1
            self._chars.pop(self._cursor)
        await self._redraw_line()

    async def _handle_delete(self):
        if self._cursor >= len(self._chars):
            return
        self._chars.pop(self._cursor)
        await self._redraw_line()

    async def _handle_ctrl_delete(self):
        if self._cursor >= len(self._chars):
            return
        while self._cursor < len(self._chars) and self._chars[self._cursor].isspace():
            self._chars.pop(self._cursor)
        while self._cursor < len(self._chars) and not self._chars[self._cursor].isspace():
            self._chars.pop(self._cursor)
        await self._redraw_line()

    # ============================================================
    # Cursor movement
    # ============================================================

    async def _cursor_left(self):
        if self._cursor <= 0:
            return
        self._cursor -= 1
        width = self._char_width(self._chars[self._cursor])
        await self.session_io.output.output_bytes(b"\b" * width)

    async def _cursor_right(self):
        if self._cursor >= len(self._chars):
            return
        ch = self._chars[self._cursor]
        await self.session_io.output.output_str(ch)
        self._cursor += 1

    async def _cursor_word_left(self):
        if self._cursor <= 0:
            return
        while self._cursor > 0 and self._chars[self._cursor - 1].isspace():
            self._cursor -= 1
        while self._cursor > 0 and not self._chars[self._cursor - 1].isspace():
            self._cursor -= 1
        await self._redraw_line()

    async def _cursor_word_right(self):
        if self._cursor >= len(self._chars):
            return
        while self._cursor < len(self._chars) and not self._chars[self._cursor].isspace():
            self._cursor += 1
        while self._cursor < len(self._chars) and self._chars[self._cursor].isspace():
            self._cursor += 1
        await self._redraw_line()

    # ============================================================
    # History
    # ============================================================

    async def _history_up(self):
        prev = self.history.previous()
        if prev is None:
            return
        self._chars = list(prev)
        self._cursor = len(self._chars)
        await self._redraw_line()

    async def _history_down(self):
        nxt = self.history.next()
        if nxt is None:
            self._chars.clear()
            self._cursor = 0
            await self._redraw_line()
            return
        self._chars = list(nxt)
        self._cursor = len(self._chars)
        await self._redraw_line()

    # ============================================================
    # Rendering
    # ============================================================

    async def _redraw_line(self):
        prompt = self._get_prompt()
        line = "".join(self._chars)
        left = "".join(self._chars[:self._cursor])
        out = b"\r" + (prompt + line).encode("utf-8", errors="replace") + b"\x1b[K"
        move_left = self._text_width(line) - self._text_width(left)
        if move_left > 0:
            out += b"\b" * move_left
        await self.session_io.output.output_bytes(out)

    def _get_prompt(self) -> str:
        session = getattr(self.session_io, "session", None)
        if session:
            env = session.extra.get("env", {})
            return env.get("PS1", ">>> ")
        return ">>> "

    def _char_width(self, ch: str) -> int:
        width = wcswidth(ch)
        return width if width > 0 else 1

    def _text_width(self, text: str) -> int:
        width = wcswidth(text)
        return width if width > 0 else len(text)


# ============================================================
# Internal flow exceptions
# ============================================================

class _LineReady(Exception):
    def __init__(self, line: str):
        self.line = line


class _LineEOF(Exception):
    pass