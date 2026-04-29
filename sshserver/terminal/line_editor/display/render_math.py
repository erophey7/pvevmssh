"""Чистые математические функции рендера — готовы к переносу на C."""


def calc_menu_rows(menu_grid: tuple[int, int], menu_ansi: str) -> int:
    """Количество строк меню (0 если меню нет)."""
    return menu_grid[1] if menu_ansi else 0


def calc_total_draw_rows(num_input_lines: int, menu_rows: int) -> int:
    """Общая высота нарисованного блока в строках."""
    total = num_input_lines
    if menu_rows > 0:
        total += 1 + menu_rows  # separator CRLF + menu
    return total


def calc_current_row_after_draw(num_input_lines: int, menu_rows: int) -> int:
    """0-based строка, где окажется курсор после отрисовки (в конце блока)."""
    return calc_total_draw_rows(num_input_lines, menu_rows) - 1


def calc_rows_up_to_cursor(current_row: int, cursor_row: int) -> int:
    """Сколько строк подняться от current_row до cursor_row."""
    return max(0, current_row - cursor_row)


def calc_anchor_row(abs_cursor_row_1based: int, cursor_row_0based: int) -> int:
    """0-based строка терминала, где начинается screen.lines[0]."""
    return max(0, abs_cursor_row_1based - 1 - cursor_row_0based)


def calc_rows_up_to_start(last_cursor_row: int) -> int:
    """Сколько строк подняться от текущей позиции курсора до начала блока."""
    return max(0, last_cursor_row)