import asyncio
import time

from .text_utils import split_graphemes

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .objects import LineEditorPrivateVars, LineEditorPublicVars
    from .ui import LineEditorUI
    from helpers.lsp.incode_connector import InCodeLSPConnector


# ======================================================
# LSP REQUEST MANAGER
# ======================================================

class LSPRequestManager:
    def __init__(self, connector):
        self.connector = connector

        self._task: asyncio.Task | None = None
        self._key = None
        self._result = None

        self._lock = asyncio.Lock()

    def _make_key(self, buffer, cursor, partial):
        return (tuple(buffer), cursor, partial)

    async def request(self, buffer, cursor, partial, tokens, wait: bool = False):
        key = self._make_key(buffer, cursor, partial)

        # cached result
        if self._key == key and self._result is not None:
            return self._result

        # reuse in-flight task
        if self._task and not self._task.done() and self._key == key:
            return await self._task

        async with self._lock:
            if self._task and not self._task.done() and self._key == key:
                return await self._task

            async def worker():
                res = await self.connector.completion(partial, tokens)
                self._key = key
                self._result = res
                return res

            self._task = asyncio.create_task(worker())

            if wait:
                return await self._task

            return await self._task


# ======================================================
# ADAPTER
# ======================================================

class LSPAdapter:
    def __init__(self, vpriv: LineEditorPrivateVars, vpub: LineEditorPublicVars, ui: LineEditorUI):
        self.connector: InCodeLSPConnector = None

        self.lsp: LSPRequestManager | None = None

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
        self.lsp = LSPRequestManager(connector)

    # ======================================================
    # CONTEXT
    # ======================================================

    @staticmethod
    def _context(buf, c):
        s = "".join(buf[:c])

        last_space = s.rfind(" ")

        if last_space == -1:
            tokens = []
            partial = s
            start = 0
        else:
            tokens = s[:last_space].split()
            partial = s[last_space + 1:]
            start = last_space + 1

        return start, partial, tokens

    # ======================================================
    # TAB COMPLETION
    # ======================================================

    async def tab_complete(self):
        if not self.lsp:
            return

        if time.monotonic() - self._last_tab < self._debounce:
            return
        self._last_tab = time.monotonic()

        _, partial, tokens = self._context(self.vpriv.buffer, self.vpriv.cursor)

        start, _, _ = self._context(self.vpriv.buffer, self.vpriv.cursor)

        buf = self.vpriv.buffer
        cursor = self.vpriv.cursor

        candidates = await self.lsp.request(
            buf,
            cursor,
            partial,
            tokens,
            wait=True
        )

        if not candidates:
            return

        # empty partial → show menu only
        if partial == "":
            self.vpriv.completions = candidates
            self.vpriv.awaiting_menu = True
            return

        matches = [c for c in candidates if c.startswith(partial)]

        if len(matches) == 1:
            full = matches[0]

            if full != partial:
                ins = split_graphemes(full)
                buf[start:cursor] = ins
                self.vpriv.cursor = start + len(ins)
                await self.ui.redraw()
            return

        self.vpriv.completions = candidates
        self.vpriv.awaiting_menu = True

    # ======================================================
    # INLINE HINT
    # ======================================================

    def schedule_inline_hint(self):
        if not self.lsp:
            return

        gen = self.vpriv.lsp_generation

        async def worker():
            start, partial, tokens = self._context(
                self.vpriv.buffer,
                self.vpriv.cursor
            )

            candidates = await self.lsp.request(
                self.vpriv.buffer,
                self.vpriv.cursor,
                partial,
                tokens,
                wait=False
            )

            if gen != self.vpriv.lsp_generation:
                return

            if len(candidates) == 1:
                full = candidates[0]
                if full.startswith(partial):
                    hint = full[len(partial):]
                else:
                    hint = None
            else:
                hint = None

            # ещё один stale guard перед UI
            if gen != self.vpriv.lsp_generation:
                return

            self.vpriv.inline_hint = hint
            await self.ui.redraw()

        asyncio.create_task(worker())

    # ======================================================
    # MENU ACCEPT
    # ======================================================

    async def menu_accept(self) -> None:
        if not self.vpriv.completions or self.vpriv.completion_index is None:
            return

        selected = self.vpriv.completions[self.vpriv.completion_index]

        start, _, _ = self._context(self.vpriv.buffer, self.vpriv.cursor)

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