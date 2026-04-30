from .layout import build_layout
from sshserver.session.prompt import get_prompt_segments

import re
import asyncio
import logging
logger = logging.getLogger(__name__)

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .objects import LineEditorPrivateVars, LineEditorPublicVars
    from sshserver.session.types import PromptSegment
    from .types import Layout


# =============================================
# BACKGROUND TASK HELPERS
# =============================================
_background_tasks: set[asyncio.Task] = set()


def _schedule_bg(coro) -> asyncio.Task:
    """Запускает фоновую задачу с автоочисткой."""
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task


# =============================================
# CALLMANAGER
# =============================================
class CallManager:
    def __init__(self, trigger):
        self._pending: bool = False
        self._trigger = trigger
        self._debounce_time: float = 0.003

    def request(self):
        if not self._pending:
            self._pending = True
            asyncio.create_task(self._debounce())

    async def _debounce(self):
        await asyncio.sleep(self._debounce_time)
        self._pending = False
        await self._trigger()


# =============================================
# UI
# =============================================
class LineEditorUI:
    def __init__(self, vpriv: "LineEditorPrivateVars", vpub: "LineEditorPublicVars"):
        self.vpriv = vpriv
        self.vpub = vpub

        self._last_layout: "Layout | None" = None
        self._task_id: int = 0
        self._call_manager = CallManager(self._render_pipeline)

        # 1-based (row, col) — известна только после CPR или clear_screen.
        # None = позиция неизвестна → используем relative mode (как readline).
        # Абсолютный diff-рендер включается только когда это поле заполнено.
        self._cursor_abs: tuple[int, int] | None = None

        # 0-based строка терминала где начинается layout row=0.
        # Актуальна только в absolute diff mode (_cursor_abs is not None).
        self._anchor_row: int = 0

        # Отслеживание позиции layout row=0 на экране, независимо от курсора.
        # Исправляет баг: anchor_row выводился из cursor_pos, что ломалось
        # при перемещении курсора между строками.
        self._layout_anchor_row: int | None = None

    # =============================================
    # PUBLIC
    # =============================================
    async def redraw(self) -> None:
        self._call_manager.request()

    async def move_cursor_only_or_redraw(self) -> None:
        self._call_manager.request()

    async def clear_screen_and_redraw(self) -> None:
        if self.vpub.echo:
            await self.vpub.terminal.output.output_bytes(b"\x1b[2J\x1b[H")
        self._last_layout = None
        self._cursor_abs = (1, 1)  # после \x1b[H позиция известна
        self._anchor_row = 0
        self._call_manager.request()

    def get_last_layout(self) -> "Layout | None":
        return self._last_layout

    def clear_cache(self) -> None:
        self._last_layout = None
        self._task_id = 0
        self._cursor_abs = None
        self._anchor_row = 0
        self._layout_anchor_row = None
        self._call_manager._pending = False

    # =============================================
    # PROMPT
    # =============================================
    def cache_prompt_segments(self) -> list["PromptSegment"]:
        if self.vpriv.prompt_segments is None:
            self.vpriv.prompt_segments = get_prompt_segments(self.vpub.terminal.session)
        return self.vpriv.prompt_segments

    # =============================================
    # SNAPSHOT
    # =============================================
    def _make_snapshot(self) -> dict:
        return {
            "prompt_segments": self.cache_prompt_segments(),
            "buffer": self.vpriv.buffer.copy(),
            "cursor": self.vpriv.cursor,
            "term_width": self.vpub.terminal.session.term_width,
            "term_height": self.vpub.terminal.session.term_height,
            "completions": self.vpriv.completions,
            "completion_index": self.vpriv.completion_index,
            "inline_hint": self.vpriv.inline_hint,
            "style_ctx": self.vpub.style_ctx,
            "semantic_tokens": self.vpriv.semantic_tokens,
        }

    # =============================================
    # TASK
    # =============================================
    def _next_task_id(self) -> int:
        self._task_id += 1
        return self._task_id

    # =============================================
    # PIPELINE
    # =============================================
    async def _render_pipeline(self):
        task_id = self._next_task_id()
        snapshot = self._make_snapshot()
        layout = build_layout(**snapshot)

        if task_id != self._task_id:
            return

        # Выбор режима рендера:
        #
        # Relative mode (как readline по умолчанию):
        #   — позиция курсора не известна точно
        #   — двигаемся относительно текущей позиции
        #   — \r\x1b[J + рисуем вниз + возвращаемся к курсору
        #   — терминал сам скроллит при выходе за нижний край
        #
        # Absolute diff mode:
        #   — позиция известна после CPR или clear_screen
        #   — точечный diff с абсолютной адресацией строк
        #   — быстрее при больших layout, поддерживает скролл явно
        #
        use_abs = self._cursor_abs is not None and self._last_layout is not None

        if use_abs:
            out = self._render_diff(layout)
        else:
            out = self._render_relative(layout)

        if self.vpub.echo and out:
            await self.vpub.terminal.output.output_bytes(out)

        self._last_layout = layout

    # =============================================
    # РЕЖИМ 1: RELATIVE RENDER (default, как readline)
    #
    # Не требует знания абсолютной позиции курсора.
    # Работает правильно всегда — именно этот режим используется
    # по умолчанию до первого CPR запроса.
    #
    # Алгоритм (аналог readline rl_redisplay):
    #   1. Если есть last_layout — поднимаемся к его строке 0
    #   2. \r\x1b[J — в начало строки, очищаем вниз до конца экрана
    #   3. Рисуем весь layout (rendered_ansi + меню)
    #   4. Относительными движениями возвращаемся к курсору
    #
    # _cursor_abs обновляется ТОЛЬКО если уже был заполнен (CPR сделан).
    # Если не был — остаёмся в relative mode и для следующего рендера.
    # =============================================
    def _render_relative(self, layout: "Layout") -> bytes:
        out = b""

        # Шаг 1: поднимаемся к началу прошлого layout
        if self._last_layout is not None:
            rows_up = self._last_layout.cursor_pos.row
            if rows_up > 0:
                out += f"\x1b[{rows_up}A".encode()

        # Шаг 2: в начало строки + очистить до конца экрана
        out += b"\r\x1b[J"

        # Шаг 3: рисуем layout
        out += layout.rendered_ansi.encode("utf-8", errors="replace")

        if layout.pending_wrap:
            out += b"\r\n"

        menu_rows = layout.menu_grid[1] if layout.menu_ansi else 0
        menu_sep  = 1 if menu_rows else 0

        if layout.menu_ansi:
            out += b"\r\n"
            lines = layout.menu_ansi.split("\r\n")
            for i, line in enumerate(lines):
                out += line.encode("utf-8", errors="replace")
                if i < len(lines) - 1:
                    out += b"\r\n"

        # Шаг 4: относительное перемещение к курсору
        # end_pos.row — строка layout где заканчивается контент (после меню)
        # cursor_pos.row — строка layout где должен стоять курсор
        # ИСПРАВЛЕНИЕ: последняя строка меню не имеет \r\n после себя,
        # поэтому курсор после отрисовки меню на 1 строку выше, чем
        # menu_rows + menu_sep. Вычитаем 1, если меню есть.
        rows_up_to_cursor = layout.end_pos.row - layout.cursor_pos.row + menu_rows + menu_sep
        if menu_rows > 0:
            rows_up_to_cursor -= 1
        if rows_up_to_cursor > 0:
            out += f"\x1b[{rows_up_to_cursor}A".encode()
        out += f"\x1b[{layout.cursor_pos.col}G".encode()

        out += b"\x1b[0m"

        # Обновляем _cursor_abs ТОЛЬКО если он был заполнен (CPR уже делался).
        # Если нет — НЕ угадываем позицию, остаёмся в relative mode.
        if self._cursor_abs is not None:
            self._update_abs_after_relative(layout, menu_rows, menu_sep)

        return out

    def _update_abs_after_relative(
        self, layout: "Layout", menu_rows: int, menu_sep: int
    ) -> None:
        """Обновляет _cursor_abs и _anchor_row после relative render."""
        term_height = self.vpub.terminal.session.term_height
        start_row_0 = self._cursor_abs[0] - 1  # 0-based строка где начали рисовать

        # ИСПРАВЛЕНИЕ: учитываем pending_wrap в подсчёте строк
        # и корректируем: последняя строка меню без \r\n
        wrap_adjust = 1 if layout.pending_wrap else 0
        menu_adjust = -1 if menu_rows > 0 else 0
        total_written = layout.end_pos.row + 1 + menu_sep + menu_rows + wrap_adjust + menu_adjust
        bottom_0      = start_row_0 + total_written - 1
        scrolled      = max(0, bottom_0 - (term_height - 1))

        self._anchor_row = max(0, start_row_0 - scrolled)
        # ИСПРАВЛЕНИЕ: сохраняем позицию layout row=0, независимо от курсора
        self._layout_anchor_row = self._anchor_row
        self._cursor_abs = (
            self._anchor_row + layout.cursor_pos.row + 1,
            layout.cursor_pos.col,
        )

    # =============================================
    # РЕЖИМ 2: ABSOLUTE DIFF RENDER
    #
    # Включается только когда _cursor_abs известен (после CPR или clear_screen).
    # Делает точечный diff layout-строк с абсолютной адресацией.
    # Меню диффится отдельно. Курсор ставится ПОСЛЕДНИМ — после меню.
    # =============================================
    def _render_diff(self, layout: "Layout") -> bytes:
        term_height = self.vpub.terminal.session.term_height

        # Anchor: 0-based строка терминала = layout row 0
        # ИСПРАВЛЕНИЕ: используем сохранённый anchor вместо вычисления из cursor_pos
        if self._layout_anchor_row is not None:
            self._anchor_row = self._layout_anchor_row
        else:
            # Fallback для первого рендера после CPR
            cursor_abs_0     = self._cursor_abs[0] - 1
            self._anchor_row = cursor_abs_0 - self._last_layout.cursor_pos.row
        self._anchor_row = max(0, self._anchor_row)

        # Не даём layout вылезти за нижний край терминала
        menu_rows  = layout.menu_grid[1] if layout.menu_ansi else 0
        menu_sep   = 1 if menu_rows else 0
        total      = len(layout.rows) + menu_sep + menu_rows
        max_anchor = max(0, term_height - total)
        self._anchor_row = min(self._anchor_row, max_anchor)

        ops  = self._diff_layouts(self._last_layout, layout)
        ops += self._menu_ops(self._last_layout, layout)

        # Курсор ВСЕГДА последний — menu ops двигают физический курсор в меню
        ops.append(("cursor", layout.cursor_pos))

        out = self._render_ops(ops)

        # Обновляем трек с учётом возможного скролла
        bottom_0 = self._anchor_row + total - 1
        scrolled  = max(0, bottom_0 - (term_height - 1))
        self._anchor_row = max(0, self._anchor_row - scrolled)
        # ИСПРАВЛЕНИЕ: сохраняем позицию layout row=0
        self._layout_anchor_row = self._anchor_row
        self._cursor_abs = (
            self._anchor_row + layout.cursor_pos.row + 1,
            layout.cursor_pos.col,
        )

        return out

    # =============================================
    # DIFF
    # =============================================
    def _diff_layouts(self, old: "Layout", new: "Layout") -> list:
        ops = []
        max_rows = max(len(old.rows), len(new.rows))

        for i in range(max_rows):
            old_row = old.rows[i] if i < len(old.rows) else None
            new_row = new.rows[i] if i < len(new.rows) else None

            if new_row is None:
                ops.append(("clear_row", i))
            elif old_row != new_row:
                ops.append(("draw_row", i, new_row))

        return ops

    # =============================================
    # MENU OPS
    # =============================================
    def _menu_ops(self, old: "Layout", new: "Layout") -> list:
        ops = []
        menu_base_abs = self._anchor_row + len(new.rows)

        old_lines: list[str] = old.menu_ansi.split("\r\n") if old.menu_ansi else []
        new_lines: list[str] = new.menu_ansi.split("\r\n") if new.menu_ansi else []

        max_lines = max(len(old_lines), len(new_lines))

        for i in range(max_lines):
            abs_row  = menu_base_abs + i
            old_line = old_lines[i] if i < len(old_lines) else None
            new_line = new_lines[i] if i < len(new_lines) else None

            if new_line is None:
                ops.append(("clear_abs", abs_row))
            elif old_line != new_line:
                ops.append(("draw_menu", abs_row, new_line))

        return ops

    # =============================================
    # RENDER OPS
    # =============================================
    def _render_ops(self, ops: list) -> bytes:
        out = b""
        current_style: str | None = None

        for op in ops:

            if op[0] == "draw_row":
                _, row_idx, row = op
                abs_row = self._anchor_row + row_idx

                out += f"\x1b[{abs_row + 1};1H".encode()
                out += b"\x1b[2K"

                for cell in row:
                    if not cell.text:
                        continue
                    cell_style = cell.style or ""
                    if cell_style != current_style:
                        if current_style:
                            out += b"\x1b[0m"
                        if cell_style:
                            out += cell_style.encode()
                        current_style = cell_style
                    out += cell.text.encode("utf-8", "replace")

            elif op[0] == "clear_row":
                _, row_idx = op
                abs_row = self._anchor_row + row_idx
                out += f"\x1b[{abs_row + 1};1H".encode()
                out += b"\x1b[2K"

            elif op[0] == "clear_abs":
                _, abs_row = op
                out += f"\x1b[{abs_row + 1};1H".encode()
                out += b"\x1b[2K"

            elif op[0] == "draw_menu":
                _, abs_row, text = op
                out += f"\x1b[{abs_row + 1};1H".encode()
                out += b"\x1b[2K"
                out += text.encode("utf-8", "replace")

            elif op[0] == "cursor":
                _, pos = op
                abs_row = self._anchor_row + pos.row
                out += f"\x1b[{abs_row + 1};{pos.col}H".encode()

        if out:
            out += b"\x1b[0m"

        return out

    # =============================================
    # CPR — запрос позиции курсора у терминала
    # =============================================
    async def request_cursor_position(self) -> None:
        """
        Запрашивает позицию курсора через ESC[6n (DSR).

        После успешного ответа переключает рендер в absolute diff mode.
        Вызывать при инициализации — тогда diff mode активируется
        с первого рендера и работает максимально эффективно.

        Без вызова этого метода рендер работает в relative mode
        (корректно, но без точечного diff по строкам).
        """
        if not self.vpub.echo:
            return

        await self.vpub.terminal.output.output_bytes(b"\x1b[6n")

        try:
            response = await self.vpub.terminal.input.read_until(b"R", timeout=0.05)
        except Exception:
            logger.debug("CPR timeout")
            return

        if not response:
            return

        match = re.search(rb"\x1b\[(\d+);(\d+)R", response)
        if not match:
            return

        row = int(match.group(1))
        col = int(match.group(2))

        self._cursor_abs = (row, col)
        logger.debug("CPR: row=%d col=%d", row, col)