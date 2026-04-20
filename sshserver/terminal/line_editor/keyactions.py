from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .private import LineEditorLogic
    from .objects import LineEditorPrivateVars, LineEditorPublicVars
    from typing import Optional

class LineEditorKeyactions:
    def __init__(self, bg_logic: LineEditorLogic):
        self.bg: LineEditorLogic = bg_logic
        self.vpriv: LineEditorPrivateVars = self.bg.get_priv_vars()
        self.vpub: LineEditorPublicVars = self.bg.get_pub_vars()

    # =============================================
    # DEFAULT KEYMAP
    # =============================================
    def build_default_keymap(self):
        """
        Возвращает dict[Key, callable]
        callable принимает KeyEvent
        """

        async def wrap(fn):
            async def inner(_event=None):
                return await fn()
            return inner

        return {
            # arrows
            "UP": self.key_up,
            "DOWN": self.key_down,
            "LEFT": self.key_left,
            "RIGHT": self.key_right,

            # ctrl arrows
            "CTRL_UP": self.keys_ctrl_up,
            "CTRL_DOWN": self.keys_ctrl_down,
            "CTRL_LEFT": self.keys_ctrl_left,
            "CTRL_RIGHT": self.keys_ctrl_right,

            # home/end
            "HOME": self.key_home,
            "END": self.key_end,

            # deletes
            "BACKSPACE": self.key_backspace,
            "CTRL_BACKSPACE": self.keys_ctrl_backspace,
            "DEL": self.key_delete,
            "CTRL_DEL": self.keys_ctrl_delete,
            "CTRL_U": self.keys_ctrl_u,
            "CTRL_K": self.keys_ctrl_k,

            # other
            "ENTER": self.key_enter,
            "TAB": self.key_tab,
            "ESC": self.key_esc,
            "CTRL_L": self.keys_ctrl_l,
            "CTRL_C": self.keys_ctrl_c,
            "CTRL_D": self.keys_ctrl_d,
            "CTRL_R": self.keys_ctrl_r,
        }
            
    # =============================================
    # ARROWS
    # =============================================

    async def key_up(self) -> None:
        if self.vpriv.completions:
            await self.bg.menu_up()
        else:
            await self.bg.history_up()

    async def key_down(self) -> None:
        if self.vpriv.completions:
            await self.bg.menu_down()
        else:
            await self.bg.history_down()

    async def key_left(self) -> None:
        if self.vpriv.completions:
            await self.bg.menu_prev()
        else:
            await self.bg.cursor_left()

    async def key_right(self) -> None:
        if self.vpriv.completions:
            await self.bg.menu_next()
        elif self.vpriv.inline_hint and self.vpriv.cursor == len(self.vpriv.buffer):
            await self.bg.accept_inline_hint()
        else:
            await self.bg.cursor_right()

    # =============================================
    # CTRL ARROWS
    # =============================================
    async def keys_ctrl_up(self) -> None:
        pass

    async def keys_ctrl_down(self) -> None:
        pass

    async def keys_ctrl_left(self) -> None:
        await self.bg.cursor_word_left()

    async def keys_ctrl_right(self) -> None:
        await self.bg.cursor_word_right()

    # =============================================
    # HOME END
    # =============================================

    async def key_home(self) -> None:
        await self.bg.cursor_home()

    async def key_end(self) -> None:
        await self.bg.cursor_end()

    # =============================================
    # ALL DELETES
    # =============================================
    async def key_backspace(self) -> None:
        await self.bg.char_left_del()

    async def keys_ctrl_backspace(self) -> None:
        await self.bg.word_left_del()

    async def key_delete(self) -> None:
        await self.bg.char_right_del()

    async def keys_ctrl_delete(self) -> None:
        await self.bg.word_right_del()

    async def keys_ctrl_u(self) -> None:
        await self.bg.home_del()

    async def keys_ctrl_k(self) -> None:
        await self.bg.end_del()

    # =============================================
    # OTHER
    # =============================================
    async def key_enter(self) -> str:
        if self.vpriv.completions is not None:
            await self.bg.menu_accept()
        else:
            return await self.bg.enter()

    async def key_tab(self) -> None:
        if self.vpriv.completions:
            await self.bg.menu_next()
        elif self.vpriv.inline_hint and self.vpriv.cursor == len(self.vpriv.buffer):
            await self.bg.accept_inline_hint()
        else:
            await self.bg.tab_complete()
            await self.bg.menu_request()

    async def key_esc(self) -> None:
        if self.vpriv.completions:
            await self.bg.menu_hide()

    async def keys_ctrl_l(self) -> None:
        await self.bg.clear_screen()

    async def keys_ctrl_r(self) -> None:
        pass

    async def keys_ctrl_c(self) -> str:
        return await self.bg.ctrlc_cancellation()

    async def keys_ctrl_d(self) -> Optional[str]:
        return await self.bg.ctrld_exiting()