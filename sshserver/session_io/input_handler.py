import typing as t
import logging

from sshserver.session_io.line_editor import LineEditor

logger = logging.getLogger(__name__)


class InputHandler:
    """
    Обработка входящих данных.

    Поддержка:
    - raw bytes
    - строкового ввода
    - локальной line discipline / line editor
    """

    def __init__(self, session_io):
        self.session_io = session_io
        self.editor = LineEditor(session_io)

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
        self.editor.reset()
        pending = bytearray()

        while True:
            chunk = await self.session_io.input_queue.get()

            if chunk is None:
                line = self.editor.current_line()
                return line if line else None

            if not chunk:
                line = self.editor.current_line()
                return line if line else None

            pending.extend(chunk)

            while pending:
                result, consumed = await self._consume_pending(pending, encoding)

                if consumed == 0:
                    break

                del pending[:consumed]

                if result == "__IGNORE__":
                    continue

                if result is not None:
                    return result

    # ============================================================
    # Core parser
    # ============================================================

    async def _consume_pending(
        self,
        pending: bytearray,
        encoding: str = "utf-8"
    ) -> tuple[t.Optional[str], int]:
        """
        Возвращает:
        - (None, n)           -> обработали n байт, строка ещё не готова
        - ("...", n)          -> готовая строка
        - (None, 0)           -> нужно дождаться ещё байтов
        """

        b0 = pending[0]

        # ------------------------------------------------------------
        # Ctrl+C
        # ------------------------------------------------------------
        if b0 == 0x03:
            line = await self.editor.ctrl_c()
            return line, 1

        # ------------------------------------------------------------
        # Ctrl+D
        # ------------------------------------------------------------
        if b0 == 0x04:
            result = await self.editor.ctrl_d()
            return result, 1

        # ------------------------------------------------------------
        # Ctrl+W (часто приходит как Ctrl+Backspace)
        # ------------------------------------------------------------
        if b0 == 0x17:   # можно заменить на b0 in (0x17, 0x08): но это уже не shell like
            await self.editor.ctrl_backspace()
            return None, 1

        # ------------------------------------------------------------
        # Enter (\r / \n)
        # ------------------------------------------------------------
        if b0 in (0x0D, 0x0A):
            line = await self.editor.enter()

            # CRLF защита: если пришло \r\n или \n\r
            if len(pending) >= 2 and pending[1] in (0x0D, 0x0A) and pending[1] != b0:
                return line, 2

            return line, 1

        # ------------------------------------------------------------
        # Backspace / DEL in tty mode
        # ------------------------------------------------------------
        if b0 in (0x08, 0x7F):
            await self.editor.backspace()
            return None, 1

        # ------------------------------------------------------------
        # ANSI escape sequence
        # ------------------------------------------------------------
        if b0 == 0x1B:
            seq_len = self._try_parse_escape(pending)
            if seq_len is None:
                return None, 0

            seq = bytes(pending[:seq_len])
            await self._handle_escape(seq)
            return None, seq_len

        # ------------------------------------------------------------
        # UTF-8 printable char
        # ------------------------------------------------------------
        char_len = self._utf8_char_len(b0)

        if len(pending) < char_len:
            return None, 0

        raw = bytes(pending[:char_len])

        try:
            char = raw.decode(encoding)
        except UnicodeDecodeError:
            logger.debug("Invalid UTF-8 byte sequence: %r", raw)
            return None, char_len

        await self.editor.feed_char(char)
        return None, char_len

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
        """
        Поддерживаем:
        - ESC [ A/B/C/D
        - ESC [ 3~
        - ESC [ 1;5D
        - ESC [ 3;5~
        - ESC O A/B/C/D
        - ESC DEL
        """
        if len(pending) < 2:
            return None

        # ESC DEL / ESC BS
        if pending[1] in (0x7F, 0x08):
            return 2

        # ESC O A/B/C/D
        if pending[1] == ord("O"):
            if len(pending) < 3:
                return None
            return 3

        # ESC [ ...
        if pending[1] != ord("["):
            return 2

        for i in range(2, len(pending)):
            b = pending[i]
            if 0x40 <= b <= 0x7E:
                return i + 1

        return None

    async def _handle_escape(self, seq: bytes):
        text = seq.decode("ascii", errors="ignore")


        # ------------------------------------------------------------
        # Стрелки
        # ------------------------------------------------------------
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

        # ------------------------------------------------------------
        # Ctrl + стрелки
        # ------------------------------------------------------------
        if text in ("\x1b[1;5D", "\x1b[5D", "\x1b[;5D"):
            await self.editor.cursor_word_left()
            return

        if text in ("\x1b[1;5C", "\x1b[5C", "\x1b[;5C"):
            await self.editor.cursor_word_right()
            return

        if text in ("\x1b[1;5A", "\x1b[5A", "\x1b[;5A"):
            await self.editor.history_up()
            return

        if text in ("\x1b[1;5B", "\x1b[5B", "\x1b[;5B"):
            await self.editor.history_down()
            return

        # ------------------------------------------------------------
        # Delete
        # ------------------------------------------------------------
        if text == "\x1b[3~":
            await self.editor.delete()
            return

        # ------------------------------------------------------------
        # Ctrl + Delete
        # ------------------------------------------------------------
        if text in ("\x1b[3;5~", "\x1b[;5~"):
            await self.editor.ctrl_delete()
            return
        
        # ------------------------------------------------------------
        # Home / End
        # ------------------------------------------------------------
        if text in ("\x1b[H", "\x1bOH", "\x1b[1~", "\x1b[7~"):
            await self.editor.cursor_home()
            return

        if text in ("\x1b[F", "\x1bOF", "\x1b[4~", "\x1b[8~"):
            await self.editor.cursor_end()
            return
