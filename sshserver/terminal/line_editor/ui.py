from .layout import build_layout
from sshserver.session.prompt import get_prompt_segments

import logging
logger = logging.getLogger(__name__)

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .objects import LineEditorPrivateVars, LineEditorPublicVars
    from sshserver.session.types import PromptSegment


class LineEditorUI:
    def __init__(self, vpriv: LineEditorPrivateVars, vpub: LineEditorPublicVars):
        self.vpriv = vpriv
        self.vpub = vpub

    def cache_prompt_segments(self) -> list[PromptSegment]:
        if self.vpriv.prompt_segments is None:
            self.vpriv.prompt_segments = get_prompt_segments(self.vpub.terminal.session)
        return self.vpriv.prompt_segments

    async def redraw(self) -> None:
        layout = build_layout(
            prompt_segments=self.cache_prompt_segments(),
            buffer=self.vpriv.buffer,
            cursor=self.vpriv.cursor,
            term_width=self.vpub.terminal.session.term_width,
            term_height=self.vpub.terminal.session.term_height,
            completions=self.vpriv.completions,
            completion_index=self.vpriv.completion_index,
            inline_hint=self.vpriv.inline_hint,
            style_ctx=self.vpub.style_ctx,
            semantic_tokens=self.vpriv.semantic_tokens,
        )

        logger.debug(f"Layout: {layout}")

        out = b""

        if self.vpriv.last_layout is not None and self.vpriv.last_layout.cursor_pos.row > 0:
            out += f"\x1b[{self.vpriv.last_layout.cursor_pos.row}A".encode()

        out += b"\r\x1b[J"
        out += layout.rendered_ansi.encode("utf-8", errors="replace")

        if layout.pending_wrap:
            out += b"\r\n"

        if layout.menu_ansi:
            out += b"\r\n"
            lines = layout.menu_ansi.split("\r\n")
            for i, line in enumerate(lines):
                if layout.menu_start_col > 1:
                    out += f"\x1b[{layout.menu_start_col}G".encode()
                out += line.encode("utf-8", errors="replace")
                if i < len(lines) - 1:
                    out += b"\r\n"

        _, menu_height = layout.menu_grid 

        extra = menu_height if layout.menu_ansi else 0
        rows_up = layout.end_pos.row - layout.cursor_pos.row + extra

        if rows_up > 0:
            out += f"\x1b[{rows_up}A".encode()

        out += f"\x1b[{layout.cursor_pos.col}G".encode()

        self.vpriv.last_layout = layout

        if self.vpub.echo:
            await self.vpub.terminal.output.output_bytes(out)

    async def move_cursor_only_or_redraw(self) -> None:
        if self.vpriv.last_layout is None:
            await self.redraw()
            return

        new_layout = build_layout(
            prompt_segments=self.cache_prompt_segments(),
            buffer=self.vpriv.buffer,
            cursor=self.vpriv.cursor,
            term_width=self.vpub.terminal.session.term_width,
            term_height=self.vpub.terminal.session.term_height,
            completions=self.vpriv.completions,
            completion_index=self.vpriv.completion_index,
            inline_hint=self.vpriv.inline_hint,
            style_ctx=self.vpub.style_ctx,
            semantic_tokens=self.vpriv.semantic_tokens,
        )

        if (
            new_layout.rendered_ansi != self.vpriv.last_layout.rendered_ansi
            or new_layout.pending_wrap != self.vpriv.last_layout.pending_wrap
            or len(new_layout.rows) != len(self.vpriv.last_layout.rows)
            or new_layout.menu_ansi != self.vpriv.last_layout.menu_ansi
        ):
            await self.redraw()
            return

        out = b""
        old = self.vpriv.last_layout.cursor_pos
        new = new_layout.cursor_pos

        row_delta = old.row - new.row
        if row_delta > 0:
            out += f"\x1b[{row_delta}A".encode()
        elif row_delta < 0:
            out += f"\x1b[{-row_delta}B".encode()

        out += f"\x1b[{new.col}G".encode()

        self.vpriv.last_layout = new_layout

        if self.vpub.echo and out:
            await self.vpub.terminal.output.output_bytes(out)


    async def clear_screen_and_redraw(self) -> None:
        if self.vpub.echo:
            await self.vpub.terminal.output.output_bytes(b"\x1b[2J\x1b[H]")
        self.vpriv.last_layout = None
        await self.redraw()