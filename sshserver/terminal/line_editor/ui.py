import logging
import re
from dataclasses import dataclass

from .layout import build_layout
from sshserver.session.prompt import get_prompt_segments
from sshserver.session.types import PromptSegment

logger = logging.getLogger(__name__)

def cache_prompt_segments(editor) -> list[PromptSegment]:
    if editor._prompt_segments is None:
        editor._prompt_segments = get_prompt_segments(editor.terminal)
    return editor._prompt_segments


async def redraw(editor) -> None:
    layout = build_layout(
        prompt_segments=cache_prompt_segments(editor),
        buffer=editor._buffer,
        cursor=editor._cursor,
        term_width=getattr(editor.terminal.session, "term_width", 80),
        term_height=getattr(editor.terminal.session, "term_height", 24),
        completions=getattr(editor, "_completions", None),
        completion_index=getattr(editor, "_completion_index", None),
    )

    out = b""

    # Возвращаемся в начало промпта (учитываем многострочный ввод)
    if editor._last_layout is not None and editor._last_layout.cursor_pos.row > 0:
        out += f"\x1b[{editor._last_layout.cursor_pos.row}A".encode()

    out += b"\r\x1b[J"                                      # чистим от начала строки вниз
    out += layout.rendered_ansi.encode("utf-8", errors="replace")

    if layout.pending_wrap:
        out += b"\r\n"

    # ==================== МЕНЮ (всегда слева, col=1) ====================
    if layout.menu_ansi:
        out += b"\r\n"
        lines = layout.menu_ansi.split("\r\n")
        for i, line in enumerate(lines):
            if layout.menu_start_col > 1:
                out += f"\x1b[{layout.menu_start_col}G".encode()
            out += line.encode("utf-8", errors="replace")
            if i < len(lines) - 1:
                out += b"\r\n"

    extra = layout.menu_height if layout.menu_ansi else 0
    rows_up = layout.end_pos.row - layout.cursor_pos.row + extra

    if rows_up > 0:
        out += f"\x1b[{rows_up}A".encode()

    out += f"\x1b[{layout.cursor_pos.col}G".encode()

    editor._last_layout = layout

    if editor.echo:
        await editor.terminal.output.output_bytes(out)


async def move_cursor_only_or_redraw(editor) -> None:
    if editor._last_layout is None:
        await redraw(editor)
        return

    new_layout = build_layout(
        prompt_segments=cache_prompt_segments(editor),
        buffer=editor._buffer,
        cursor=editor._cursor,
        term_width=getattr(editor.terminal.session, "term_width", 80),
        term_height=getattr(editor.terminal.session, "term_height", 24),
        completions=getattr(editor, "_completions", None),
        completion_index=getattr(editor, "_completion_index", None),
    )

    if (
        new_layout.rendered_ansi != editor._last_layout.rendered_ansi
        or new_layout.pending_wrap != editor._last_layout.pending_wrap
        or len(new_layout.rows) != len(editor._last_layout.rows)
        or new_layout.menu_ansi != editor._last_layout.menu_ansi
    ):
        await redraw(editor)
        return

    out = b""
    old = editor._last_layout.cursor_pos
    new = new_layout.cursor_pos

    row_delta = old.row - new.row
    if row_delta > 0:
        out += f"\x1b[{row_delta}A".encode()
    elif row_delta < 0:
        out += f"\x1b[{-row_delta}B".encode()

    out += f"\x1b[{new.col}G".encode()

    editor._last_layout = new_layout

    if editor.echo and out:
        await editor.terminal.output.output_bytes(out)


async def clear_screen_and_redraw(editor) -> None:
    if editor.echo:
        await editor.terminal.output.output_bytes(b"\x1b[2J\x1b[H]")
    editor._last_layout = None
    await redraw(editor)