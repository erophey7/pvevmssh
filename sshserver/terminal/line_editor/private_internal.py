from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .objects import LineEditorPrivateVars, LineEditorPublicVars
    from .private import LineEditorLogic

import re
import logging

logger = logging.getLogger(__name__)

class LineEditorPrivateInternal:
    def __init__(self, vpriv: LineEditorPrivateVars, vpub: LineEditorPublicVars, parent: LineEditorLogic):
        self.vpriv: LineEditorPrivateVars = vpriv
        self.vpub: LineEditorPublicVars = vpub
        self.parent: LineEditorLogic = parent

    async def reset_state(self) -> None:
        self.vpriv.buffer.clear()
        self.menu_hide()
        self.vpriv.cursor = 0
        self.vpriv.prompt_segments = None
        self.parent.ui.clear_cache()
        self.vpriv.history_draft = None
        self.vpriv.history_navigation_active = False
        self.vpriv.quoted_insert = False
        self.vpriv.completions = None
        self.vpriv.completion_index = 0
        self.vpriv.awaiting_menu = False
        self.vpriv.inline_hint = None
        self.vpriv.lsp_complete_generation = 0
        self.vpriv.lsp_semantic_generation = 0
        self.vpriv.semantic_tokens = None
        self.parent.lsp_adapter.lsp.clear_complete_cache()
        self.parent.lsp_adapter.lsp.clear_semantic_cache()
        self.vpub.history.reset_index()

    def menu_hide(self) -> None:
        """Hiding completion menu, without redraw"""
        self.vpriv.completions = None
        self.vpriv.inline_hint = None
        self.vpriv.awaiting_menu = False