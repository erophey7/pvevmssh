"""
Performing silent refactor
in testing
"""

import typing as t
import logging
import asyncio

from .line_editor._public import LineEditor
from .mouse_handler import MouseHandler
from .types import EOF, Key, KeyEvent
from ._keybinding import KeymapManager

logger = logging.getLogger(__name__)


class InputHandler:
    BRACKETED_PASTE_START = b"\x1b[200~"
    BRACKETED_PASTE_END = b"\x1b[201~"

    def __init__(self, terminal):
        self.terminal = terminal
        self.editor = LineEditor(terminal)
        self.mouse = MouseHandler(terminal)

        self._in_bracketed_paste = False

        self.keymap = KeymapManager()
        self.byte_parsers: list[t.Callable] = []
        self.escape_parsers: list[t.Callable] = []

        asyncio.create_task(self._init_keymap())

    # =========================================================
    # Public API
    # =========================================================
    async def input_bytes(self, data: bytes):
        await self.terminal.input_queue.put(data)

    async def input_str(self, data: str, encoding="utf-8"):
        if hasattr(self.terminal.editor, "_literal_insert"):
            self.terminal.editor._literal_insert = True
        await self.terminal.input_queue.put(data.encode(encoding))
        if hasattr(self.terminal.editor, "_literal_insert"):
            self.terminal.editor._literal_insert = False

    async def read_bytes(self) -> t.Optional[bytes]:
        return await self.terminal.input_queue.get()

    async def read_str(self, encoding="utf-8") -> t.Optional[str]:
        await self.editor.reset()
        pending = bytearray()

        while True:
            chunk = await self.terminal.input_queue.get()
            if chunk is None or not chunk:
                try:
                    return self.editor.current_line()
                except AttributeError:
                    return None

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

    # =========================================================
    # Parser registration (runtime)
    # =========================================================
    async def register_byte_parser(self, parser, first: bool = False):
        if first:
            self.byte_parsers.insert(0, parser)
        else:
            self.byte_parsers.append(parser)

    async def register_escape_parser(self, parser, first: bool = False):
        if first:
            self.escape_parsers.insert(0, parser)
        else:
            self.escape_parsers.append(parser)

    async def parse_bytes(self, pending: bytearray):
        for parser in self.byte_parsers:
            result = await parser(pending)
            if result:
                return result
        return None, 0

    async def parse_escape(self, seq: bytes):
        for parser in self.escape_parsers:
            result = await parser(seq)
            if result:
                return result
        return None

    # =========================================================
    # Core Parser
    # =========================================================
    async def _consume_pending(
        self, pending: bytearray, encoding: str = "utf-8"
    ) -> tuple[t.Optional[str], int]:

        if not pending:
            return None, 0

        event, consumed = await self.parse_bytes(pending)
        if consumed > 0:
            if event:
                result = await self.keymap.dispatch(event)
                return result, consumed
            return None, consumed

        # =====================================================
        # Bracketed paste
        # =====================================================
        if self._in_bracketed_paste:
            end_idx = pending.find(self.BRACKETED_PASTE_END)
            if end_idx == -1:
                text, used = self._decode_paste_bytes(bytes(pending), encoding)
                if used > 0 and text:
                    await self.keymap.dispatch(KeyEvent(Key.TEXT, text))
                    return None, used
                return None, 0

            payload = bytes(pending[:end_idx])
            text, _ = self._decode_paste_bytes(payload, encoding)
            if text:
                await self.keymap.dispatch(KeyEvent(Key.TEXT, text))

            self._in_bracketed_paste = False
            return None, end_idx + len(self.BRACKETED_PASTE_END)

        if pending.startswith(self.BRACKETED_PASTE_START):
            self._in_bracketed_paste = True
            return None, len(self.BRACKETED_PASTE_START)

        # =====================================================
        # ESC / sequences
        # =====================================================
        b0 = pending[0]

        if b0 == 0x1B:
            if getattr(self.editor, "_literal_insert", False):
                char = bytes([b0]).decode("ascii", errors="ignore")
                return KeyEvent(Key.TEXT, char), 1

            seq_len = self._try_parse_escape(pending)
            if seq_len is None:
                return None, 0

            seq = bytes(pending[:seq_len])

            if await self.mouse.feed(seq):
                return None, seq_len

            event = await self.parse_escape(seq)
            if event:
                result = await self.keymap.dispatch(event)
                return result, seq_len

            return None, seq_len

        # =====================================================
        # Bulk text
        # =====================================================
        bulk_text, bulk_len = self._try_parse_plain_text_run(pending, encoding)
        if bulk_len > 0 and bulk_text:
            result = await self.keymap.dispatch(KeyEvent(Key.TEXT, bulk_text))
            return result, bulk_len

        # =====================================================
        # Single char
        # =====================================================
        char_len = self._utf8_char_len(b0)
        if len(pending) < char_len:
            return None, 0

        raw = bytes(pending[:char_len])
        try:
            char = raw.decode(encoding)
        except UnicodeDecodeError:
            logger.debug("Invalid UTF-8: %r", raw)
            return None, char_len

        result = await self.keymap.dispatch(KeyEvent(Key.TEXT, char))
        return result, char_len

    # =========================================================
    # Helpers
    # =========================================================
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
        if len(pending) < 2:
            return None

        if pending[1] == ord("O"):
            return 3 if len(pending) >= 3 else None

        if pending[1] == ord("["):
            if len(pending) > 3 and pending[2] == ord("<"):
                for i in range(3, len(pending)):
                    if pending[i] in (ord("M"), ord("m")):
                        return i + 1
                return None

            for i in range(2, len(pending)):
                if 0x40 <= pending[i] <= 0x7E:
                    return i + 1
            return None

        return 2

    def _try_parse_plain_text_run(
        self, pending: bytearray, encoding: str
    ) -> tuple[str, int]:
        if not pending:
            return "", 0

        i = 0
        n = len(pending)

        while i < n:
            b0 = pending[i]

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

    def _decode_paste_bytes(
        self, data: bytes, encoding: str
    ) -> tuple[str, int]:
        if not data:
            return "", 0

        try:
            text = data.decode(encoding, errors="replace")
        except Exception:
            return "", 0

        text = text.replace("\r\n", "\n").replace("\r", "\n")
        return text, len(data)
    
    async def _init_keymap(self):
        # регистрируем дефолтные парсеры
        await self.register_byte_parser(self._default_ctrl_parser)
        await self.register_escape_parser(self._default_escape_parser)

        # получаем keymap от editor
        raw_map = self.editor.keys.build_default_keymap()

        # конвертим str → Key
        keymap = {}
        for k, v in raw_map.items():
            try:
                key = Key[k]
                if v:
                    keymap[key] = self._wrap_editor_handler(v)
            except KeyError:
                continue

        # TEXT всегда должен быть
        keymap[Key.TEXT] = self.editor.on_keybind

        await self.keymap._set_default_keymap(keymap)

    def _wrap_editor_handler(self, fn):
        async def wrapper(event):
            return await fn()
        return wrapper
    
    async def _default_ctrl_parser(self, pending: bytearray):
        b0 = pending[0]

        mapping = {
            0x01: Key.HOME,
            0x03: Key.CTRL_C,
            0x04: Key.CTRL_D,
            0x05: Key.END,
            0x0B: Key.CTRL_K,
            0x0C: Key.CTRL_L,
            0x12: Key.CTRL_R,
            0x15: Key.CTRL_U,
            0x17: Key.CTRL_BACKSPACE,
            0x09: Key.TAB,
        }

        if b0 in mapping:
            return KeyEvent(mapping[b0]), 1

        if b0 in (0x0D, 0x0A):
            return KeyEvent(Key.ENTER), 1

        if b0 in (0x08, 0x7F):
            return KeyEvent(Key.BACKSPACE), 1

        return None
    
    async def _default_escape_parser(self, seq: bytes):
        text = seq.decode("ascii", errors="ignore")

        # arrows
        if text in ("\x1b[A", "\x1bOA"): return KeyEvent(Key.UP)
        if text in ("\x1b[B", "\x1bOB"): return KeyEvent(Key.DOWN)
        if text in ("\x1b[C", "\x1bOC"): return KeyEvent(Key.RIGHT)
        if text in ("\x1b[D", "\x1bOD"): return KeyEvent(Key.LEFT)

        # SHIFT
        if text == "\x1b[1;2A": return KeyEvent(Key.SHIFT_UP)
        if text == "\x1b[1;2B": return KeyEvent(Key.SHIFT_DOWN)
        if text == "\x1b[1;2C": return KeyEvent(Key.SHIFT_RIGHT)
        if text == "\x1b[1;2D": return KeyEvent(Key.SHIFT_LEFT)

        # CTRL
        if text in ("\x1b[1;5A", "\x1b[5A"): return KeyEvent(Key.CTRL_UP)
        if text in ("\x1b[1;5B", "\x1b[5B"): return KeyEvent(Key.CTRL_DOWN)
        if text in ("\x1b[1;5C", "\x1b[5C"): return KeyEvent(Key.CTRL_RIGHT)
        if text in ("\x1b[1;5D", "\x1b[5D"): return KeyEvent(Key.CTRL_LEFT)

        # CTRL+SHIFT
        if text == "\x1b[1;6A": return KeyEvent(Key.CTRL_SHIFT_UP)
        if text == "\x1b[1;6B": return KeyEvent(Key.CTRL_SHIFT_DOWN)
        if text == "\x1b[1;6C": return KeyEvent(Key.CTRL_SHIFT_RIGHT)
        if text == "\x1b[1;6D": return KeyEvent(Key.CTRL_SHIFT_LEFT)

        # CTRL+ALT
        if text == "\x1b[1;7A": return KeyEvent(Key.CTRL_ALT_UP)
        if text == "\x1b[1;7B": return KeyEvent(Key.CTRL_ALT_DOWN)
        if text == "\x1b[1;7C": return KeyEvent(Key.CTRL_ALT_RIGHT)
        if text == "\x1b[1;7D": return KeyEvent(Key.CTRL_ALT_LEFT)

        # delete/home/end
        if text == "\x1b[3~": return KeyEvent(Key.DEL)
        if text == "\x1b[3;5~": return KeyEvent(Key.CTRL_DEL)

        if text in ("\x1b[H", "\x1bOH", "\x1b[1~"):
            return KeyEvent(Key.HOME)

        if text in ("\x1b[F", "\x1bOF", "\x1b[4~"):
            return KeyEvent(Key.END)

        if seq == b"\x1b":
            return KeyEvent(Key.ESC)

        if seq == b"\x1b\x7f":
            return KeyEvent(Key.CTRL_BACKSPACE)

        return None