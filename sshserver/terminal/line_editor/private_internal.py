from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .objects import LineEditorPrivateVars, LineEditorPublicVars

import logging

logger = logging.getLogger(__name__)

class LineEditorPrivateInternal:
    def __init__(self, vpriv: LineEditorPrivateVars, vpub: LineEditorPublicVars):
        self.vpriv: LineEditorPrivateVars = vpriv
        self.vpub: LineEditorPublicVars = vpub

    def reset_state(self) -> None:
        self.vpriv.buffer.clear()
        self.menu_hide()
        self.vpriv.cursor = 0
        self.vpriv.prompt_segments = None
        self.vpriv.last_layout = None
        self.vpriv.history_draft = None
        self.vpriv.history_navigation_active = False
        self.vpriv.quoted_insert = False
        self.vpriv.completions = None
        self.vpriv.completion_index = 0
        self.vpriv.awaiting_menu = False
        self.vpriv.inline_hint = None
        self.vpriv.lsp_generation = 0
        self.vpub.history.reset_index()

    def menu_hide(self) -> None:
        """Hiding completion menu, without redraw"""
        self.vpriv.completions = None
        self.vpriv.inline_hint = None
        self.vpriv.awaiting_menu = False
