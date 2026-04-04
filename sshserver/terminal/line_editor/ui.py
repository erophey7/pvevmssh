import logging
import re
from dataclasses import dataclass

from .layout import build_layout

logger = logging.getLogger(__name__)

_BASH_PROMPT_NONPRINT_RE = re.compile(r"\\\[(.*?)\\\]", re.DOTALL)


@dataclass
class PromptSegment:
    text: str
    visible: bool


def get_prompt(terminal) -> str:
    session = getattr(terminal, "session", None)
    if session:
        env = session.extra.get("env", {})
        return env.get("PS1", ">>> ")
    return ">>> "


def get_prompt_segments(terminal) -> list[PromptSegment]:
    prompt = get_prompt(terminal)
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


async def redraw(editor) -> None:
    layout = build_layout(
        prompt_segments=get_prompt_segments(editor.terminal),
        buffer=editor._buffer,
        cursor=editor._cursor,
        term_width=getattr(editor.terminal.session, "term_width", 80),
    )

    out = b""

    logger.debug(
        "[REDRAW] START | last=%s | new_rows=%d | pending=%s | cursor=(%d,%d) | end=(%d,%d)",
        "None" if editor._last_layout is None else f"rows={len(editor._last_layout.rows)} p={editor._last_layout.pending_wrap}",
        len(layout.rows), layout.pending_wrap,
        layout.cursor_pos.row, layout.cursor_pos.col,
        layout.end_pos.row, layout.end_pos.col
    )

    if editor._last_layout is not None and editor._last_layout.cursor_pos.row > 0:
        out += f"\x1b[{editor._last_layout.cursor_pos.row}A".encode()
        logger.debug("[REDRAW] ↑ up %d to block start", editor._last_layout.cursor_pos.row)

    out += b"\r"
    out += b"\x1b[J"

    rendered_bytes = layout.rendered_text.replace("\n", "\r\n").encode("utf-8", errors="replace")
    out += rendered_bytes

    if layout.pending_wrap:
        out += b"\r\n"
        logger.debug("[REDRAW] pending_wrap → extra \\r\\n")

    rows_up = layout.end_pos.row - layout.cursor_pos.row
    if rows_up > 0:
        out += f"\x1b[{rows_up}A".encode()
        logger.debug("[REDRAW] ↑ up %d to cursor", rows_up)

    out += f"\x1b[{layout.cursor_pos.col}G".encode()
    logger.debug("[REDRAW] → column %d", layout.cursor_pos.col)

    editor._last_layout = layout

    if editor.echo:
        await editor.terminal.output.output_bytes(out)
        logger.debug("[REDRAW] bytes sent (%d)", len(out))


async def move_cursor_only_or_redraw(editor) -> None:
    if editor._last_layout is None:
        await redraw(editor)
        return

    new_layout = build_layout(
        prompt_segments=get_prompt_segments(editor.terminal),
        buffer=editor._buffer,
        cursor=editor._cursor,
        term_width=getattr(editor.terminal.session, "term_width", 80),
    )

    if (
        new_layout.rendered_text != editor._last_layout.rendered_text
        or new_layout.pending_wrap != editor._last_layout.pending_wrap
        or len(new_layout.rows) != len(editor._last_layout.rows)
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
        await editor.terminal.output.output_bytes(b"\x1b[2J\x1b[H")
    editor._last_layout = None
    await redraw(editor)