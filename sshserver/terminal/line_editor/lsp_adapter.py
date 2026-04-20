import asyncio
import time
from collections import OrderedDict

import logging
logger = logging.getLogger(__name__)

from .text_utils import split_graphemes

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .objects import LineEditorPrivateVars, LineEditorPublicVars
    from .ui import LineEditorUI
    from helpers.lsp.incode_connector import InCodeLSPConnector
    from .types import SyntaxToken


# ======================================================
# LSP REQUEST MANAGER
# ======================================================

class LSPRequestManager:
    def __init__(self, connector: InCodeLSPConnector, max_cache: int = 32, ttl: float = 5.0):
        self.connector = connector

        self._task: asyncio.Task | None = None
        self._key = None

        self._lock = asyncio.Lock()

        # cache: key -> (timestamp, result)
        self._cache = OrderedDict()
        self._max_cache = max_cache
        self._ttl = ttl

    # -------------------------
    # CACHE HELPERS
    # -------------------------

    def clear_cache(self):
        self._cache.clear()
        self._task = None
        self._key = None

    def _make_key(self, buffer, cursor, partial):
        return (tuple(buffer), cursor, partial)

    def _get_cached(self, key):
        now = time.monotonic()

        item = self._cache.get(key)
        if not item:
            return None

        ts, value = item

        if now - ts > self._ttl:
            del self._cache[key]
            return None

        self._cache.move_to_end(key)
        return value

    def _store_cache(self, key, value):
        self._cache[key] = (time.monotonic(), value)
        self._cache.move_to_end(key)

        if len(self._cache) > self._max_cache:
            self._cache.popitem(last=False)

    def _prefix_match(self, partial):
        for (buf, cur, old_partial), (ts, result) in reversed(self._cache.items()):
            if result and partial.startswith(old_partial):
                return [c for c in result if c.startswith(partial)]
        return None

    # -------------------------
    # MAIN REQUEST
    # -------------------------

    async def request(self, buffer, cursor, partial, tokens, wait=False):
        key = self._make_key(buffer, cursor, partial)

        if partial == "":
            self.clear_cache()

        # 1. exact cache
        cached = self._get_cached(key)
        if cached is not None:
            return cached

        # 2. prefix reuse
        reused = self._prefix_match(partial)
        if reused:
            return reused

        # 3. in-flight reuse
        if self._task and not self._task.done() and self._key == key:
            return await self._task

        async with self._lock:
            if self._task and not self._task.done() and self._key == key:
                return await self._task

            async def worker():
                res = await self.connector.completion(partial, tokens)
                self._store_cache(key, res)
                return res

            self._key = key
            self._task = asyncio.create_task(worker())

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
        self._last_semantic = 0.0

        self._semantic_cache: dict[tuple[str, ...], list[SyntaxToken]] = {}

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
    # SEMANTIC TOKENS (AST HIGHLIGHT)
    # ======================================================
    def schedule_semantic_highlight(self):
        if not self.connector:
            return

        gen = self.vpriv.lsp_generation
        buffer_key = tuple(self.vpriv.buffer)

        if buffer_key in self._semantic_cache:
            self.vpriv.semantic_styles = self._semantic_cache[buffer_key]
            asyncio.create_task(self.ui.redraw())
            return

        now = time.monotonic()
        if now - self._last_semantic < self._debounce:
            return
        self._last_semantic = now

        async def worker():
            try:
                result = await self.connector.semantic_tokens("".join(self.vpriv.buffer))
                if gen != self.vpriv.lsp_generation:
                    return

                tokens = result.get("tokens") or []
                if not isinstance(tokens, list):
                    tokens = []

                self._semantic_cache[buffer_key] = tokens
                if len(self._semantic_cache) > 32:
                    self._semantic_cache.pop(next(iter(self._semantic_cache)))

                self.vpriv.semantic_tokens = tokens  

            except Exception:
                self.vpriv.semantic_tokens = None

            if gen == self.vpriv.lsp_generation:
                await self.ui.redraw()

        asyncio.create_task(worker())

    # ======================================================
    # TAB COMPLETION
    # ======================================================

    async def tab_complete(self):
        if not self.lsp:
            return

        if time.monotonic() - self._last_tab < self._debounce:
            return
        self._last_tab = time.monotonic()

        start, partial, tokens = self._context(self.vpriv.buffer, self.vpriv.cursor)

        candidates = await self.lsp.request(
            self.vpriv.buffer,
            self.vpriv.cursor,
            partial,
            tokens,
            wait=True
        )

        if not candidates:
            return

        if partial == "":
            self.vpriv.completions = candidates
            self.vpriv.awaiting_menu = True
            return

        matches = [c for c in candidates if c.startswith(partial)]

        if len(matches) == 1:
            full = matches[0]

            if full != partial:
                ins = split_graphemes(full)
                self.vpriv.buffer[start:self.vpriv.cursor] = ins
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

            if len(candidates) == 1 and candidates[0].startswith(partial):
                hint = candidates[0][len(partial):]
            else:
                hint = None

            if gen != self.vpriv.lsp_generation:
                return

            self.vpriv.inline_hint = hint
            await self.ui.redraw()

        asyncio.create_task(worker())

    # ======================================================
    # MENU ACCEPT
    # ======================================================

    async def menu_accept(self):
        if not self.vpriv.completions or self.vpriv.completion_index is None:
            return

        selected = self.vpriv.completions[self.vpriv.completion_index]

        start, _, _ = self._context(self.vpriv.buffer, self.vpriv.cursor)

        self.vpriv.buffer[start:self.vpriv.cursor] = split_graphemes(selected)
        self.vpriv.cursor = start + len(split_graphemes(selected))

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