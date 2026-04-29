import logging
from .buffer import ScreenBuffer, ScreenLine
from ..types import ScreenPos
from . import ansi

logger = logging.getLogger(__name__)


class ZshRefresh:
    """Character-level diff engine в стиле zsh (ZLE)."""

    def __init__(self):
        self.actual_lines: list[ScreenLine] | None = None
        self.actual_menu: str = ""
        self.actual_cursor: ScreenPos | None = None

    def reset(self) -> None:
        self.actual_lines = None
        self.actual_menu = ""
        self.actual_cursor = None

    def refresh(self, desired: ScreenBuffer, anchor_row: int = 0) -> bytes:
        if self.actual_lines is None:
            return self._full_refresh(desired, anchor_row)

        out = bytearray()

        # --- diff input lines ---
        first_diff, last_diff = self._find_diff_range(self.actual_lines, desired.lines)

        if first_diff is not None:
            for row in range(first_diff, last_diff + 1):
                old_line = self.actual_lines[row] if row < len(self.actual_lines) else ScreenLine()
                new_line = desired.lines[row] if row < len(desired.lines) else ScreenLine()
                out.extend(self._diff_line(anchor_row + row, old_line, new_line))

        # --- diff menu ---
        if self.actual_menu != desired.menu_ansi:
            menu_base = anchor_row + len(desired.lines)
            old_lines = self.actual_menu.split("\r\n") if self.actual_menu else []
            new_lines = desired.menu_ansi.split("\r\n") if desired.menu_ansi else []
            max_lines = max(len(old_lines), len(new_lines))

            for i in range(max_lines):
                abs_row = menu_base + i
                old_line = old_lines[i] if i < len(old_lines) else None
                new_line = new_lines[i] if i < len(new_lines) else None

                if new_line is None:
                    out.extend(ansi.move_cursor(abs_row, 1))
                    out.extend(ansi.CLEAR_LINE)
                elif old_line != new_line:
                    out.extend(ansi.move_cursor(abs_row, 1))
                    out.extend(ansi.CLEAR_LINE)
                    out.extend(new_line.encode("utf-8", "replace"))

        # --- cursor ---
        out.extend(ansi.move_cursor(anchor_row + desired.cursor_pos.row, desired.cursor_pos.col))
        out.extend(ansi.RESET_STYLE)

        self.actual_lines = list(desired.lines)
        self.actual_menu = desired.menu_ansi
        self.actual_cursor = desired.cursor_pos
        return bytes(out)

    def _find_diff_range(self, old: list[ScreenLine], new: list[ScreenLine]) -> tuple[int | None, int]:
        first_diff = None
        last_diff = 0
        max_rows = max(len(old), len(new))
        for row in range(max_rows):
            o = old[row] if row < len(old) else None
            n = new[row] if row < len(new) else None
            if (o or n) and (not o or not n or o != n):
                if first_diff is None:
                    first_diff = row
                last_diff = row
        return first_diff, last_diff

    def _full_refresh(self, desired: ScreenBuffer, anchor_row: int = 0) -> bytes:
        out = bytearray()

        for i, line in enumerate(desired.lines):
            out.extend(ansi.move_cursor(anchor_row + i, 1))
            out.extend(ansi.CLEAR_LINE)
            current_style = ""
            for cell in line.cells:
                if not cell.text:
                    continue
                if cell.style != current_style:
                    if current_style:
                        out.extend(ansi.RESET_STYLE)
                    if cell.style:
                        out.extend(cell.style.encode())
                    current_style = cell.style
                out.extend(cell.text.encode("utf-8", "replace"))
            if current_style:
                out.extend(ansi.RESET_STYLE)

        # Menu
        if desired.menu_ansi:
            menu_base = anchor_row + len(desired.lines)
            lines = desired.menu_ansi.split("\r\n")
            for i, line in enumerate(lines):
                out.extend(ansi.move_cursor(menu_base + i, 1))
                out.extend(ansi.CLEAR_LINE)
                out.extend(line.encode("utf-8", "replace"))

        out.extend(ansi.move_cursor(anchor_row + desired.cursor_pos.row, desired.cursor_pos.col))
        out.extend(ansi.RESET_STYLE)

        self.actual_lines = list(desired.lines)
        self.actual_menu = desired.menu_ansi
        self.actual_cursor = desired.cursor_pos
        return bytes(out)

    def _diff_line(self, abs_row: int, old: ScreenLine, new: ScreenLine) -> bytes:
        col = 0
        while col < len(old.cells) and col < len(new.cells) and old.cells[col] == new.cells[col]:
            col += 1

        if col == len(old.cells) and col == len(new.cells):
            return b""

        out = bytearray()
        out.extend(ansi.move_cursor(abs_row, col + 1))

        # suffix optimization
        suffix = 0
        while (suffix < len(old.cells) - col and
               suffix < len(new.cells) - col and
               old.cells[len(old.cells) - 1 - suffix] == new.cells[len(new.cells) - 1 - suffix]):
            suffix += 1

        draw_to = len(new.cells) - suffix

        current_style = ""
        for c in range(col, draw_to):
            cell = new.cells[c]
            if cell.style != current_style:
                if current_style:
                    out.extend(ansi.RESET_STYLE)
                if cell.style:
                    out.extend(cell.style.encode())
                current_style = cell.style
            out.extend(cell.text.encode("utf-8", "replace"))

        if current_style:
            out.extend(ansi.RESET_STYLE)

        if len(old.cells) > len(new.cells):
            out.extend(ansi.CLEAR_TO_END_OF_LINE)
        elif suffix > 0 and draw_to < len(new.cells):
            for c in range(draw_to, len(new.cells)):
                cell = new.cells[c]
                if cell.style != current_style:
                    if current_style:
                        out.extend(ansi.RESET_STYLE)
                    if cell.style:
                        out.extend(cell.style.encode())
                    current_style = cell.style
                out.extend(cell.text.encode("utf-8", "replace"))
            if current_style:
                out.extend(ansi.RESET_STYLE)

        return bytes(out)