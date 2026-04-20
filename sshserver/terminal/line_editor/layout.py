# layout.py
import logging
import typing as t

from .text_utils import split_graphemes, char_width, get_style, highlight_buffer
from .types import Layout, VisualCell, ScreenPos
from sshserver.session.syntax_highlight import (
    StyleConfig,
    StyleContext
)

logger = logging.getLogger(__name__)


def build_layout(
    prompt_segments,
    buffer: list[str],
    cursor: int,
    term_width: int,
    term_height: int,
    completions: list[str] | None = None,
    completion_index: int | None = None,
    inline_hint: str | None = None,
    style_ctx: StyleContext = None,
    semantic_styles: list[str] | None = None,
) -> Layout:
    term_width = max(1, term_width or 80)
    term_height = max(24, term_height or 24)

    rows: list[list[VisualCell]] = [[]]
    index_to_pos: list[ScreenPos] = []

    row = 0
    col = 1

    def push_cell(text: str, width: int, buffer_index: int | None,
                  style: str = "", highlight: bool = False) -> None:
        nonlocal row, col, rows

        if width <= 0:
            width = 1

        if col + width - 1 > term_width:
            row += 1
            rows.append([])
            col = 1

        rows[row].append(VisualCell(text, width, buffer_index, style, highlight))
        if buffer_index is not None:
            while len(index_to_pos) <= buffer_index:
                index_to_pos.append(ScreenPos(0, 1))
            index_to_pos[buffer_index] = ScreenPos(row, col)

        col += width

    # PROMPT
    for seg in prompt_segments:
        if seg.visible:
            for g in split_graphemes(seg.text):
                push_cell(g, char_width(g), None)
        else:
            rows[row].append(VisualCell(seg.text, 0, None))

    # BUFFER + SYNTAX HIGHLIGHT
    styled_buffer = highlight_buffer(
        buffer=buffer, 
        style_ctx=style_ctx, 
        semantic_styles=semantic_styles
    )
    for i, (g, style) in enumerate(styled_buffer):
        push_cell(g, char_width(g), i, style=style)

    pending_wrap = (col == term_width + 1)

    if cursor == len(buffer):
        cursor_pos = ScreenPos(row + 1 if pending_wrap else row, 1 if pending_wrap else col)
    else:
        cursor_pos = index_to_pos[cursor]

    # === INLINE HINT (ghost text) — только если курсор в конце ===
    if inline_hint and cursor == len(buffer):
        hint_style = style_ctx.get("INLINE_HINT")
        for g in split_graphemes(inline_hint):
            push_cell(g, char_width(g), None, style=hint_style)

    end_pos = ScreenPos(row + 1 if (col == term_width + 1) else row,
                        1 if (col == term_width + 1) else col)

    # ANSI для строки ввода
    input_ansi = ""
    current_style = ""
    for visual_row in rows:
        for cell in visual_row:
            style = cell.style + ("\x1b[7m" if cell.highlight else "")
            if style != current_style:
                if current_style:
                    input_ansi += StyleConfig.RESET
                input_ansi += style
                current_style = style
            input_ansi += cell.text
    if current_style:
        input_ansi += StyleConfig.RESET

    # ==================== МЕНЮ ====================
    menu_ansi = ""
    menu_start_col = 1
    menu_grid = (0, 0)

    if completions and completion_index is not None and len(completions) > 1:
        max_len = max(len(cand) for cand in completions) + 3
        available_width = term_width - (menu_start_col - 1)
        num_cols = max(1, available_width // max_len)

        input_rows = end_pos.row + 1
        max_menu_rows = max(1, term_height - input_rows - 1)

        num_rows_calc = (len(completions) + num_cols - 1) // num_cols
        num_rows = min(num_rows_calc, max_menu_rows)

        menu_lines = []
        for r in range(num_rows):
            line_parts = []
            for c_idx in range(num_cols):
                idx = r * num_cols + c_idx
                if idx < len(completions):
                    cand = completions[idx]
                    is_selected = idx == completion_index
                    style = get_style(style_ctx, "COMPLETION_SELECTED" if is_selected else "COMPLETION")
                    padded = cand.ljust(max_len - 2)
                    line_parts.append(f"{style}{padded}{StyleConfig.RESET}")
                else:
                    line_parts.append(" " * (max_len - 2))
            menu_lines.append("".join(line_parts))
        menu_ansi = "\r\n".join(menu_lines)
        menu_rows = len(menu_lines)

        menu_grid = (num_cols, menu_rows)

    return Layout(
        rows=rows,
        index_to_pos=index_to_pos,
        cursor_pos=cursor_pos,
        end_pos=end_pos,
        rendered_ansi=input_ansi,
        pending_wrap=pending_wrap,
        menu_ansi=menu_ansi,
        menu_start_col=menu_start_col,
        menu_grid=menu_grid,
    )

def compute_completion_grid_dims(
    completions: list[str],
    term_width: int,
    term_height: int,
    start_row: int,
    start_col: int = 1,
) -> tuple[int, int]:
    """
    Returns:
        num_rows, num_cols
    """

    if not completions:
        return 0, 0

    max_len = max(len(c) for c in completions) + 3

    available_width = term_width - (start_col - 1)
    num_cols = max(1, available_width // max_len)

    max_rows = max(1, term_height - start_row - 1)

    num_rows_calc = (len(completions) + num_cols - 1) // num_cols
    num_rows = min(num_rows_calc, max_rows)

    return num_rows, num_cols