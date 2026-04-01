import typing as t
import logging

from wcwidth import wcswidth
from sshserver.session import CommandHistory
from .types import EOF, Layout, VisualCell, ScreenPos

logger = logging.getLogger(__name__)


class LineEditor:
    """
    Full line editor with history, word navigation, and shell-like word classes.

    Internal model:
    - _buffer: logical text buffer (one-dimensional)
    - _cursor: insertion point inside _buffer
    - layout: visual projection of prompt + buffer onto terminal rows
    """

    def __init__(self, terminal):
        self.terminal = terminal

        self._buffer: list[str] = []
        self._cursor: int = 0

        # Last rendered visual layout
        self._last_layout: Layout | None = None

        self._history_draft: list[str] | None = None
        self._history_navigation_active: bool = False

        self.history = CommandHistory()
        self.echo: bool = True

    ########## Public Methods ##########
    def reset(self) -> None:
        self._buffer.clear()
        self._cursor = 0
        self._last_layout = None
        self._history_draft = None
        self._history_navigation_active = False
        self.history.reset_index()

    async def on_terminal_resize(self) -> None:
        """
        Called when terminal geometry changes.
        We invalidate previous layout and redraw current logical line.
        """
        self._last_layout = None
        await self._redraw_line()

    async def feed_char(self, char: str) -> None:
        self._buffer.insert(self._cursor, char)
        self._cursor += 1
        await self._redraw_line()

    async def feed_text(self, text: str) -> None:
        """
        Fast bulk insert used for paste bursts:
        insert all text at cursor and redraw once.
        """
        if not text:
            return

        insert = list(text)
        self._buffer[self._cursor:self._cursor] = insert
        self._cursor += len(insert)
        await self._redraw_line()

    async def enter(self) -> str:
        self._last_layout = None
        await self.terminal.output.output_bytes(b"\r\n")
        line = "".join(self._buffer)

        if line.strip():
            self.history.add(line)

        return line

    async def ctrl_c(self) -> str:
        self._last_layout = None
        self._buffer.clear()
        self._cursor = 0
        await self.terminal.output.output_bytes(b"^C\r\n")
        return ""

    async def ctrl_d(self) -> t.Optional[str]:
        if not self._buffer:
            return EOF
        return None

    async def backspace(self) -> None:
        if self._cursor <= 0:
            return
        self._cursor -= 1
        self._buffer.pop(self._cursor)
        await self._redraw_line()

    async def ctrl_backspace(self) -> None:
        """Delete word to the left (Ctrl+W)."""
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

        await self._redraw_line()

    async def delete(self) -> None:
        if self._cursor >= len(self._buffer):
            return
        self._buffer.pop(self._cursor)
        await self._redraw_line()

    async def ctrl_delete(self) -> None:
        """Delete word to the right (Ctrl+Delete)."""
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

        await self._redraw_line()

    ########## Cursor Movement ##########
    async def cursor_left(self) -> None:
        if self._cursor <= 0:
            return
        self._cursor -= 1
        await self._move_cursor_only_or_redraw()

    async def cursor_right(self) -> None:
        if self._cursor >= len(self._buffer):
            return
        self._cursor += 1
        await self._move_cursor_only_or_redraw()

    async def cursor_word_left(self) -> None:
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
        if self._cursor == 0:
            return
        self._cursor = 0
        await self._move_cursor_only_or_redraw()

    async def cursor_end(self) -> None:
        if self._cursor == len(self._buffer):
            return
        self._cursor = len(self._buffer)
        await self._move_cursor_only_or_redraw()

    ########## History ##########
    async def history_up(self) -> None:
        if not self._history_navigation_active:
            self._history_draft = self._buffer.copy()
            self._history_navigation_active = True

        prev = self.history.previous()
        if prev is None:
            return

        self._buffer = list(prev)
        self._cursor = len(self._buffer)
        await self._redraw_line()

    async def history_down(self) -> None:
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

        self._buffer = list(nxt)
        self._cursor = len(self._buffer)
        await self._redraw_line()

    def current_line(self) -> str:
        return "".join(self._buffer)

    ########## Rendering ##########
    def _build_layout(self) -> Layout:
        """
        Build visual layout of:
            prompt + buffer
        projected onto terminal rows.
        """
        prompt = self._get_prompt()
        term_width = self.terminal.session.term_width or 80

        rows: list[list[VisualCell]] = [[]]
        index_to_pos: list[ScreenPos] = []

        row = 0
        col = 1  # 1-based terminal column

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

        # Render prompt
        for ch in prompt:
            push_cell(ch, self._char_width(ch), None)

        # Render buffer
        for i, ch in enumerate(self._buffer):
            push_cell(ch, self._char_width(ch), i)

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

        return Layout(
            rows=rows,
            index_to_pos=index_to_pos,
            cursor_pos=cursor_pos,
            end_pos=end_pos,
            rendered_text=rendered_text,
            pending_wrap=pending_wrap,
        )

    def _visible_row_count(self, layout: Layout) -> int:
        """
        How many physical terminal rows the rendered block occupies.
        """
        count = len(layout.rows)
        if layout.pending_wrap:
            count += 1
        return max(1, count)

    async def _move_cursor_only_or_redraw(self) -> None:
        """
        Fast path for pure cursor movement:
        recompute layout and only move terminal cursor if content didn't change.
        """
        if self._last_layout is None:
            await self._redraw_line()
            return

        new_layout = self._build_layout()

        # If text geometry changed, do full redraw
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
        """
        Stable redraw strategy:
        - return to start of previous rendered block
        - clear all old physical rows
        - render new block
        - place cursor back
        """
        layout = self._build_layout()
        out = b""

        if self._last_layout is not None:
            old_rows = self._visible_row_count(self._last_layout)

            # Go from old cursor row to top of old block
            if self._last_layout.cursor_pos.row > 0:
                out += f"\x1b[{self._last_layout.cursor_pos.row}A".encode()

            # Clear every old row
            for i in range(old_rows):
                out += b"\r\x1b[2K"
                if i < old_rows - 1:
                    out += b"\x1b[1B"

            # Return to top of old block
            if old_rows > 1:
                out += f"\x1b[{old_rows - 1}A".encode()

        else:
            out += b"\r\x1b[2K"

        # Draw new prompt + buffer
        out += layout.rendered_text.replace("\n", "\r\n").encode("utf-8", errors="replace")

        # Force physical wrap if render ends exactly at terminal edge
        if layout.pending_wrap:
            out += b"\r\n"

        # Clear anything after current draw
        out += b"\x1b[J"

        # Move from end of new rendered block back to cursor position
        rows_up = layout.end_pos.row - layout.cursor_pos.row
        if rows_up > 0:
            out += f"\x1b[{rows_up}A".encode()

        out += f"\x1b[{layout.cursor_pos.col}G".encode()

        self._last_layout = layout

        if self.echo:
            await self.terminal.output.output_bytes(out)

    def _get_prompt(self) -> str:
        session = getattr(self.terminal, "session", None)
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