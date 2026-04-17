
from .types import Layout, VisualCell, ScreenPos
from .text_utils import split_graphemes, char_width, get_style, highlight_buffer
from sshserver.session.syntax_highlight import (
    StyleConfig,
    StyleContext
)

import asyncio

class LineEditorLayoutPIPELINE:
    def __init__(self):
        self._rows: list[list[VisualCell]] = None
        self._index_to_pos: list[ScreenPos] = None 
        self._cursor_pos: ScreenPos = None
        self._end_pos: ScreenPos = None
        self._rendered_ansi: str = ""
        self._pending_wrap: bool = False
        self._menu_ansi: str = ""
        self._menu_height: int = 0
        self._menu_start_col: int = 1

        self._lock = asyncio.Lock()

    async def get_layout(self) -> Layout:
        layout = Layout(
            rows=self._rows,
            index_to_pos=self._index_to_pos,
            cursor_pos=self._cursor_pos,
            end_pos=self._end_pos,
            rendered_ansi=self._rendered_ansi,
            pending_wrap=self._pending_wrap,
            menu_ansi=self._menu_ansi,
            menu_height=self._menu_height,
            menu_start_col=self._menu_start_col
        )
        return layout
    
    async def build_layout(
            self,
            prompt_segments,
            buffer: list[str],
            cursor: int,
            term_width: int,
            term_height: int,
            completions: list[str] | None = None,
            completion_index: int | None = None,
            inline_hint: str | None = None,
            style_ctx: StyleContext = None,
        ):
        pass