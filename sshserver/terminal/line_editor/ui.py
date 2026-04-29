import asyncio
import logging

from .display import TerminalDriver, ZshRefresh, build_screen, ansi
from .display.builder import build_layout
from sshserver.session.prompt import get_prompt_segments

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .objects import LineEditorPrivateVars, LineEditorPublicVars
    from sshserver.session.types import PromptSegment
    from .types import Layout

logger = logging.getLogger(__name__)


class CallManager:
    def __init__(self, trigger):
        self._pending = False
        self._trigger = trigger
        self._debounce_time = 0.003

    def request(self):
        if not self._pending:
            self._pending = True
            asyncio.create_task(self._debounce())

    async def _debounce(self):
        await asyncio.sleep(self._debounce_time)
        self._pending = False
        await self._trigger()


class LineEditorUI:
    def __init__(self, vpriv: "LineEditorPrivateVars", vpub: "LineEditorPublicVars"):
        self.vpriv = vpriv
        self.vpub = vpub

        self._last_layout: "Layout | None" = None
        self._last_screen = None
        self._task_id = 0
        self._call_manager = CallManager(self._render_pipeline)

        self._driver = TerminalDriver(vpub.terminal)
        self._refresh = ZshRefresh()

        # Relative mode state
        self._last_total_rows = 0   # сколько строк занимал весь блок в прошлый раз
        self._last_term_size = (0, 0)

    # =============================================
    # PUBLIC API (backward compatible)
    # =============================================
    async def redraw(self) -> None:
        self._call_manager.request()

    async def move_cursor_only_or_redraw(self) -> None:
        # Оптимизация cursor-only убрана — всегда полный redraw
        self._call_manager.request()

    async def clear_screen_and_redraw(self) -> None:
        if self.vpub.echo:
            await self._driver.write(ansi.CLEAR_SCREEN + ansi.CURSOR_HOME)
        self._driver.set_abs_pos(1, 1)
        self._reset_state()
        self._call_manager.request()

    def get_last_layout(self) -> "Layout | None":
        return self._last_layout

    def clear_cache(self) -> None:
        self._reset_state()

    def _reset_state(self):
        self._last_layout = None
        self._last_screen = None
        self._task_id = 0
        self._refresh.reset()
        self._driver.clear_abs_pos()
        self._last_total_rows = 0
        self._last_term_size = (0, 0)
        self._call_manager._pending = False

    def cache_prompt_segments(self) -> list["PromptSegment"]:
        if self.vpriv.prompt_segments is None:
            self.vpriv.prompt_segments = get_prompt_segments(self.vpub.terminal.session)
        return self.vpriv.prompt_segments

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

    def _next_task_id(self) -> int:
        self._task_id += 1
        return self._task_id

    # =============================================
    # PIPELINE
    # =============================================
    async def _render_pipeline(self):
        task_id = self._next_task_id()
        snapshot = self._make_snapshot()

        # --- Resize detection ---
        # Если размер изменился, старый _last_total_rows невалиден (другой wrap).
        # Сбрасываем в 0 — следующий рендер не будет подниматься, а просто
        # нарисует с текущей позиции и очистит вниз.
        current_size = (snapshot["term_width"], snapshot["term_height"])
        if self._last_term_size not in ((0, 0), current_size):
            logger.debug("Resize detected %s -> %s", self._last_term_size, current_size)
            self._last_total_rows = 0
            self._refresh.reset()
            self._driver.clear_abs_pos()
        self._last_term_size = current_size

        screen = build_screen(**snapshot)
        self._last_screen = screen

        layout = build_layout(**snapshot)
        self._last_layout = layout

        if task_id != self._task_id:
            return

        # Absolute mode (zsh diff) отключён до стабилизации.
        # Relative mode всегда корректен — единственное требование:
        # курсор терминала должен находиться в конце блока после прошлого рендера.
        out = self._render_relative(screen)

        if self.vpub.echo and out:
            await self._driver.write(out)

    # =============================================
    # RELATIVE RENDER (readline-style)
    # =============================================
    def _render_relative(self, screen) -> bytes:
        out = bytearray()

        # 1. Подъём к началу предыдущего блока.
        #    После прошлого рендера курсор был в конце блока.
        #    Чтобы попасть в начало (row 0 блока), поднимаемся на все строки минус 1.
        rows_up = max(0, self._last_total_rows - 1)
        if rows_up > 0:
            out.extend(ansi.move_up(rows_up))

        # 2. В начало строки + очистить всё вниз до конца экрана.
        #    Это гарантирует, что старый мусор (включая предыдущее меню) стёрт.
        out.extend(ansi.CR + ansi.CLEAR_TO_END_OF_SCREEN)

        # 3. Рисуем input lines (prompt + buffer + hint).
        #    Только hard breaks между ScreenLine. Soft wrap делает терминал сам.
        for i, line in enumerate(screen.lines):
            if i > 0:
                out.extend(ansi.CRLF)
            current_style = ""
            for cell in line.cells:
                if not cell.text:
                    continue
                style = cell.style + ("\x1b[7m" if cell.highlight else "")
                if style != current_style:
                    if current_style:
                        out.extend(ansi.RESET_STYLE)
                    if style:
                        out.extend(style.encode())
                    current_style = style
                out.extend(cell.text.encode("utf-8", "replace"))
            if current_style:
                out.extend(ansi.RESET_STYLE)

        # 4. Меню — всегда под вводом, hard breaks.
        menu_lines = screen.menu_ansi.split("\r\n") if screen.menu_ansi else []
        if menu_lines:
            out.extend(ansi.CRLF)
            for i, line in enumerate(menu_lines):
                out.extend(line.encode("utf-8", "replace"))
                if i < len(menu_lines) - 1:
                    out.extend(ansi.CRLF)

        # 5. Где физически находится курсор ПОСЛЕ отрисовки (0-based от начала блока).
        #    screen.end_pos.row уже учитывает pending_wrap (auto-wrap терминала).
        current_row = screen.end_pos.row + len(menu_lines)
        self._last_total_rows = current_row + 1

        # 6. Возврат курсора в позицию ввода (не в меню).
        rows_up_to_cursor = current_row - screen.cursor_pos.row
        if rows_up_to_cursor > 0:
            out.extend(ansi.move_up(rows_up_to_cursor))
        out.extend(ansi.move_to_column(screen.cursor_pos.col))
        out.extend(ansi.RESET_STYLE)

        return bytes(out)

    # =============================================
    # CPR (reserved for future absolute mode)
    # =============================================
    async def request_cursor_position(self) -> None:
        if not self.vpub.echo:
            return
        pos = await self._driver.request_cursor_position(timeout=0.05)
        if pos:
            logger.debug("CPR: row=%d col=%d", pos[0], pos[1])