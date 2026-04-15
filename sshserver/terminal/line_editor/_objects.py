"""
Performing silent refactor
in testing
"""

from .lsp_adapter import LSPAdapter
from asyncio import Lock
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sshserver.session.history import CommandHistory
    from sshserver.terminal import Terminal
    from sshserver.session.syntax_highlight import StyleContext

class LineEditorPublicVars:
    def __init__(self, terminal):
        self.history: CommandHistory = None
        self.echo: bool = True
        self.terminal: Terminal = terminal
        self.style_ctx: StyleContext = None

class LineEditorPrivateVars:
    def __init__(self):
        self.buffer: list[str] = []
        self.cursor: int = 0
        self.prompt_segments: list | None = None

        self.last_layout = None

        self.history_draft: list[str] | None = None
        self.history_navigation_active: bool = False

        self.lock = Lock()

        self.quoted_insert: bool = False

        self.lsp_adapter = LSPAdapter()

        self.completions: list[str] | None = None
        self.completion_index: int = 0
        self.awaiting_menu: bool = False

        self.inline_hint: str | None = None