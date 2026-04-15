"""
Performing silent refactor
in testing
"""

# ===============================================
# IMPORTS
# ===============================================  
# project objects & funcs
from sshserver.session import CommandHistory, get_current_session
from helpers.globals import GlobalStore

# self objects & internal
from ._objects import LineEditorPrivateVars, LineEditorPublicVars
from ._private_internal import LineEditorPrivateInternal


# self funcs
from .text_utils import split_graphemes, char_class
from .types import EOF
from . import ui

# other imports
from typing import Optional


# temp proxy
class EditorProxy:
    _map = {
        "_buffer": ("vpriv", "buffer"),
        "_cursor": ("vpriv", "cursor"),
        "_completions": ("vpriv", "completions"),
        "_completion_index": ("vpriv", "completion_index"),
        "_inline_hint": ("vpriv", "inline_hint"),
        "_last_layout": ("vpriv", "last_layout"),
        "_prompt_segments": ("vpriv", "prompt_segments"),
        "_awaiting_menu": ("vpriv", "awaiting_menu"),
        "_history_navigation_active": ("vpriv", "history_navigation_active"),

        "terminal": ("vpub", "terminal"),
        "style_ctx": ("vpub", "style_ctx"),
        "echo": ("vpub", "echo"),
    }

    def __init__(self, vpriv, vpub):
        object.__setattr__(self, "_vpriv", vpriv)
        object.__setattr__(self, "_vpub", vpub)

    def __getattr__(self, name):
        if name in self._map:
            src, attr = self._map[name]
            target = self._vpriv if src == "vpriv" else self._vpub
            return getattr(target, attr)

        raise AttributeError(name)

    def __setattr__(self, name, value):
        if name in self._map:
            src, attr = self._map[name]
            target = self._vpriv if src == "vpriv" else self._vpub
            setattr(target, attr, value)
        else:
            object.__setattr__(self, name, value)


class LineEditorLogic:
    # ===============================================
    # INIT LOGIC
    # ===============================================
    def __init__(self, terminal):
        self.vpriv = LineEditorPrivateVars()
        self.vpub = LineEditorPublicVars(terminal)
        self.internal = LineEditorPrivateInternal(self.vpriv, self.vpub)

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
    
    # ===============================================
    # RESET
    # ===============================================    
    async def reset_state(self) -> None:
        async with self.vpriv.lock:
            self.internal.reset_state()

    # ===============================================
    # CURRENT LINE FUNC
    # ===============================================  
    def current_line(self) -> str:
        return "".join(self.vpriv.buffer)
    
    # ===============================================
    # TEMP REFACTOR OVERRIDES
    # ===============================================  
    async def ___move_cursor_only_or_redraw(self) -> None:
        editor = EditorProxy(self.vpriv, self.vpub)
        await ui.move_cursor_only_or_redraw(editor)

    async def ___redraw(self) -> None:
        editor = EditorProxy(self.vpriv, self.vpub)
        await ui.redraw(editor)

    async def ___tab_complete(self) -> None:
        editor = EditorProxy(self.vpriv, self.vpub)
        await self.vpriv.lsp_adapter.tab_complete(editor)

    async def ___menu_accept(self) -> None:
        editor = EditorProxy(self.vpriv, self.vpub)
        await self.vpriv.lsp_adapter.menu_accept(editor)

    async def ___schedule_inline_hint(self) -> None:
        editor = EditorProxy(self.vpriv, self.vpub)
        self.vpriv.lsp_adapter.schedule_inline_hint(editor)

    # ===============================================
    # FEED TEXT (redraw, schedule_inline_hint)
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
            await self.___schedule_inline_hint()
            self.vpriv.history_navigation_active = False
            await self.___redraw()

    # ===============================================
    # RESIZE (redraw)
    # ===============================================  
    async def resize(self) -> None:
        async with self.vpriv.lock:
            await self.___redraw()

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
    # TAB COMPLETE (tab_complete)
    # ===============================================
    async def tab_complete(self) -> None:
        async with self.vpriv.lock:
            if not self.vpriv.lsp_adapter:
                return
            await self.___tab_complete()
        
    # ===============================================
    # REQUEST MENU (redraw)
    # ===============================================
    async def menu_request(self) -> None:
        async with self.vpriv.lock:
            if self.vpriv.completions and len(self.vpriv.completions) > 1:
                if self.vpriv.completion_index is None:
                    self.vpriv.completion_index = 0
                await self.___redraw()
                return

    # ===============================================
    # MENU ACCEPT (menu_accept)
    # ===============================================
    async def menu_accept(self) -> None:
        async with self.vpriv.lock:
            if self.vpriv.completions is not None:
                await self.___menu_accept()

    # ===============================================
    # INLINE HINT ACCEPT (redraw)
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
            await self.___redraw()

    # ===============================================
    # HIDE MENU (redraw)
    # ===============================================
    async def menu_hide(self) -> None:
        async with self.vpriv.lock:
            self.internal.menu_hide()
            await self.___redraw()

    # ===============================================
    # MENU NAV (redraw)
    # ===============================================
    async def menu_up(self) -> None:
        async with self.vpriv.lock:
            if not self.vpriv.completions:
                return
            cols = self.internal.get_menu_columns()
            num = len(self.vpriv.completions)
            self.vpriv.completion_index = (self.vpriv.completion_index - cols) % num
            await self.___redraw()

    async def menu_down(self) -> None:
        async with self.vpriv.lock:
            if not self.vpriv.completions:
                return
            cols = self.internal.get_menu_columns()
            num = len(self.vpriv.completions)
            self.vpriv.completion_index = (self.vpriv.completion_index + cols) % num
            await self.___redraw()

    async def menu_prev(self) -> None:
        async with self.vpriv.lock:
            if not self.vpriv.completions:
                return
            num = len(self.vpriv.completions)
            self.vpriv.completion_index = (self.vpriv.completion_index - 1) % num
            await self.___redraw()

    async def menu_next(self) -> None:
        async with self.vpriv.lock:
            if not self.vpriv.completions:
                return
            num = len(self.vpriv.completions)
            self.vpriv.completion_index = (self.vpriv.completion_index + 1) % num
            await self.___redraw()

    # ===============================================
    # CURSOR (move_cursor_only_or_redraw)
    # ===============================================
    async def cursor_left(self) -> None:
        async with self.vpriv.lock:
            if self.vpriv.cursor <= 0:
                return
            self.vpriv.cursor -= 1
            self.internal.menu_hide
            await self.___move_cursor_only_or_redraw()

    async def cursor_right(self) -> None:
        async with self.vpriv.lock:
            if self.vpriv.cursor >= len(self.vpriv.buffer):
                return
            self.vpriv.cursor += 1
            self.internal.menu_hide
            await self.___move_cursor_only_or_redraw()

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


            self.internal.menu_hide
            await self.___move_cursor_only_or_redraw()

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


            self.internal.menu_hide
            await self.___move_cursor_only_or_redraw()

    async def cursor_home(self) -> None:
        async with self.vpriv.lock:
            if self.vpriv.cursor == 0:
                return
            self.vpriv.cursor = 0

            self.internal.menu_hide
            await self.___move_cursor_only_or_redraw()

    async def cursor_end(self) -> None:
        async with self.vpriv.lock:
            if self.vpriv.cursor == len(self.vpriv.buffer):
                return
            self.vpriv.cursor = len(self.vpriv.buffer)

            self.internal.menu_hide
            await self.___move_cursor_only_or_redraw()

    # ===============================================
    # HISTORY (redraw)
    # ===============================================
    async def history_up(self) -> None:
        async with self.vpriv.lock:
            if not self.vpriv.history_navigation_active:
                self.vpriv.history_draft = self.vpriv.buffer.copy()
                self.vpriv.history_navigation_active = True

            self.internal.menu_hide

            prev = self.vpub.history.previous()
            if prev is None:
                return

            self.vpriv.buffer = split_graphemes(prev)
            self.vpriv.cursor = len(self.vpriv.buffer)
            await self.___redraw()

    async def history_down(self) -> None:
        async with self.vpriv.lock:
            if not self.vpriv.history_navigation_active:
                return

            self.internal.menu_hide

            nxt = self.vpub.history.next()

            if nxt is None or nxt == "":
                if self.vpriv.history_draft is not None:
                    self.vpriv.buffer = self.vpriv.history_draft.copy()
                    self.vpriv.cursor = len(self.vpriv.buffer)

                self.vpriv.history_navigation_active = False
                self.vpriv.history_draft = None
                self.vpub.history.reset_index()

                await self.___redraw()
                return

            self.vpriv.buffer = split_graphemes(nxt)
            self.vpriv.cursor = len(self.vpriv.buffer)
            await self.___redraw()

    async def history_search_backward(self) -> None:
        return
    
    # ===============================================
    # DELETING (redraw, schedule_inline_hint)
    # ===============================================
    async def char_left_del(self) -> None:
        async with self.vpriv.lock:
            if self.vpriv.cursor <= 0:
                return
            self.vpriv.cursor -= 1
            self.vpriv.buffer.pop(self.vpriv.cursor)
            self.internal.menu_hide
            await self.___schedule_inline_hint()
            self.vpriv.history_navigation_active = False
            await self.___redraw()

    async def char_right_del(self) -> None:
        async with self.vpriv.lock:
            if self.vpriv.cursor >= len(self.vpriv.buffer):
                return
            self.vpriv.buffer.pop(self.vpriv.cursor)

            self.internal.menu_hide
            await self.___schedule_inline_hint()
            self.vpriv.history_navigation_active = False
            await self.___redraw()

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

            self.internal.menu_hide
            self.vpriv.history_navigation_active = False
            await self.___redraw()

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

            self.internal.menu_hide
            self.vpriv.history_navigation_active = False
            await self.___redraw()

    async def home_del(self) -> None:
        async with self.vpriv.lock:
            if self.vpriv.cursor <= 0:
                return
            del self.vpriv.buffer[:self.vpriv.cursor]
            self.vpriv.cursor = 0

            self.internal.menu_hide
            self.vpriv.history_navigation_active = False
            await self.___redraw()

    async def end_del(self) -> None:
        async with self.vpriv.lock:
            if self.vpriv.cursor >= len(self.vpriv.buffer):
                return
            del self.vpriv.buffer[self.vpriv.cursor:]

            self.internal.menu_hide
            self.vpriv.history_navigation_active = False
            await self.___redraw()

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
            await ui.clear_screen_and_redraw(self)

    async def ctrlc_cancellation(self) -> str:
        async with self.vpriv.lock:
            self.internal.reset_state()
            await self.vpub.terminal.output.output_bytes(b"^C\r\n")
            return ""
        
    async def ctrld_exiting(self) -> Optional[str]:
        async with self.vpriv.lock:
            if not self.vpriv.buffer:
                return EOF
            return None