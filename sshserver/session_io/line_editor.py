import typing as t
import logging

from wcwidth import wcswidth
from sshserver.session_env.history import CommandHistory

logger = logging.getLogger(__name__)


class LineEditor:
    """
    Полноценный line editor поверх raw SSH input.

    Поддержка:
    - UTF-8 / Unicode ввод
    - Enter
    - Backspace
    - Ctrl+Backspace / Ctrl+W
    - Delete
    - Ctrl+Delete
    - Ctrl+C / Ctrl+D
    - Стрелки ← ↑ → ↓
    - Ctrl+← / Ctrl+→ / Ctrl+↑ / Ctrl+↓
    - Home / End
    - История команд

    Shell-like логика:
    - word  = [A-Za-z0-9_]
    - punct = / : = - . # & и т.п.
    - ws    = whitespace
    """

    def __init__(self, session_io):
        self.session_io = session_io

        self._chars: list[str] = []
        self._cursor: int = 0
        self.history = CommandHistory()

    # ============================================================
    # Public
    # ============================================================

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
            return None
        return "__IGNORE__"

    async def backspace(self) -> None:
        """
        Обычный backspace: удалить 1 символ слева от курсора.
        """
        if self._cursor <= 0:
            return

        self._cursor -= 1
        self._chars.pop(self._cursor)
        await self._redraw_line()

    async def ctrl_backspace(self) -> None:
        """
        Bash-like Ctrl+W:
        удалить shell-word слева от курсора.

        Логика:
        1. Съесть whitespace слева
        2. Если слева punct — удалить весь contiguous punct block
        3. Если слева word  — удалить весь contiguous word block
        """
        if self._cursor <= 0:
            return

        # 1) whitespace слева
        while self._cursor > 0 and self._char_class(self._chars[self._cursor - 1]) == "ws":
            self._cursor -= 1
            self._chars.pop(self._cursor)

        if self._cursor <= 0:
            await self._redraw_line()
            return

        # 2) удалить contiguous block слева
        cls = self._char_class(self._chars[self._cursor - 1])

        while self._cursor > 0 and self._char_class(self._chars[self._cursor - 1]) == cls:
            self._cursor -= 1
            self._chars.pop(self._cursor)

        await self._redraw_line()

    async def delete(self) -> None:
        """
        Обычный Delete: удалить 1 символ под курсором.
        """
        if self._cursor >= len(self._chars):
            return

        self._chars.pop(self._cursor)
        await self._redraw_line()

    async def ctrl_delete(self) -> None:
        """
        Bash-like Ctrl+Delete:
        удалить shell-word справа от курсора.

        Логика:
        1. Съесть whitespace справа
        2. Удалить contiguous block справа
        """
        if self._cursor >= len(self._chars):
            return

        # 1) whitespace справа
        while self._cursor < len(self._chars) and self._char_class(self._chars[self._cursor]) == "ws":
            self._chars.pop(self._cursor)

        if self._cursor >= len(self._chars):
            await self._redraw_line()
            return

        # 2) удалить contiguous block справа
        cls = self._char_class(self._chars[self._cursor])

        while self._cursor < len(self._chars) and self._char_class(self._chars[self._cursor]) == cls:
            self._chars.pop(self._cursor)

        await self._redraw_line()

    # ============================================================
    # Cursor movement
    # ============================================================

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
        """
        Bash-like Ctrl+Left:
        перейти в начало shell-word / shell-block слева.

        Пример:
        export PATH=/usr/local/bin:/usr/bin
                                     ^
        шаги влево:
        bin -> usr -> : -> bin -> local -> / -> usr -> = -> PATH -> export
        """
        if self._cursor <= 0:
            return

        # 1) пропустить whitespace слева
        while self._cursor > 0 and self._char_class(self._chars[self._cursor - 1]) == "ws":
            self._cursor -= 1

        if self._cursor <= 0:
            await self._redraw_line()
            return

        # 2) взять класс блока слева
        cls = self._char_class(self._chars[self._cursor - 1])

        # 3) пройти весь блок этого класса
        while self._cursor > 0 and self._char_class(self._chars[self._cursor - 1]) == cls:
            self._cursor -= 1

        await self._redraw_line()

    async def cursor_word_right(self) -> None:
        """
        Bash-like Ctrl+Right:
        перейти в конец текущего/следующего shell-word / shell-block справа.

        Пример:
        !export PATH=/usr/local/bin:/usr/bin
        export! PATH=/usr/local/bin:/usr/bin
        export PATH!=/usr/local/bin:/usr/bin
        export PATH=/usr!/local/bin:/usr/bin
        ...
        """
        if self._cursor >= len(self._chars):
            return

        # 1) если стоим на whitespace — сначала пропускаем whitespace
        while self._cursor < len(self._chars) and self._char_class(self._chars[self._cursor]) == "ws":
            self._cursor += 1

        if self._cursor >= len(self._chars):
            await self._redraw_line()
            return

        # 2) проходим contiguous block текущего класса
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

    # ============================================================
    # History
    # ============================================================

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

    # ============================================================
    # Rendering
    # ============================================================

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

    def _char_width(self, ch: str) -> int:
        width = wcswidth(ch)
        return width if width > 0 else 1

    def _text_width(self, text: str) -> int:
        width = wcswidth(text)
        return width if width > 0 else len(text)

    # ============================================================
    # Helper
    # ============================================================

    def _char_class(self, ch: str) -> str:
        """
        Shell-like классификация символов:
        - ws    : whitespace
        - word  : [A-Za-z0-9_]
        - punct : всё остальное
        """
        if ch.isspace():
            return "ws"
        if ch.isalnum() or ch == "_":
            return "word"
        return "punct"