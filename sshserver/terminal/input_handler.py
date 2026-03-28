"""Input handling with local line discipline and line editor."""

import typing as t
import logging

from .line_editor import LineEditor
from .mouse_handler import MouseHandler
from .types import EOF

logger = logging.getLogger(__name__)


class InputHandler:
    """
    Processes raw input bytes, handles escape sequences, and provides line editing.
    """

    def __init__(self, terminal):
        self.terminal = terminal
        self.editor = LineEditor(terminal)
        self.mouse = MouseHandler(terminal)

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
        self.editor.reset()
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

    ########## Core Parser ##########
    async def _consume_pending(
        self, pending: bytearray, encoding: str = "utf-8"
    ) -> tuple[t.Optional[str], int]:
        if not pending:
            return None, 0

        b0 = pending[0]

        # Ctrl+C
        if b0 == 0x03:
            line = await self.editor.ctrl_c()
            return line, 1

        # Ctrl+D
        if b0 == 0x04:
            result = await self.editor.ctrl_d()
            return result, 1

        # Ctrl+W (word erase)
        if b0 == 0x17:
            await self.editor.ctrl_backspace()
            return None, 1

        # Enter
        if b0 in (0x0D, 0x0A):
            line = await self.editor.enter()
            # Handle CR+LF
            if len(pending) >= 2 and pending[1] in (0x0D, 0x0A) and pending[1] != b0:
                return line, 2
            return line, 1

        # Backspace / Delete
        if b0 in (0x08, 0x7F):
            await self.editor.backspace()
            return None, 1

        # ANSI escape sequences
        if b0 == 0x1B:
            seq_len = self._try_parse_escape(pending)
            if seq_len is None:
                return None, 0

            seq = bytes(pending[:seq_len])

            if await self.mouse.feed(seq):
                return None, seq_len

            await self._handle_escape(seq)
            return None, seq_len

        # UTF-8 character
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
        """Determine length of an ANSI escape sequence."""
        if len(pending) < 2:
            return None

        # ESC O ... (arrows)
        if pending[1] == ord("O"):
            return 3 if len(pending) >= 3 else None

        # ESC [ ...
        if pending[1] != ord("["):
            return 2 if len(pending) >= 2 else None

        # Mouse SGR sequences
        if len(pending) > 3 and pending[2] == ord("<"):
            for i in range(3, len(pending)):
                if pending[i] in (ord('M'), ord('m')):
                    return i + 1
            return None

        # Regular CSI sequences (end with @-~)
        for i in range(2, len(pending)):
            if 0x40 <= pending[i] <= 0x7E:
                return i + 1

        return None

    async def _handle_escape(self, seq: bytes):
        """Handle standard key escape sequences (arrows, delete, home, etc.)."""
        text = seq.decode("ascii", errors="ignore")

        # Mouse events already handled
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

        # Delete
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