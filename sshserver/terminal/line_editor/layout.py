import logging

from .text_utils import split_graphemes, char_width
from .types import Layout, VisualCell, ScreenPos

logger = logging.getLogger(__name__)


def build_layout(
    prompt_segments,
    buffer: list[str],
    cursor: int,
    term_width: int,
    ) -> Layout:
    term_width = max(1, term_width or 80)

    #logger.debug(
    #    "[BUILD_LAYOUT] term_width=%d | prompt_segments=%d | buffer_graphemes=%d",
    #    term_width, len(prompt_segments), len(buffer)
    #)

    rows: list[list[VisualCell]] = [[]]
    index_to_pos: list[ScreenPos] = []

    row = 0
    col = 1

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
            for g in split_graphemes(seg.text):
                push_cell(g, char_width(g), None)
        else:
            rows[row].append(
                VisualCell(
                    text=seg.text,
                    width=0,
                    buffer_index=None,
                )
            )

    # Buffer
    for i, g in enumerate(buffer):
        push_cell(g, char_width(g), i)

    pending_wrap = (col == term_width + 1)

    if cursor == len(buffer):
        if pending_wrap:
            cursor_pos = ScreenPos(row + 1, 1)
        else:
            cursor_pos = ScreenPos(row, col)
    else:
        cursor_pos = index_to_pos[cursor]

    if pending_wrap:
        end_pos = ScreenPos(row + 1, 1)
    else:
        end_pos = ScreenPos(row, col)

    rendered_text = "".join(
        cell.text for visual_row in rows for cell in visual_row
    )

    #logger.debug(
    #    "[BUILD_LAYOUT] DONE → rows=%d | pending_wrap=%s | cursor=(%d,%d) | end=(%d,%d)",
    #    len(rows), pending_wrap,
    #    cursor_pos.row, cursor_pos.col,
    #    end_pos.row, end_pos.col
    #)

    return Layout(
        rows=rows,
        index_to_pos=index_to_pos,
        cursor_pos=cursor_pos,
        end_pos=end_pos,
        rendered_text=rendered_text,
        pending_wrap=pending_wrap,
    )