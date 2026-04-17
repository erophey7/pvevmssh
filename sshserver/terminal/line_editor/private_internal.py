from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .objects import LineEditorPrivateVars, LineEditorPublicVars

class LineEditorPrivateInternal:
    def __init__(self, vpriv: LineEditorPrivateVars, vpub: LineEditorPublicVars):
        self.vpriv: LineEditorPrivateVars = vpriv
        self.vpub: LineEditorPublicVars = vpub

    def reset_state(self) -> None:
        self.vpriv.buffer.clear()
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
        self.vpub.history.reset_index()

    def menu_hide(self) -> None:
        """Hiding completion menu, without redraw"""
        self.vpriv.completions = None
        self.vpriv.inline_hint = None
        self.vpriv.awaiting_menu = False

    def get_menu_columns(self) -> int:
        """Пропорциональное количество колонок.
        Теперь полностью совпадает с логикой layout.py (+3 и menu_start_col=1)."""
        if not self.vpriv.completions or len(self.vpriv.completions) <= 1:
            return 1

        term_width = getattr(self.vpub.terminal.session, "term_width", 80)
        max_len = max(len(c) for c in self.vpriv.completions) + 3 

        # меню всегда прижато к левому краю (col=1)
        available_width = term_width
        return max(1, available_width // max_len)