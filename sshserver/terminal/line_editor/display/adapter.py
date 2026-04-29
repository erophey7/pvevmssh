from .buffer import ScreenBuffer
from ..types import Layout, VisualCell


def screen_to_layout(screen: ScreenBuffer) -> Layout:
    """ScreenBuffer → Layout (100% backward compatible API)."""
    rows: list[list[VisualCell]] = []
    for line in screen.lines:
        row: list[VisualCell] = []
        for cell in line.cells:
            row.append(VisualCell(
                text=cell.text,
                width=cell.width,
                buffer_index=cell.buffer_index,
                style=cell.style,
                highlight=cell.highlight,
            ))
        rows.append(row)

    return Layout(
        rows=rows,
        index_to_pos=screen.index_to_pos,
        cursor_pos=screen.cursor_pos,
        end_pos=screen.end_pos,
        rendered_ansi=screen.rendered_ansi,
        pending_wrap=screen.pending_wrap,
        menu_ansi=screen.menu_ansi,
        menu_start_col=screen.menu_start_col,
        menu_grid=screen.menu_grid,
    )