import asyncio
import logging
import regex
import typing as t
from dataclasses import dataclass

import re
from wcwidth import wcswidth

from sshserver.session import CommandHistory
from .types import EOF, Layout, VisualCell, ScreenPos

logger = logging.getLogger(__name__)

# Ограничения ближе к readline-практике
MAX_LINE_LENGTH = 8192
MAX_PROMPT_LENGTH = 1024

# Bash-like non-printing prompt spans: \[ ... \]
_BASH_PROMPT_NONPRINT_RE = re.compile(r"\\\[(.*?)\\\]", re.DOTALL)


@dataclass
class PromptSegment:
    text: str
    visible: bool


class LineEditor:
    """
    Readline-like line editor.

    Internal model:
    - _buffer: list of grapheme clusters (NOT raw code points)
    - _cursor: insertion point in grapheme units
    - prompt: may contain ANSI/non-printing spans
    """

    def __init__(self, terminal):
        self.terminal = terminal

        self._buffer: list[str] = []
        self._cursor: int = 0

        self._last_layout: Layout | None = None

        self._history_draft: list[str] | None = None
        self._history_navigation_active: bool = False

        self.history = CommandHistory()
        self.echo: bool = True

        self._lock = asyncio.Lock()

        # Future readline-like states
        self._quoted_insert: bool = False

    ########## Public Methods ##########
    async def reset(self) -> None:
        async with self._lock:
            self._buffer.clear()
            self._cursor = 0
            self._last_layout = None
            self._history_draft = None
            self._history_navigation_active = False
            self._quoted_insert = False
            self.history.reset_index()

    async def on_terminal_resize(self) -> None:
        async with self._lock:
            logger.debug("[LineEditor] on_terminal_resize called | term_width=%s",
                        getattr(self.terminal.session, 'term_width', None))
            await self._redraw_line()

    async def feed_char(self, char: str) -> None:
        async with self._lock:
            if not char:
                return

            if self._quoted_insert:
                self._quoted_insert = False

            graphemes = self._split_graphemes(char)
            if not graphemes:
                return

            remaining = MAX_LINE_LENGTH - len(self._buffer)
            if remaining <= 0:
                return

            graphemes = graphemes[:remaining]
            self._buffer[self._cursor:self._cursor] = graphemes
            self._cursor += len(graphemes)

            self._history_navigation_active = False
            await self._redraw_line()

    async def feed_text(self, text: str) -> None:
        async with self._lock:
            if not text:
                return

            if self._quoted_insert:
                self._quoted_insert = False

            insert = self._split_graphemes(text)
            if not insert:
                return

            remaining = MAX_LINE_LENGTH - len(self._buffer)
            if remaining <= 0:
                return

            insert = insert[:remaining]
            self._buffer[self._cursor:self._cursor] = insert
            self._cursor += len(insert)

            self._history_navigation_active = False
            await self._redraw_line()

    async def enter(self) -> str:
        async with self._lock:
            self._last_layout = None
            await self.terminal.output.output_bytes(b"\r\n")
            line = "".join(self._buffer)

            if line.strip():
                self.history.add(line)

            # Bash-like: после Enter редактор должен сброситься
            self._buffer.clear()
            self._cursor = 0
            self._history_draft = None
            self._history_navigation_active = False
            self._quoted_insert = False
            self.history.reset_index()

            return line

    async def ctrl_c(self) -> str:
        async with self._lock:
            self._last_layout = None
            self._buffer.clear()
            self._cursor = 0
            self._history_draft = None
            self._history_navigation_active = False
            self._quoted_insert = False
            self.history.reset_index()
            await self.terminal.output.output_bytes(b"^C\r\n")
            return ""

    async def ctrl_d(self) -> t.Optional[str]:
        async with self._lock:
            if not self._buffer:
                return EOF
            return None

    async def backspace(self) -> None:
        async with self._lock:
            if self._cursor <= 0:
                return
            self._cursor -= 1
            self._buffer.pop(self._cursor)
            self._history_navigation_active = False
            await self._redraw_line()

    async def ctrl_backspace(self) -> None:
        """Backward kill word (Ctrl+W)."""
        async with self._lock:
            if self._cursor <= 0:
                return

            while self._cursor > 0 and self._char_class(self._buffer[self._cursor - 1]) == "ws":
                self._cursor -= 1
                self._buffer.pop(self._cursor)

            if self._cursor <= 0:
                await self._redraw_line()
                return

            cls = self._char_class(self._buffer[self._cursor - 1])
            while self._cursor > 0 and self._char_class(self._buffer[self._cursor - 1]) == cls:
                self._cursor -= 1
                self._buffer.pop(self._cursor)

            self._history_navigation_active = False
            await self._redraw_line()

    async def ctrl_u(self) -> None:
        """Kill from cursor to beginning."""
        async with self._lock:
            if self._cursor <= 0:
                return
            del self._buffer[:self._cursor]
            self._cursor = 0
            self._history_navigation_active = False
            await self._redraw_line()

    async def ctrl_k(self) -> None:
        """Kill from cursor to end."""
        async with self._lock:
            if self._cursor >= len(self._buffer):
                return
            del self._buffer[self._cursor:]
            self._history_navigation_active = False
            await self._redraw_line()

    async def ctrl_l(self) -> None:
        """Clear screen + redraw like readline."""
        async with self._lock:
            out = b"\x1b[2J\x1b[H"
            if self.echo:
                await self.terminal.output.output_bytes(out)
            self._last_layout = None
            await self._redraw_line()

    async def quoted_insert(self) -> None:
        """Readline-like Ctrl+V preparation."""
        async with self._lock:
            self._quoted_insert = True

    async def delete(self) -> None:
        async with self._lock:
            if self._cursor >= len(self._buffer):
                return
            self._buffer.pop(self._cursor)
            self._history_navigation_active = False
            await self._redraw_line()

    async def ctrl_delete(self) -> None:
        """Delete word to the right."""
        async with self._lock:
            if self._cursor >= len(self._buffer):
                return

            while self._cursor < len(self._buffer) and self._char_class(self._buffer[self._cursor]) == "ws":
                self._buffer.pop(self._cursor)

            if self._cursor >= len(self._buffer):
                await self._redraw_line()
                return

            cls = self._char_class(self._buffer[self._cursor])
            while self._cursor < len(self._buffer) and self._char_class(self._buffer[self._cursor]) == cls:
                self._buffer.pop(self._cursor)

            self._history_navigation_active = False
            await self._redraw_line()

    async def tab_complete(self) -> None:
        """
        Заглушка под completion.
        Bash-like поведение будет позже.
        """
        # TODO: completion engine
        return

    ########## Cursor Movement ##########
    async def cursor_left(self) -> None:
        async with self._lock:
            if self._cursor <= 0:
                return
            self._cursor -= 1
            await self._move_cursor_only_or_redraw()

    async def cursor_right(self) -> None:
        async with self._lock:
            if self._cursor >= len(self._buffer):
                return
            self._cursor += 1
            await self._move_cursor_only_or_redraw()

    async def cursor_word_left(self) -> None:
        async with self._lock:
            if self._cursor <= 0:
                return

            while self._cursor > 0 and self._char_class(self._buffer[self._cursor - 1]) == "ws":
                self._cursor -= 1

            if self._cursor > 0:
                cls = self._char_class(self._buffer[self._cursor - 1])
                while self._cursor > 0 and self._char_class(self._buffer[self._cursor - 1]) == cls:
                    self._cursor -= 1

            await self._move_cursor_only_or_redraw()

    async def cursor_word_right(self) -> None:
        async with self._lock:
            if self._cursor >= len(self._buffer):
                return

            while self._cursor < len(self._buffer) and self._char_class(self._buffer[self._cursor]) == "ws":
                self._cursor += 1

            if self._cursor < len(self._buffer):
                cls = self._char_class(self._buffer[self._cursor])
                while self._cursor < len(self._buffer) and self._char_class(self._buffer[self._cursor]) == cls:
                    self._cursor += 1

            await self._move_cursor_only_or_redraw()

    async def cursor_home(self) -> None:
        async with self._lock:
            if self._cursor == 0:
                return
            self._cursor = 0
            await self._move_cursor_only_or_redraw()

    async def cursor_end(self) -> None:
        async with self._lock:
            if self._cursor == len(self._buffer):
                return
            self._cursor = len(self._buffer)
            await self._move_cursor_only_or_redraw()

    ########## History ##########
    async def history_up(self) -> None:
        async with self._lock:
            if not self._history_navigation_active:
                self._history_draft = self._buffer.copy()
                self._history_navigation_active = True

            prev = self.history.previous()
            if prev is None:
                return

            self._buffer = self._split_graphemes(prev)
            self._cursor = len(self._buffer)
            await self._redraw_line()

    async def history_down(self) -> None:
        async with self._lock:
            if not self._history_navigation_active:
                return

            nxt = self.history.next()

            if nxt is None or nxt == "":
                if self._history_draft is not None:
                    self._buffer = self._history_draft.copy()
                    self._cursor = len(self._buffer)

                self._history_navigation_active = False
                self._history_draft = None
                self.history.reset_index()

                await self._redraw_line()
                return

            self._buffer = self._split_graphemes(nxt)
            self._cursor = len(self._buffer)
            await self._redraw_line()

    async def history_search_backward(self) -> None:
        """Заглушка под Ctrl+R."""
        # TODO: incremental reverse search
        return

    def current_line(self) -> str:
        return "".join(self._buffer)

    ########## Rendering ##########
    def _build_layout(self) -> Layout:
        prompt_segments = self._get_prompt_segments()
        term_width = max(1, self.terminal.session.term_width or 80)

        logger.debug("[BUILD_LAYOUT] term_width=%d | prompt_segments=%d | buffer_graphemes=%d",
                     term_width, len(prompt_segments), len(self._buffer))

        rows: list[list[VisualCell]] = [[]]
        index_to_pos: list[ScreenPos] = []

        row = 0
        col = 1  # terminal columns are 1-based

        def push_cell(text: str, width: int, buffer_index: int | None) -> None:
            nonlocal row, col, rows

            if width <= 0:
                width = 1

            if col + width - 1 > term_width:
                row += 1
                rows.append([])
                col = 1

            rows[row].append(
                VisualCell(
                    text=text,
                    width=width,
                    buffer_index=buffer_index,
                )
            )

            if buffer_index is not None:
                while len(index_to_pos) <= buffer_index:
                    index_to_pos.append(ScreenPos(0, 1))
                index_to_pos[buffer_index] = ScreenPos(row, col)

            col += width

        # Prompt
        for seg in prompt_segments:
            if seg.visible:
                for g in self._split_graphemes(seg.text):
                    push_cell(g, self._char_width(g), None)
            else:
                # Non-printing ANSI/control prompt span:
                # render it, but do NOT consume width
                rows[row].append(
                    VisualCell(
                        text=seg.text,
                        width=0,
                        buffer_index=None,
                    )
                )

        # Buffer
        for i, g in enumerate(self._buffer):
            push_cell(g, self._char_width(g), i)

        pending_wrap = (col == term_width + 1)

        if self._cursor == len(self._buffer):
            if pending_wrap:
                cursor_pos = ScreenPos(row + 1, 1)
            else:
                cursor_pos = ScreenPos(row, col)
        else:
            cursor_pos = index_to_pos[self._cursor]

        if pending_wrap:
            end_pos = ScreenPos(row + 1, 1)
        else:
            end_pos = ScreenPos(row, col)

        rendered_text = "\n".join(
            "".join(cell.text for cell in visual_row)
            for visual_row in rows
        )

        logger.debug("[BUILD_LAYOUT] DONE → rows=%d | pending_wrap=%s | cursor=(%d,%d) | end=(%d,%d)",
                     len(rows), pending_wrap,
                     row, col,
                     end_pos.row, end_pos.col)

        return Layout(
            rows=rows,
            index_to_pos=index_to_pos,
            cursor_pos=cursor_pos,
            end_pos=end_pos,
            rendered_text=rendered_text,
            pending_wrap=pending_wrap,
        )

    def _visible_row_count(self, layout: Layout) -> int:
        count = len(layout.rows)
        if layout.pending_wrap:
            count += 1
        return max(1, count)

    async def _move_cursor_only_or_redraw(self) -> None:
        if self._last_layout is None:
            await self._redraw_line()
            return

        new_layout = self._build_layout()

        if (
            new_layout.rendered_text != self._last_layout.rendered_text
            or new_layout.pending_wrap != self._last_layout.pending_wrap
            or len(new_layout.rows) != len(self._last_layout.rows)
        ):
            await self._redraw_line()
            return

        out = b""

        old = self._last_layout.cursor_pos
        new = new_layout.cursor_pos

        row_delta = old.row - new.row
        if row_delta > 0:
            out += f"\x1b[{row_delta}A".encode()
        elif row_delta < 0:
            out += f"\x1b[{-row_delta}B".encode()

        out += f"\x1b[{new.col}G".encode()

        self._last_layout = new_layout

        if self.echo and out:
            await self.terminal.output.output_bytes(out)

    async def _redraw_line(self) -> None:
        layout = self._build_layout()
        out = b""
    
        logger.debug("[REDRAW] START | last=%s | new_rows=%d | pending=%s | cursor=(%d,%d) | end=(%d,%d)",
                     "None" if self._last_layout is None else f"rows={len(self._last_layout.rows)} p={self._last_layout.pending_wrap}",
                     len(layout.rows), layout.pending_wrap,
                     layout.cursor_pos.row, layout.cursor_pos.col,
                     layout.end_pos.row, layout.end_pos.col)
    
        if self._last_layout is not None and self._last_layout.cursor_pos.row > 0:
            out += f"\x1b[{self._last_layout.cursor_pos.row}A".encode()
            logger.debug("[REDRAW] ↑ up %d to block start", self._last_layout.cursor_pos.row)
    
        out += b"\r"
        out += b"\x1b[J"  # ← до рендера, пока курсор в начале блока
    
        rendered_bytes = layout.rendered_text.replace("\n", "\r\n").encode("utf-8", errors="replace")
        out += rendered_bytes
        if layout.pending_wrap:
            out += b"\r\n"
            logger.debug("[REDRAW] pending_wrap → extra \\r\\n")
    
        logger.debug("[REDRAW] printed %d chars", len(layout.rendered_text))
    
        rows_up = layout.end_pos.row - layout.cursor_pos.row
        if rows_up > 0:
            out += f"\x1b[{rows_up}A".encode()
            logger.debug("[REDRAW] ↑ up %d to cursor", rows_up)
        out += f"\x1b[{layout.cursor_pos.col}G".encode()
        logger.debug("[REDRAW] → column %d", layout.cursor_pos.col)
    
        self._last_layout = layout
        logger.debug("[REDRAW] END | _last_layout updated")
    
        if self.echo:
            await self.terminal.output.output_bytes(out)
            logger.debug("[REDRAW] bytes sent (%d)", len(out))

    ########## Prompt ##########
    def _get_prompt(self) -> str:
        session = getattr(self.terminal, "session", None)
        if session:
            env = session.extra.get("env", {})
            prompt = env.get("PS1", ">>> ")
            return prompt[:MAX_PROMPT_LENGTH]
        return ">>> "

    def _get_prompt_segments(self) -> list[PromptSegment]:
        prompt = self._get_prompt()
        parts: list[PromptSegment] = []

        pos = 0
        for m in _BASH_PROMPT_NONPRINT_RE.finditer(prompt):
            if m.start() > pos:
                parts.append(PromptSegment(prompt[pos:m.start()], True))
            parts.append(PromptSegment(m.group(1), False))
            pos = m.end()

        if pos < len(prompt):
            parts.append(PromptSegment(prompt[pos:], True))

        if not parts:
            parts.append(PromptSegment(prompt, True))

        return parts

    ########## Character / Text Utilities ##########
    def _split_graphemes(self, text: str) -> list[str]:
        return regex.findall(r"\X", text)

    def _char_width(self, g: str) -> int:
        width = wcswidth(g)
        return width if width > 0 else 1

    def _char_class(self, g: str) -> str:
        if g.isspace():
            return "ws"
        if g.isalnum() or g == "_":
            return "word"
        return "punct"