"""
Performing silent refactor
in testing
"""

from ._private import LineEditorLogic
from ._keyactions import LineEditorKeyactions

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from sshserver.session.history import CommandHistory
    from sshserver.terminal import Terminal
    from sshserver.session.syntax_highlight import StyleContext


class LineEditor:
    def __init__(self, terminal):
        self.bg = LineEditorLogic(terminal)
        self.vpriv = self.bg.get_priv_vars()
        self.vpub = self.bg.get_pub_vars()
        self.keys = LineEditorKeyactions(self.bg)

    async def reset(self) -> None:
        await self.bg.reset_state()

    async def on_terminal_resize(self) -> None:
        await self.bg.resize()

    async def feed_char(self, char: str) -> None:
        await self.bg.feed_text(char)

    async def feed_text(self, text: str) -> None:
        await self.bg.feed_text(text)

    async def on_keybind(self, event) -> None:
        if event.key.name == "TEXT":
            await self.feed_text(event.data)
            return

        handler = getattr(self.keys, f"key_{event.key.name.lower()}", None)

        # fallback для keys_ctrl_*
        if handler is None:
            handler = getattr(self.keys, f"keys_{event.key.name.lower()}", None)

        if handler:
            return await handler()

    async def quoted_insert(self) -> None:
        await self.bg.quoted_insert()

    def set_lsp_engine(self, engine) -> None:
        """Подключить LSP engine (вызывается снаружи, например из handle_client)."""
        if self.vpriv.lsp_adapter:
            self.vpriv.lsp_adapter.set_engine(engine)

    def set_style_context(self, style_ctx: StyleContext) -> None:
        """Подключить LSP engine (вызывается снаружи, например из handle_client)."""
        if self.vpub.style_ctx:
            self.vpub.style_ctx = style_ctx

    async def menu_hide(self) -> None:
        await self.bg.menu_hide()