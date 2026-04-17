import asyncio
import time

from .text_utils import split_graphemes

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .objects import LineEditorPrivateVars, LineEditorPublicVars
    from .ui import LineEditorUI
    from helpers.lsp.incode_connector import InCodeLSPConnector


class LSPAdapter:
    def __init__(self, vpriv: LineEditorPrivateVars, vpub: LineEditorPublicVars, ui: LineEditorUI):
        self.connector: InCodeLSPConnector = None

        self._completion_task: asyncio.Task | None = None
        self._inline_task: asyncio.Task | None = None

        self._request_id = 0
        self._inline_request_id = 0

        self._debounce = 0.08
        self._last_tab = 0.0
        self._last_inline = 0.0

        self.vpriv = vpriv
        self.vpub = vpub
        self.ui = ui

    # ======================================================
    # BIND
    # ======================================================

    def set_engine(self, connector):
        self.connector = connector

    # ======================================================
    # CONTEXT
    # ======================================================
    @staticmethod
    def _context(buf, c):
        s = "".join(buf[:c])

        # найти последний пробел
        last_space = s.rfind(" ")

        if last_space == -1:
            # вводится команда
            tokens = []
            partial = s
            start = 0
        else:
            # есть команда + аргументы
            tokens = s[:last_space].split()
            partial = s[last_space + 1:]
            start = last_space + 1

        return start, partial, tokens

    # ======================================================
    # TAB COMPLETION
    # ======================================================

    async def tab_complete(self):
        if not self.connector:
            return

        if time.monotonic() - self._last_tab < self._debounce:
            return
        self._last_tab = time.monotonic()

        if self._completion_task and not self._completion_task.done():
            self._completion_task.cancel()

        self._request_id += 1
        req_id = self._request_id

        _, partial, tokens = self._context(self.vpriv.buffer, self.vpriv.cursor)

        async def worker():
            try:
                candidates = await self.connector.completion(partial, tokens)

                if req_id != self._request_id:
                    return

                if not candidates:
                    return
                
                #for test
                numered_candidates: list[str] = []
                for i, n in enumerate(candidates):
                    numered_candidates.append(f"{i} {n}")

                # 👉 берём АКТУАЛЬНОЕ состояние после await
                start2, partial2, _ = self._context(self.vpriv.buffer, self.vpriv.cursor)
                cursor2 = self.vpriv.cursor
                buf2 = self.vpriv.buffer

                # ==================================================
                # ❗ НЕЛЬЗЯ автодополнять если partial пустой
                # ==================================================
                if not partial2:
                    self.vpriv.completions = candidates
                    self.vpriv.awaiting_menu = True
                    return

                # ==================================================
                # ФИЛЬТРУЕМ кандидатов по partial
                # ==================================================
                matches = [c for c in candidates if c.startswith(partial2)]

                # ==================================================
                # SINGLE MATCH → REPLACE
                # ==================================================
                if len(matches) == 1:
                    full = matches[0]

                    # защита от лишней перезаписи
                    if full != partial2:
                        ins = split_graphemes(full)
                        buf2[start2:cursor2] = ins
                        self.vpriv.cursor = start2 + len(ins)
                        await self.ui.redraw()

                    return

                # ==================================================
                # MULTIPLE MATCHES → ТОЛЬКО МЕНЮ
                # ==================================================
                self.vpriv.completions = candidates
                self.vpriv.awaiting_menu = True

            except asyncio.CancelledError:
                pass

        self._completion_task = asyncio.create_task(worker())

    # ======================================================
    # INLINE HINT
    # ======================================================

    def schedule_inline_hint(self):
        if not self.connector:
            return

        if time.monotonic() - self._last_inline < self._debounce:
            return
        self._last_inline = time.monotonic()

        if self._inline_task and not self._inline_task.done():
            self._inline_task.cancel()

        self._inline_request_id += 1
        req_id = self._inline_request_id

        _, partial, tokens = self._context(self.vpriv.buffer, self.vpriv.cursor)

        async def worker():
            try:
                candidates = await self.connector.completion(partial, tokens)

                if req_id != self._inline_request_id:
                    return

                if len(candidates) == 1:
                    full = candidates[0]
                    if full.startswith(partial):
                        self.vpriv.inline_hint = full[len(partial):]
                    else:
                        self.vpriv.inline_hint = None
                else:
                    self.vpriv.inline_hint = None

                await self.ui.redraw()

            except asyncio.CancelledError:
                pass

        self._inline_task = asyncio.create_task(worker())

    # =======================================================
    # MENU ACCEPT
    # =======================================================
    async def menu_accept(self) -> None:
        if not self.connector:
            return

        # защита от пустого состояния
        if not self.vpriv.completions or self.vpriv.completion_index is None:
            return

        selected = self.vpriv.completions[self.vpriv.completion_index]

        start, partial, _ = self._context(self.vpriv.buffer, self.vpriv.cursor)

        buf = self.vpriv.buffer
        cursor = self.vpriv.cursor

        if start > cursor:
            start = cursor

        replacement = split_graphemes(selected)

        buf[start:cursor] = replacement
        self.vpriv.cursor = start + len(replacement)

        self.vpriv.completions = None
        self.vpriv.completion_index = 0
        self.vpriv.inline_hint = None
        self.vpriv.awaiting_menu = False
        self.vpriv.history_navigation_active = False

        await self.ui.redraw()
    # ======================================================
    # UTIL
    # ======================================================

    @staticmethod
    def _common_prefix(words):
        if not words:
            return ""
        p = words[0]
        for w in words[1:]:
            i = 0
            while i < len(p) and i < len(w) and p[i] == w[i]:
                i += 1
            p = p[:i]
        return p