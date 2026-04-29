import logging

from ..text_utils import char_width, get_style, highlight_buffer
from ..types import ScreenPos
from .buffer import ScreenBuffer, ScreenLine, ScreenCell
from .adapter import screen_to_layout

from sshserver.session.syntax_highlight import StyleConfig
from helpers.text_utils.char_tools import split_graphemes

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from helpers.lsp.json_rpc_proto import SemanticTokens
    from sshserver.session.syntax_highlight import StyleContext
    from ..types import Layout

logger = logging.getLogger(__name__)


def _iter_graphemes(text: str):
    if text.isascii():
        return iter(text)
    return split_graphemes(text)


def build_screen(
    prompt_segments,
    buffer: list[str],
    cursor: int,
    term_width: int,
    term_height: int,
    completions: list[str] | None = None,
    completion_index: int | None = None,
    inline_hint: str | None = None,
    style_ctx: "StyleContext" = None,
    semantic_tokens: "SemanticTokens | None" = None,
) -> ScreenBuffer:
    term_width = max(1, term_width or 80)
    term_height = max(24, term_height or 24)

    lines: list[ScreenLine] = [ScreenLine()]
    index_to_pos: list[ScreenPos] = [ScreenPos(0, 1)] * len(buffer)

    row = 0
    col = 1

    def push_cell(text: str, width: int, buffer_index: int | None,
                  style: str = "", highlight: bool = False) -> None:
        nonlocal row, col
        if width <= 0:
            width = 1
        if col + width - 1 > term_width:
            row += 1
            lines.append(ScreenLine())
            col = 1

        lines[row].cells.append(ScreenCell(text, width, buffer_index, style, highlight))
        if buffer_index is not None:
            index_to_pos[buffer_index] = ScreenPos(row, col)
        col += width

    # Prompt
    for seg in prompt_segments:
        if seg.visible:
            for g in _iter_graphemes(seg.text):
                push_cell(g, char_width(g), None)
        else:
            lines[row].cells.append(ScreenCell(seg.text, 0, None))

    # Buffer + syntax highlight
    styled_runs = highlight_buffer(
        buffer=buffer,
        style_ctx=style_ctx,
        semantic_tokens=semantic_tokens
    )

    buf_idx = 0
    for run_text, style in styled_runs:
        for g in _iter_graphemes(run_text):
            push_cell(g, char_width(g), buf_idx, style=style)
            buf_idx += 1

    pending_wrap = (col == term_width + 1)

    if cursor == len(buffer):
        cursor_pos = ScreenPos(row + 1 if pending_wrap else row,
                               1 if pending_wrap else col)
    else:
        cursor_pos = index_to_pos[cursor]

    # Inline hint
    if inline_hint and cursor == len(buffer):
        hint_style = style_ctx.get("INLINE_HINT")
        for g in _iter_graphemes(inline_hint):
            push_cell(g, char_width(g), None, style=hint_style)

    pending_wrap = (col == term_width + 1)
    end_pos = ScreenPos(row + 1 if pending_wrap else row,
                        1 if pending_wrap else col)

    # ANSI assembly for backward compatibility
    parts: list[str] = []
    current_style = ""
    for line in lines:
        for cell in line.cells:
            if not cell.text:
                continue
            cell_style = cell.style + ("\x1b[7m" if cell.highlight else "")
            if cell_style == StyleConfig.RESET:
                cell_style = ""
            if cell_style != current_style:
                if current_style:
                    parts.append(StyleConfig.RESET)
                if cell_style:
                    parts.append(cell_style)
                current_style = cell_style
            parts.append(cell.text)
    if current_style:
        parts.append(StyleConfig.RESET)
    input_ansi = "".join(parts)

    # Menu
    menu_ansi = ""
    menu_start_col = 1
    menu_grid = (0, 0)

    if completions and completion_index is not None and len(completions) > 1:
        menu_rows, num_cols = compute_completion_grid_dims(
            completions=completions,
            term_width=term_width,
            term_height=term_height,
            start_row=end_pos.row + 1,
            start_col=menu_start_col,
        )
        if menu_rows > 0:
            max_len = max(len(c) for c in completions) + 3
            style_normal = get_style(style_ctx, "COMPLETION")
            style_selected = get_style(style_ctx, "COMPLETION_SELECTED")

            menu_lines = []
            for r in range(menu_rows):
                line_parts = []
                for c_idx in range(num_cols):
                    idx = r * num_cols + c_idx
                    if idx < len(completions):
                        cand = completions[idx]
                        style = style_selected if idx == completion_index else style_normal
                        padded = cand.ljust(max_len - 2)
                        line_parts.append(f"{style}{padded}{StyleConfig.RESET}")
                    else:
                        line_parts.append(" " * (max_len - 2))
                menu_lines.append("".join(line_parts))

            menu_ansi = "\r\n".join(menu_lines)
            menu_grid = (num_cols, menu_rows)

    return ScreenBuffer(
        lines=lines,
        index_to_pos=index_to_pos,
        cursor_pos=cursor_pos,
        end_pos=end_pos,
        pending_wrap=pending_wrap,
        menu_grid=menu_grid,
        rendered_ansi=input_ansi,
        menu_ansi=menu_ansi,
        menu_start_col=menu_start_col,
    )


def build_layout(
    prompt_segments,
    buffer: list[str],
    cursor: int,
    term_width: int,
    term_height: int,
    completions: list[str] | None = None,
    completion_index: int | None = None,
    inline_hint: str | None = None,
    style_ctx: "StyleContext" = None,
    semantic_tokens: "SemanticTokens | None" = None,
) -> "Layout":
    screen = build_screen(
        prompt_segments=prompt_segments,
        buffer=buffer,
        cursor=cursor,
        term_width=term_width,
        term_height=term_height,
        completions=completions,
        completion_index=completion_index,
        inline_hint=inline_hint,
        style_ctx=style_ctx,
        semantic_tokens=semantic_tokens,
    )
    return screen_to_layout(screen)


def compute_completion_grid_dims(
    completions: list[str],
    term_width: int,
    term_height: int,
    start_row: int,
    start_col: int = 1,
) -> tuple[int, int]:
    if not completions:
        return 0, 0
    max_len = max(len(c) for c in completions) + 3
    available_width = term_width - (start_col - 1)
    num_cols = max(1, available_width // max_len)
    max_rows = max(1, term_height - start_row - 1)
    num_rows_calc = (len(completions) + num_cols - 1) // num_cols
    num_rows = min(num_rows_calc, max_rows)
    return num_rows, num_cols