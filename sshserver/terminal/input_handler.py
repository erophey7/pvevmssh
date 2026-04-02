"""Input handling with local line discipline and readline-like editor."""

import typing as t
import logging

from .line_editor import LineEditor
from .mouse_handler import MouseHandler
from .types import EOF

logger = logging.getLogger(__name__)


class InputHandler:
    """
    Processes raw terminal input and translates it into line-editor actions.

    Important:
    - ESC/CSI/SS3 are treated as terminal control protocol, not literal text.
    - Bracketed paste is supported.
    - Plain text is bulk-inserted for speed.
    """

    BRACKETED_PASTE_START = b"\x1b[200~"
    BRACKETED_PASTE_END = b"\x1b[201~"

    def __init__(self, terminal):
        self.terminal = terminal
        self.editor = LineEditor(terminal)
        self.mouse = MouseHandler(terminal)

        self._in_bracketed_paste = False

    ########## Public API ##########
    async def input_bytes(self, data: bytes):
        await self.terminal.input_queue.put(data)

    async def input_str(self, data: str, encoding="utf-8"):
        await self.terminal.input_queue.put(data.encode(encoding))

    async def read_bytes(self) -> t.Optional[bytes]:
        return await self.terminal.input_queue.get()

    async def read_str(self, encoding="utf-8") -> t.Optional[str]:
        """
        Read one complete line using the line editor.
        Returns EOF on Ctrl+D at empty line.
        """
        await self.editor.reset()
        pending = bytearray()

        while True:
            chunk = await self.terminal.input_queue.get()

            if chunk is None:
                return self.editor.current_line() or None

            if not chunk:
                return self.editor.current_line() or None

            pending.extend(chunk)

            while pending:
                result, consumed = await self._consume_pending(pending, encoding)

                if consumed == 0:
                    break

                del pending[:consumed]

                if result == "__IGNORE__":
                    continue

                if result is EOF:
                    return EOF

                if result is not None:
                    return result

    async def on_terminal_resize(self) -> None:
        await self.editor.on_terminal_resize()

    ########## Core Parser ##########
    async def _consume_pending(
        self, pending: bytearray, encoding: str = "utf-8"
    ) -> tuple[t.Optional[str], int]:
        if not pending:
            return None, 0

        # Bracketed paste mode
        if self._in_bracketed_paste:
            end_idx = pending.find(self.BRACKETED_PASTE_END)
            if end_idx == -1:
                # consume all available as paste payload
                text, used = self._decode_paste_bytes(bytes(pending), encoding)
                if used > 0 and text:
                    await self.editor.feed_text(text)
                    return None, used
                return None, 0

            payload = bytes(pending[:end_idx])
            text, _ = self._decode_paste_bytes(payload, encoding)
            if text:
                await self.editor.feed_text(text)

            self._in_bracketed_paste = False
            return None, end_idx + len(self.BRACKETED_PASTE_END)

        # Detect bracketed paste start
        if pending.startswith(self.BRACKETED_PASTE_START):
            self._in_bracketed_paste = True
            return None, len(self.BRACKETED_PASTE_START)

        b0 = pending[0]

        # Ctrl+A
        if b0 == 0x01:
            await self.editor.cursor_home()
            return None, 1

        # Ctrl+C
        if b0 == 0x03:
            line = await self.editor.ctrl_c()
            return line, 1

        # Ctrl+D
        if b0 == 0x04:
            result = await self.editor.ctrl_d()
            return result, 1

        # Ctrl+E
        if b0 == 0x05:
            await self.editor.cursor_end()
            return None, 1

        # Ctrl+K
        if b0 == 0x0B:
            await self.editor.ctrl_k()
            return None, 1

        # Ctrl+L
        if b0 == 0x0C:
            await self.editor.ctrl_l()
            return None, 1

        # Ctrl+R (stub)
        if b0 == 0x12:
            await self.editor.history_search_backward()
            return None, 1

        # Ctrl+U
        if b0 == 0x15:
            await self.editor.ctrl_u()
            return None, 1

        # Ctrl+W
        if b0 == 0x17:
            await self.editor.ctrl_backspace()
            return None, 1

        # Ctrl+V quoted insert prep
        if b0 == 0x16:
            await self.editor.quoted_insert()
            return None, 1

        # Tab
        if b0 == 0x09:
            await self.editor.tab_complete()
            return None, 1

        # Enter
        if b0 in (0x0D, 0x0A):
            line = await self.editor.enter()
            if len(pending) >= 2 and pending[1] in (0x0D, 0x0A) and pending[1] != b0:
                return line, 2
            return line, 1

        # Backspace / DEL
        if b0 in (0x08, 0x7F):
            await self.editor.backspace()
            return None, 1

        # ANSI escape sequences / Meta keys
        if b0 == 0x1B:
            seq_len = self._try_parse_escape(pending)
            if seq_len is None:
                return None, 0

            seq = bytes(pending[:seq_len])

            if await self.mouse.feed(seq):
                return None, seq_len

            await self._handle_escape(seq)
            return None, seq_len

        # Fast path: bulk plain text
        bulk_text, bulk_len = self._try_parse_plain_text_run(pending, encoding)
        if bulk_len > 0 and bulk_text:
            await self.editor.feed_text(bulk_text)
            return None, bulk_len

        # Single UTF-8 grapheme fallback
        char_len = self._utf8_char_len(b0)
        if len(pending) < char_len:
            return None, 0

        raw = bytes(pending[:char_len])
        try:
            char = raw.decode(encoding)
        except UnicodeDecodeError:
            logger.debug("Invalid UTF-8: %r", raw)
            return None, char_len

        await self.editor.feed_char(char)
        return None, char_len

    ########## Helpers ##########
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

    def _try_parse_escape(self, pending: bytearray) -> t.Optional[int]:
        """
        Determine length of terminal escape sequence.

        Supports:
        - ESC O ...
        - ESC [ ...
        - bracketed paste
        - SGR mouse
        - Meta-prefixed keys (ESC + printable)
        """
        if len(pending) < 2:
            return None

        # ESC O ...
        if pending[1] == ord("O"):
            return 3 if len(pending) >= 3 else None

        # ESC [ ...
        if pending[1] == ord("["):
            # Mouse SGR
            if len(pending) > 3 and pending[2] == ord("<"):
                for i in range(3, len(pending)):
                    if pending[i] in (ord("M"), ord("m")):
                        return i + 1
                return None

            # CSI / bracketed paste / function keys
            for i in range(2, len(pending)):
                if 0x40 <= pending[i] <= 0x7E:
                    return i + 1
            return None

        # ESC + printable => Meta-key / Alt-key
        return 2

    def _try_parse_plain_text_run(
        self, pending: bytearray, encoding: str
    ) -> tuple[str, int]:
        """
        Fast path for paste / normal typing:
        parse maximal run of printable UTF-8 text until first control/newline/escape.
        """
        if not pending:
            return "", 0

        i = 0
        n = len(pending)

        while i < n:
            b0 = pending[i]

            # stop on controls / escape
            if b0 < 0x20 or b0 in (0x7F, 0x1B):
                break

            char_len = self._utf8_char_len(b0)
            if i + char_len > n:
                break

            raw = bytes(pending[i:i + char_len])
            try:
                ch = raw.decode(encoding)
            except UnicodeDecodeError:
                break

            if ch in ("\r", "\n", "\x08", "\x7f", "\x1b"):
                break

            i += char_len

        if i == 0:
            return "", 0

        try:
            return bytes(pending[:i]).decode(encoding), i
        except UnicodeDecodeError:
            return "", 0

    def _decode_paste_bytes(self, data: bytes, encoding: str) -> tuple[str, int]:
        """
        Decode paste payload best-effort.
        Unlike normal typing, pasted text may contain tabs/newlines/etc.
        For now we normalize CRLF/CR into LF, but keep literal content.
        """
        if not data:
            return "", 0

        try:
            text = data.decode(encoding, errors="replace")
        except Exception:
            return "", 0

        text = text.replace("\r\n", "\n").replace("\r", "\n")
        return text, len(data)

    async def _handle_escape(self, seq: bytes):
        """
        Handle terminal key escape sequences.
        """
        text = seq.decode("ascii", errors="ignore")

        # Mouse already handled
        if text.startswith("\x1b[<"):
            return

        # Arrows
        if text in ("\x1b[A", "\x1bOA"):
            await self.editor.history_up()
            return
        if text in ("\x1b[B", "\x1bOB"):
            await self.editor.history_down()
            return
        if text in ("\x1b[C", "\x1bOC"):
            await self.editor.cursor_right()
            return
        if text in ("\x1b[D", "\x1bOD"):
            await self.editor.cursor_left()
            return

        # Ctrl + arrows
        if text in ("\x1b[1;5D", "\x1b[5D", "\x1b[;5D"):
            await self.editor.cursor_word_left()
            return
        if text in ("\x1b[1;5C", "\x1b[5C", "\x1b[;5C"):
            await self.editor.cursor_word_right()
            return

        # Delete / Ctrl+Delete
        if text == "\x1b[3~":
            await self.editor.delete()
            return
        if text in ("\x1b[3;5~", "\x1b[;5~"):
            await self.editor.ctrl_delete()
            return

        # Home / End
        if text in ("\x1b[H", "\x1bOH", "\x1b[1~", "\x1b[7~"):
            await self.editor.cursor_home()
            return
        if text in ("\x1b[F", "\x1bOF", "\x1b[4~", "\x1b[8~"):
            await self.editor.cursor_end()
            return

        # Alt+Backspace (часто ESC DEL)
        if seq == b"\x1b\x7f":
            await self.editor.ctrl_backspace()
            return

        # TODO:
        # Alt+F / Alt+B / Alt+D / etc.
        # Reverse-i-search, completion menus, yank-pop, vi mode, etc.
        return