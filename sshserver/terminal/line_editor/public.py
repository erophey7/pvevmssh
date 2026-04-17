from .private import LineEditorLogic
from .keyactions import LineEditorKeyactions

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from sshserver.session.syntax_highlight import StyleContext
    from sshserver.terminal.types import KeyEvent


class LineEditor:
    def __init__(self, terminal):
        self.bg = LineEditorLogic(terminal)
        self.keys = LineEditorKeyactions(self.bg)
        self.vpriv = self.bg.get_priv_vars()
        self.vpub = self.bg.get_pub_vars()

    async def reset(self) -> None:
        await self.bg.reset_state()

    async def on_terminal_resize(self) -> None:
        await self.bg.resize()

    async def feed_char(self, char: str) -> None:
        await self.bg.feed_text(char)

    async def feed_text(self, text: str) -> None:
        await self.bg.feed_text(text)

    async def on_keybind(self, event: KeyEvent) -> None:
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
        self.bg.get_lsp_adapter().set_engine(engine)

    def set_style_context(self, style_ctx: StyleContext) -> None:
        """Подключить StyleContext engine (вызывается снаружи, например из handle_client)."""
        if hasattr(self.vpub, "style_ctx"):
            self.vpub.style_ctx = style_ctx

    async def menu_hide(self) -> None:
        await self.bg.menu_hide()