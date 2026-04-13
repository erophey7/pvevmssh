import typing as t

from .core import LineEditorCore
from .text_utils import split_graphemes, char_class
from .types import EOF
from . import ui

if t.TYPE_CHECKING:
    from ...lsp_engine import LSPEngine



class LineEditor(LineEditorCore):
    async def reset(self) -> None:
        async with self._lock:
            self._reset_state()

    async def on_terminal_resize(self) -> None:
        async with self._lock:
            await ui.redraw(self)

    async def feed_char(self, char: str) -> None:
        await self.feed_text(char)

    async def feed_text(self, text: str) -> None:
        async with self._lock:
            if not text:
                return

            if self._quoted_insert:
                self._quoted_insert = False

            insert = split_graphemes(text)
            if not insert:
                return

            self._buffer[self._cursor:self._cursor] = insert
            self._cursor += len(insert)

            self._completions = None
            self._inline_hint = None
            self._lsp_adapter.schedule_inline_hint(self)
            self._history_navigation_active = False
            await ui.redraw(self)

    async def enter(self) -> str:
        async with self._lock:
            self._last_layout = None
            await self.terminal.output.output_bytes(b"\r\n")
            line = "".join(self._buffer)

            if line.strip():
                self.history.add(line)

            self._reset_state()
            return line

    async def ctrl_c(self) -> str:
        async with self._lock:
            self._reset_state()
            await self.terminal.output.output_bytes(b"^C\r\n")
            return ""

    async def ctrl_d(self) -> t.Optional[str]:
        async with self._lock:
            if not self._buffer:
                return EOF
            return None

    async def backspace(self) -> None:
        async with self._lock:
            if self._cursor <= 0:
                return
            self._cursor -= 1
            self._buffer.pop(self._cursor)
            self._completions = None
            self._inline_hint = None
            self._lsp_adapter.schedule_inline_hint(self)
            self._history_navigation_active = False
            await ui.redraw(self)

    async def delete(self) -> None:
        async with self._lock:
            if self._cursor >= len(self._buffer):
                return
            self._buffer.pop(self._cursor)

            # Скрываем меню
            self._completions = None
            self._inline_hint = None
            self._lsp_adapter.schedule_inline_hint(self)
            self._awaiting_menu = False
            self._history_navigation_active = False
            await ui.redraw(self)

    async def ctrl_backspace(self) -> None:
        async with self._lock:
            if self._cursor <= 0:
                return

            while self._cursor > 0 and char_class(self._buffer[self._cursor - 1]) == "ws":
                self._cursor -= 1
                self._buffer.pop(self._cursor)

            if self._cursor > 0:
                cls = char_class(self._buffer[self._cursor - 1])
                while self._cursor > 0 and char_class(self._buffer[self._cursor - 1]) == cls:
                    self._cursor -= 1
                    self._buffer.pop(self._cursor)

            # Скрываем меню
            self._completions = None
            self._inline_hint = None
            self._awaiting_menu = False
            self._history_navigation_active = False
            await ui.redraw(self)

    async def ctrl_delete(self) -> None:
        async with self._lock:
            if self._cursor >= len(self._buffer):
                return

            while self._cursor < len(self._buffer) and char_class(self._buffer[self._cursor]) == "ws":
                self._buffer.pop(self._cursor)

            if self._cursor < len(self._buffer):
                cls = char_class(self._buffer[self._cursor])
                while self._cursor < len(self._buffer) and char_class(self._buffer[self._cursor]) == cls:
                    self._buffer.pop(self._cursor)

            # Скрываем меню
            self._completions = None
            self._inline_hint = None
            self._awaiting_menu = False
            self._history_navigation_active = False
            await ui.redraw(self)

    async def ctrl_u(self) -> None:
        async with self._lock:
            if self._cursor <= 0:
                return
            del self._buffer[:self._cursor]
            self._cursor = 0

            # Скрываем меню
            self._completions = None
            self._inline_hint = None
            self._awaiting_menu = False
            self._history_navigation_active = False
            await ui.redraw(self)

    async def ctrl_k(self) -> None:
        async with self._lock:
            if self._cursor >= len(self._buffer):
                return
            del self._buffer[self._cursor:]

            # Скрываем меню
            self._completions = None
            self._inline_hint = None
            self._awaiting_menu = False
            self._history_navigation_active = False
            await ui.redraw(self)

    async def ctrl_l(self) -> None:
        async with self._lock:
            await ui.clear_screen_and_redraw(self)

    async def quoted_insert(self) -> None:
        async with self._lock:
            self._quoted_insert = True

    async def cursor_left(self) -> None:
        async with self._lock:
            if self._cursor <= 0:
                return
            self._cursor -= 1
            self._completions = None
            self._inline_hint = None
            self._awaiting_menu = False
            await ui.move_cursor_only_or_redraw(self)

    async def cursor_right(self) -> None:
        async with self._lock:
            if self._cursor >= len(self._buffer):
                return
            self._cursor += 1
            self._completions = None
            self._inline_hint = None
            self._awaiting_menu = False
            await ui.move_cursor_only_or_redraw(self)

    async def cursor_word_left(self) -> None:
        async with self._lock:
            if self._cursor <= 0:
                return

            while self._cursor > 0 and char_class(self._buffer[self._cursor - 1]) == "ws":
                self._cursor -= 1

            if self._cursor > 0:
                cls = char_class(self._buffer[self._cursor - 1])
                while self._cursor > 0 and char_class(self._buffer[self._cursor - 1]) == cls:
                    self._cursor -= 1

            # Скрываем меню
            self._completions = None
            self._inline_hint = None
            self._awaiting_menu = False
            await ui.move_cursor_only_or_redraw(self)

    async def cursor_word_right(self) -> None:
        async with self._lock:
            if self._cursor >= len(self._buffer):
                return

            while self._cursor < len(self._buffer) and char_class(self._buffer[self._cursor]) == "ws":
                self._cursor += 1

            if self._cursor < len(self._buffer):
                cls = char_class(self._buffer[self._cursor])
                while self._cursor < len(self._buffer) and char_class(self._buffer[self._cursor]) == cls:
                    self._cursor += 1

            # Скрываем меню
            self._completions = None
            self._inline_hint = None
            self._awaiting_menu = False
            await ui.move_cursor_only_or_redraw(self)

    async def cursor_home(self) -> None:
        async with self._lock:
            if self._cursor == 0:
                return
            self._cursor = 0
            # Скрываем меню
            self._completions = None
            self._inline_hint = None
            self._awaiting_menu = False
            await ui.move_cursor_only_or_redraw(self)

    async def cursor_end(self) -> None:
        async with self._lock:
            if self._cursor == len(self._buffer):
                return
            self._cursor = len(self._buffer)
            # Скрываем меню
            self._completions = None
            self._inline_hint = None
            self._awaiting_menu = False
            await ui.move_cursor_only_or_redraw(self)

    async def history_up(self) -> None:
        async with self._lock:
            if not self._history_navigation_active:
                self._history_draft = self._buffer.copy()
                self._history_navigation_active = True

            # Скрываем меню при работе с историей
            self._completions = None
            self._inline_hint = None
            self._awaiting_menu = False

            prev = self.history.previous()
            if prev is None:
                return

            self._buffer = split_graphemes(prev)
            self._cursor = len(self._buffer)
            await ui.redraw(self)

    async def history_down(self) -> None:
        async with self._lock:
            if not self._history_navigation_active:
                return

            # Скрываем меню при работе с историей
            self._completions = None
            self._inline_hint = None
            self._awaiting_menu = False

            nxt = self.history.next()

            if nxt is None or nxt == "":
                if self._history_draft is not None:
                    self._buffer = self._history_draft.copy()
                    self._cursor = len(self._buffer)

                self._history_navigation_active = False
                self._history_draft = None
                self.history.reset_index()

                await ui.redraw(self)
                return

            self._buffer = split_graphemes(nxt)
            self._cursor = len(self._buffer)
            await ui.redraw(self)

    async def history_search_backward(self) -> None:
        return

    # ==================== TAB + MENU LOGIC ====================
    async def tab_complete(self) -> None:
        """Tab при открытом меню = следующий вариант. Иначе — запрос LSP."""
        async with self._lock:
            if self._completions and len(self._completions) > 1:
                self._completion_index = (self._completion_index + 1) % len(self._completions)
                await ui.redraw(self)
                return

            if not self._lsp_adapter:
                return
            await self._lsp_adapter.tab_complete(self)

    async def accept_inline_hint(self) -> None:
        """Принимаем ghost-подсказку (вызывается стрелкой →)"""
        async with self._lock:
            if not self._inline_hint:
                return
            insert = split_graphemes(self._inline_hint)
            self._buffer[self._cursor:self._cursor] = insert
            self._cursor += len(insert)
            self._inline_hint = None
            self._completions = None
            self._history_navigation_active = False
            await ui.redraw(self)

    async def show_completions(self, candidates: list[str]) -> None:
        async with self._lock:
            if not candidates or len(candidates) <= 1:
                self._completions = None
                self._inline_hint = None
                await ui.redraw(self)
                return
            self._completions = candidates
            self._completion_index = 0
            self._history_navigation_active = False
            await ui.redraw(self)

    # ==================== МЕНЮ НАВИГАЦИЯ (стрелки) ====================
    def _get_menu_columns(self) -> int:
        """Пропорциональное количество колонок.
        Теперь полностью совпадает с логикой layout.py (+3 и menu_start_col=1)."""
        if not self._completions or len(self._completions) <= 1:
            return 1

        term_width = getattr(self.terminal.session, "term_width", 80)
        max_len = max(len(c) for c in self._completions) + 3      # точно как в layout.py

        # меню всегда прижато к левому краю (col=1)
        available_width = term_width
        return max(1, available_width // max_len)

    async def menu_up(self) -> None:
        async with self._lock:
            if not self._completions:
                return
            cols = self._get_menu_columns()
            num = len(self._completions)
            self._completion_index = (self._completion_index - cols) % num
            await ui.redraw(self)

    async def menu_down(self) -> None:
        async with self._lock:
            if not self._completions:
                return
            cols = self._get_menu_columns()
            num = len(self._completions)
            self._completion_index = (self._completion_index + cols) % num
            await ui.redraw(self)

    async def menu_left(self) -> None:
        async with self._lock:
            if not self._completions:
                return
            num = len(self._completions)
            self._completion_index = (self._completion_index - 1) % num
            await ui.redraw(self)

    async def menu_right(self) -> None:
        async with self._lock:
            if not self._completions:
                return
            num = len(self._completions)
            self._completion_index = (self._completion_index + 1) % num
            await ui.redraw(self)

    async def menu_accept(self) -> None:
        async with self._lock:
            if not self._completions or self._completion_index is None:
                return

            selected = self._completions[self._completion_index]

            start = self._cursor
            while start > 0 and char_class(self._buffer[start - 1]) == "word":
                start -= 1

            del self._buffer[start:self._cursor]
            insert = split_graphemes(selected)
            self._buffer[start:start] = insert
            self._cursor = start + len(insert)

            self._completions = None
            self._inline_hint = None
            self._history_navigation_active = False
            await ui.redraw(self)

    async def menu_cancel(self) -> None:
        async with self._lock:
            self._completions = None
            self._inline_hint = None
            self._history_navigation_active = False
            await ui.redraw(self)

    def set_lsp_engine(self, engine) -> None:
        """Подключить LSP engine (вызывается снаружи, например из handle_client)."""
        if self._lsp_adapter:
            self._lsp_adapter.set_engine(engine)

    async def arrow_up(self) -> None:
        if self._completions:
            await self.menu_up()
        else:
            await self.history_up()

    async def arrow_down(self) -> None:
        if self._completions:
            await self.menu_down()
        else:
            await self.history_down()

    async def arrow_left(self) -> None:
        if self._completions:
            await self.menu_left()
        else:
            await self.cursor_left()

    async def arrow_right(self) -> None:
        if self._completions:
            await self.menu_right()
        elif self._inline_hint and self._cursor == len(self._buffer):
            await self.accept_inline_hint()
        else:
            await self.cursor_right()

    def set_lsp_engine(self, engine) -> None:
        if self._lsp_adapter:
            self._lsp_adapter.set_engine(engine)