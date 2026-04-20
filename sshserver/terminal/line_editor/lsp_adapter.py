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
        # params
        self.connector = connector
        self._max_cache = max_cache
        self._ttl = ttl

        # complete state
        self._complete_lock = asyncio.Lock()
        self._complete_task: asyncio.Task | None = None
        self._complete_key = None
        self._complete_cache = OrderedDict()

        # semantic state
        self._semantic_lock = asyncio.Lock()
        self._semantic_task: asyncio.Task | None = None
        self._semantic_key = None
        self._semantic_cache = OrderedDict()

    # -------------------------
    # COMPLETE CACHE HELPERS
    # -------------------------
    def clear_complete_cache(self):
        self._complete_cache.clear()
        self._complete_task = None
        self._complete_key = None

    def _make_complete_key(self, buffer, cursor, partial):
        return (tuple(buffer), cursor, partial)

    def _get_complete_cached(self, key):
        now = time.monotonic()

        item = self._complete_cache.get(key)
        if not item:
            return None

        ts, value = item

        if now - ts > self._ttl:
            del self._complete_cache[key]
            return None

        self._complete_cache.move_to_end(key)
        return value

    def _store_complete_cache(self, key, value):
        self._complete_cache[key] = (time.monotonic(), value)
        self._complete_cache.move_to_end(key)

        if len(self._complete_cache) > self._max_cache:
            self._complete_cache.popitem(last=False)

    def _prefix_match(self, partial):
        for (buf, cur, old_partial), (ts, result) in reversed(self._complete_cache.items()):
            if result and partial.startswith(old_partial):
                return [c for c in result if c.startswith(partial)]
        return None
    
    # -------------------------
    # SEMANTIC CACHE HELPERS
    # -------------------------
    def clear_semantic_cache(self):
        self._semantic_cache.clear()
        self._semantic_task = None
        self._semantic_key = None

    def _make_semantic_key(self, buffer):
        return "".join(buffer)


    def _get_semantic_cached(self, key):
        now = time.monotonic()

        item = self._semantic_cache.get(key)
        if not item:
            return None

        ts, value = item

        if now - ts > self._ttl:
            del self._semantic_cache[key]
            return None

        self._semantic_cache.move_to_end(key)
        return value


    def _store_semantic_cache(self, key, value):
        self._semantic_cache[key] = (time.monotonic(), value)
        self._semantic_cache.move_to_end(key)

        if len(self._semantic_cache) > self._max_cache:
            self._semantic_cache.popitem(last=False)

    # -------------------------
    # COMPLETE REQUEST
    # -------------------------
    async def complete_request(self, buffer, cursor, partial, tokens, wait=False):
        key = self._make_complete_key(buffer, cursor, partial)

        if partial == "":
            self.clear_complete_cache()

        # 1. exact cache
        cached = self._get_complete_cached(key)
        if cached is not None:
            return cached

        # 2. prefix reuse
        reused = self._prefix_match(partial)
        if reused:
            return reused

        # 3. in-flight reuse
        if self._complete_task and not self._complete_task.done() and self._complete_key == key:
            return await self._complete_task

        async with self._complete_lock:
            if self._complete_task and not self._complete_task.done() and self._complete_key == key:
                return await self._complete_task

            async def worker():
                res = await self.connector.completion(partial, tokens)
                self._store_complete_cache(key, res)
                return res

            self._complete_key = key
            self._complete_task = asyncio.create_task(worker())

            return await self._complete_task
        
    # -------------------------
    # SEMANTIC REQUEST
    # -------------------------
    async def semantic_request(self, buffer, generation, wait=False):
        key = self._make_semantic_key(buffer)
    
        # 1. cache
        cached = self._get_semantic_cached(key)
        if cached is not None:
            return cached
    
        # 2. cancel previous task (другой key или устаревший)
        if self._semantic_task and not self._semantic_task.done():
            self._semantic_task.cancel()
    
        # 3. in-flight reuse (редкий случай)
        if (
            self._semantic_task
            and not self._semantic_task.done()
            and self._semantic_key == key
        ):
            return await self._semantic_task if wait else None
    
        async with self._semantic_lock:
            # повторная проверка
            if (
                self._semantic_task
                and not self._semantic_task.done()
                and self._semantic_key == key
            ):
                return await self._semantic_task if wait else None
    
            # отменяем внутри lock (на всякий случай)
            if self._semantic_task and not self._semantic_task.done():
                self._semantic_task.cancel()
    
            async def worker(gen, text):
                try:
                    res = await self.connector.semantic_tokens(text)
    
                    tokens = res.get("tokens") if isinstance(res, dict) else None
                    if not isinstance(tokens, list):
                        tokens = []
    
                    # ❗ защита от устаревшего результата
                    if gen != generation:
                        return None
    
                    self._store_semantic_cache(text, tokens)
                    return tokens
    
                except asyncio.CancelledError:
                    return None
                except Exception:
                    return None
    
            self._semantic_key = key
            self._semantic_task = asyncio.create_task(worker(generation, key))
    
            return await self._semantic_task if wait else None

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
    # SEMANTIC TOKENS (AST HIGHLIGHT)
    # ======================================================
    def schedule_semantic_highlight(self):
        if not self.lsp:
            return

        gen = self.vpriv.lsp_semantic_generation

        now = time.monotonic()
        if now - self._last_semantic < self._debounce:
            return
        self._last_semantic = now

        async def worker(local_gen):
            await self.lsp.semantic_request(
                self.vpriv.buffer,
                generation=local_gen
            )

            # ждём завершения задачи
            task = self.lsp._semantic_task
            if not task:
                return

            try:
                tokens = await task
            except asyncio.CancelledError:
                return

            if tokens is None:
                return

            # ❗ проверка актуальности
            if local_gen != self.vpriv.lsp_semantic_generation:
                return

            self.vpriv.semantic_tokens = tokens

            if local_gen == self.vpriv.lsp_semantic_generation:
                await self.ui.redraw()

        asyncio.create_task(worker(gen))

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

        candidates = await self.lsp.complete_request(
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

        gen = self.vpriv.lsp_complete_generation

        async def worker():
            start, partial, tokens = self._context(
                self.vpriv.buffer,
                self.vpriv.cursor
            )

            candidates = await self.lsp.complete_request(
                self.vpriv.buffer,
                self.vpriv.cursor,
                partial,
                tokens,
                wait=False
            )

            if gen != self.vpriv.lsp_complete_generation:
                return

            if len(candidates) == 1 and candidates[0].startswith(partial):
                hint = candidates[0][len(partial):]
            else:
                hint = None

            if gen != self.vpriv.lsp_complete_generation:
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