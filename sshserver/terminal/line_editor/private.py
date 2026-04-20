# project objects & funcs
from sshserver.session import CommandHistory, get_current_session
from helpers.globals import GlobalStore

# self objects & internal
from .objects import LineEditorPrivateVars, LineEditorPublicVars
from .private_internal import LineEditorPrivateInternal
from .lsp_adapter import LSPAdapter


# self funcs
from .text_utils import split_graphemes, char_class
from .types import EOF
from .ui import LineEditorUI

# other imports
from typing import Optional

import logging
logger = logging.getLogger(__name__)


class LineEditorLogic:
    # ===============================================
    # INIT LOGIC
    # ===============================================
    def __init__(self, terminal):
        self.vpriv = LineEditorPrivateVars()
        self.vpub = LineEditorPublicVars(terminal)
        self.internal = LineEditorPrivateInternal(self.vpriv, self.vpub, self)

        self.ui = LineEditorUI(self.vpriv, self.vpub)
        self.lsp_adapter = LSPAdapter(self.vpriv, self.vpub, self.ui)

        self.ensure()

    def ensure(self) -> None:
        session = get_current_session()
        config = GlobalStore.get().require("config")
        if session:
            self.vpub.history = session.extra.get(
                "history", 
                CommandHistory(
                    max_size=config.get("db.limits.history", 1000), 
                    session=session
                    )
            )

    # ===============================================
    # TRANSFER VARS
    # ===============================================    
    def get_priv_vars(self):
        return self.vpriv

    def get_pub_vars(self):
        return self.vpub
    
    def get_lsp_adapter(self):
        if hasattr(self, "lsp_adapter"):
            return self.lsp_adapter
    
    # ===============================================
    # RESET
    # ===============================================    
    async def reset_state(self) -> None:
        async with self.vpriv.lock:
            self.internal.reset_state()

    # ===============================================
    # CURRENT LINE
    # ===============================================  
    def current_line(self) -> str:
        return "".join(self.vpriv.buffer)

    # ===============================================
    # FEED TEXT
    # ===============================================  
    async def feed_text(self, text: str) -> None:
        async with self.vpriv.lock:
            if not text:
                return

            if self.vpriv.quoted_insert:
                self.vpriv.quoted_insert = False

            insert = split_graphemes(text)
            if not insert:
                return

            self.vpriv.buffer[self.vpriv.cursor:self.vpriv.cursor] = insert
            self.vpriv.cursor += len(insert)

            self.vpriv.completions = None
            self.vpriv.inline_hint = None
            self.lsp_adapter.schedule_inline_hint()
            self.lsp_adapter.schedule_semantic_highlight()
            self.vpriv.history_navigation_active = False
            await self.ui.redraw()

    # ===============================================
    # RESIZE
    # ===============================================  
    async def resize(self) -> None:
        async with self.vpriv.lock:
            await self.ui.redraw()

    # ===============================================
    # ENTER TEXT ACTION
    # ===============================================    
    async def enter(self) -> str:
        async with self.vpriv.lock:
            self.vpriv.last_layout = None
            await self.vpub.terminal.output.output_bytes(b"\r\n")
            line = "".join(self.vpriv.buffer)

            if line.strip():
                self.vpub.history.add(line)

            self.internal.reset_state()
            return line
        
    # ===============================================
    # TAB COMPLETE
    # ===============================================
    async def tab_complete(self) -> None:
        async with self.vpriv.lock:
            if not self.lsp_adapter:
                return
            await self.lsp_adapter.tab_complete()
        
    # ===============================================
    # REQUEST MENU
    # ===============================================
    async def menu_request(self) -> None:
        async with self.vpriv.lock:
            if self.vpriv.completions and len(self.vpriv.completions) > 1:
                if self.vpriv.completion_index is None:
                    self.vpriv.completion_index = 0
                await self.ui.redraw()
                return

    # ===============================================
    # MENU ACCEPT
    # ===============================================
    async def menu_accept(self) -> None:
        async with self.vpriv.lock:
            if self.vpriv.completions is not None:
                await self.lsp_adapter.menu_accept()
                self.lsp_adapter.schedule_semantic_highlight()

    # ===============================================
    # INLINE HINT ACCEPT
    # ===============================================
    async def accept_inline_hint(self) -> None:
        """Принимаем ghost-подсказку (вызывается стрелкой →)"""
        async with self.vpriv.lock:
            if not self.vpriv.inline_hint:
                return
            insert = split_graphemes(self.vpriv.inline_hint)
            self.vpriv.buffer[self.vpriv.cursor:self.vpriv.cursor] = insert
            self.vpriv.cursor += len(insert)
            self.vpriv.inline_hint = None
            self.vpriv.completions = None
            self.vpriv.history_navigation_active = False
            self.lsp_adapter.schedule_semantic_highlight()
            await self.ui.redraw()

    # ===============================================
    # HIDE MENU
    # ===============================================
    async def menu_hide(self) -> None:
        async with self.vpriv.lock:
            self.internal.menu_hide()
            await self.ui.redraw()

    # ===============================================
    # MENU NAV
    # ===============================================
    async def menu_up(self) -> None:
        async with self.vpriv.lock:
            if not self.vpriv.completions:
                return
            if self.vpriv.last_layout is None:
                return
            cols, _ = self.vpriv.last_layout.menu_grid
            num = len(self.vpriv.completions)

            if self.vpriv.completion_index is None:
                self.vpriv.completion_index = 0

            idx = self.vpriv.completion_index
            col = idx % cols

            prev_idx = idx - cols

            if prev_idx >= 0:
                self.vpriv.completion_index = prev_idx
            else:
                # переходим в предыдущую колонку
                prev_col = col - 1

                if prev_col >= 0:
                    # последний элемент в этой колонке
                    self.vpriv.completion_index = (
                        prev_col + cols * ((num - 1 - prev_col) // cols)
                    )
                else:
                    # если были в первой колонке → в конец
                    last_col = cols - 1
                    self.vpriv.completion_index = (
                        last_col + cols * ((num - 1 - last_col) // cols)
                    )

            await self.ui.redraw()

    async def menu_down(self) -> None:
        async with self.vpriv.lock:
            if not self.vpriv.completions:
                return

            if self.vpriv.last_layout is None:
                return
            cols, _ = self.vpriv.last_layout.menu_grid
            num = len(self.vpriv.completions)

            if self.vpriv.completion_index is None:
                self.vpriv.completion_index = 0

            idx = self.vpriv.completion_index
            col = idx % cols

            # шаг вниз внутри колонки
            next_idx = idx + cols

            if next_idx < num:
                self.vpriv.completion_index = next_idx
            else:
                # переход на следующую колонку
                next_col = col + 1
                if next_col < cols:
                    self.vpriv.completion_index = next_col
                else:
                    # если были в последней колонке → в начало
                    self.vpriv.completion_index = 0

            await self.ui.redraw()

    async def menu_prev(self) -> None:
        async with self.vpriv.lock:
            if not self.vpriv.completions:
                return
            num = len(self.vpriv.completions)
            if self.vpriv.completion_index is None:
                self.vpriv.completion_index = 0
            self.vpriv.completion_index = (self.vpriv.completion_index - 1) % num
            await self.ui.redraw()

    async def menu_next(self) -> None:
        async with self.vpriv.lock:
            if not self.vpriv.completions:
                return
            num = len(self.vpriv.completions)
            if self.vpriv.completion_index is None:
                self.vpriv.completion_index = 0
            self.vpriv.completion_index = (self.vpriv.completion_index + 1) % num
            await self.ui.redraw()

    # ===============================================
    # CURSOR 
    # ===============================================
    async def cursor_left(self) -> None:
        async with self.vpriv.lock:
            if self.vpriv.cursor <= 0:
                return
            self.vpriv.cursor -= 1
            self.internal.menu_hide()
            await self.ui.move_cursor_only_or_redraw()

    async def cursor_right(self) -> None:
        async with self.vpriv.lock:
            if self.vpriv.cursor >= len(self.vpriv.buffer):
                return
            self.vpriv.cursor += 1
            self.internal.menu_hide()
            await self.ui.move_cursor_only_or_redraw()

    async def cursor_word_left(self) -> None:
        async with self.vpriv.lock:
            if self.vpriv.cursor <= 0:
                return

            while self.vpriv.cursor > 0 and char_class(self.vpriv.buffer[self.vpriv.cursor - 1]) == "ws":
                self.vpriv.cursor -= 1

            if self.vpriv.cursor > 0:
                cls = char_class(self.vpriv.buffer[self.vpriv.cursor - 1])
                while self.vpriv.cursor > 0 and char_class(self.vpriv.buffer[self.vpriv.cursor - 1]) == cls:
                    self.vpriv.cursor -= 1


            self.internal.menu_hide()
            await self.ui.move_cursor_only_or_redraw()

    async def cursor_word_right(self) -> None:
        async with self.vpriv.lock:
            if self.vpriv.cursor >= len(self.vpriv.buffer):
                return

            while self.vpriv.cursor < len(self.vpriv.buffer) and char_class(self.vpriv.buffer[self.vpriv.cursor]) == "ws":
                self.vpriv.cursor += 1

            if self.vpriv.cursor < len(self.vpriv.buffer):
                cls = char_class(self.vpriv.buffer[self.vpriv.cursor])
                while self.vpriv.cursor < len(self.vpriv.buffer) and char_class(self.vpriv.buffer[self.vpriv.cursor]) == cls:
                    self.vpriv.cursor += 1


            self.internal.menu_hide()
            await self.ui.move_cursor_only_or_redraw()

    async def cursor_home(self) -> None:
        async with self.vpriv.lock:
            if self.vpriv.cursor == 0:
                return
            self.vpriv.cursor = 0

            self.internal.menu_hide()
            await self.ui.move_cursor_only_or_redraw()

    async def cursor_end(self) -> None:
        async with self.vpriv.lock:
            if self.vpriv.cursor == len(self.vpriv.buffer):
                return
            self.vpriv.cursor = len(self.vpriv.buffer)

            self.internal.menu_hide()
            await self.ui.move_cursor_only_or_redraw()

    # ===============================================
    # HISTORY 
    # ===============================================
    async def history_up(self) -> None:
        async with self.vpriv.lock:
            if not self.vpriv.history_navigation_active:
                self.vpriv.history_draft = self.vpriv.buffer.copy()
                self.vpriv.history_navigation_active = True

            self.internal.menu_hide()

            prev = self.vpub.history.previous()
            if prev is None:
                return

            self.vpriv.buffer = split_graphemes(prev)
            self.vpriv.cursor = len(self.vpriv.buffer)
            await self.ui.redraw()

    async def history_down(self) -> None:
        async with self.vpriv.lock:
            if not self.vpriv.history_navigation_active:
                return

            self.internal.menu_hide()

            nxt = self.vpub.history.next()

            if nxt is None or nxt == "":
                if self.vpriv.history_draft is not None:
                    self.vpriv.buffer = self.vpriv.history_draft.copy()
                    self.vpriv.cursor = len(self.vpriv.buffer)

                self.vpriv.history_navigation_active = False
                self.vpriv.history_draft = None
                self.vpub.history.reset_index()

                await self.ui.redraw()
                return

            self.vpriv.buffer = split_graphemes(nxt)
            self.vpriv.cursor = len(self.vpriv.buffer)
            await self.ui.redraw()

    async def history_search_backward(self) -> None:
        return
    
    # ===============================================
    # DELETING 
    # ===============================================
    async def char_left_del(self) -> None:
        async with self.vpriv.lock:
            if self.vpriv.cursor <= 0:
                return
            self.vpriv.cursor -= 1
            self.vpriv.buffer.pop(self.vpriv.cursor)
            self.internal.menu_hide()
            self.lsp_adapter.schedule_inline_hint()
            self.lsp_adapter.schedule_semantic_highlight()
            self.vpriv.history_navigation_active = False
            await self.ui.redraw()

    async def char_right_del(self) -> None:
        async with self.vpriv.lock:
            if self.vpriv.cursor >= len(self.vpriv.buffer):
                return
            self.vpriv.buffer.pop(self.vpriv.cursor)

            self.internal.menu_hide()
            self.lsp_adapter.schedule_inline_hint()
            self.lsp_adapter.schedule_semantic_highlight()
            self.vpriv.history_navigation_active = False
            await self.ui.redraw()

    async def word_left_del(self) -> None:
        async with self.vpriv.lock:
            if self.vpriv.cursor <= 0:
                return

            while self.vpriv.cursor > 0 and char_class(self.vpriv.buffer[self.vpriv.cursor - 1]) == "ws":
                self.vpriv.cursor -= 1
                self.vpriv.buffer.pop(self.vpriv.cursor)

            if self.vpriv.cursor > 0:
                cls = char_class(self.vpriv.buffer[self.vpriv.cursor - 1])
                while self.vpriv.cursor > 0 and char_class(self.vpriv.buffer[self.vpriv.cursor - 1]) == cls:
                    self.vpriv.cursor -= 1
                    self.vpriv.buffer.pop(self.vpriv.cursor)

            self.internal.menu_hide()
            self.vpriv.history_navigation_active = False
            await self.ui.redraw()

    async def word_right_del(self) -> None:
        async with self.vpriv.lock:
            if self.vpriv.cursor >= len(self.vpriv.buffer):
                return

            while self.vpriv.cursor < len(self.vpriv.buffer) and char_class(self.vpriv.buffer[self.vpriv.cursor]) == "ws":
                self.vpriv.buffer.pop(self.vpriv.cursor)

            if self.vpriv.cursor < len(self.vpriv.buffer):
                cls = char_class(self.vpriv.buffer[self.vpriv.cursor])
                while self.vpriv.cursor < len(self.vpriv.buffer) and char_class(self.vpriv.buffer[self.vpriv.cursor]) == cls:
                    self.vpriv.buffer.pop(self.vpriv.cursor)

            self.internal.menu_hide()
            self.vpriv.history_navigation_active = False
            await self.ui.redraw()

    async def home_del(self) -> None:
        async with self.vpriv.lock:
            if self.vpriv.cursor <= 0:
                return
            del self.vpriv.buffer[:self.vpriv.cursor]
            self.vpriv.cursor = 0

            self.internal.menu_hide()
            self.vpriv.history_navigation_active = False
            await self.ui.redraw()

    async def end_del(self) -> None:
        async with self.vpriv.lock:
            if self.vpriv.cursor >= len(self.vpriv.buffer):
                return
            del self.vpriv.buffer[self.vpriv.cursor:]

            self.internal.menu_hide()
            self.vpriv.history_navigation_active = False
            await self.ui.redraw()

    # ===============================================
    # QUOTED INSERT
    # ===============================================
    async def quoted_insert(self) -> None:
        async with self.vpriv.lock:
            self.vpriv.quoted_insert = True

    # ===============================================
    # OTHER KEYFUNC
    # ===============================================
    async def clear_screen(self) -> None:
        async with self.vpriv.lock:
            await self.ui.clear_screen_and_redraw(self)

    async def ctrlc_cancellation(self) -> str:
        async with self.vpriv.lock:
            self.internal.reset_state()
            await self.ui.redraw()
            await self.vpub.terminal.output.output_bytes(b"^C\r\n")
            return ""
        
    async def ctrld_exiting(self) -> Optional[str]:
        async with self.vpriv.lock:
            if not self.vpriv.buffer:
                return EOF
            return None