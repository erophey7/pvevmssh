import typing as t
import asyncio
import time

from .text_utils import split_graphemes
from . import ui


class LSPAdapter:
    def __init__(self):
        self.connector = None

        self._completion_task: asyncio.Task | None = None
        self._inline_task: asyncio.Task | None = None

        self._request_id = 0
        self._inline_request_id = 0

        self._debounce = 0.08
        self._last_tab = 0.0
        self._last_inline = 0.0

    # ======================================================
    # BIND
    # ======================================================

    def set_engine(self, connector):
        self.connector = connector

    # ======================================================
    # CONTEXT
    # ======================================================

    def _context(self, editor):
        buf = editor._buffer
        c = editor._cursor

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

    async def tab_complete(self, editor):
        if not self.connector:
            return

        if time.monotonic() - self._last_tab < self._debounce:
            return
        self._last_tab = time.monotonic()

        if self._completion_task and not self._completion_task.done():
            self._completion_task.cancel()

        self._request_id += 1
        req_id = self._request_id

        start, partial, tokens = self._context(editor)
        buf = editor._buffer
        cursor = editor._cursor

        async def worker():
            try:
                candidates = await self.connector.completion(partial, tokens)

                if req_id != self._request_id:
                    return

                if not candidates:
                    return

                # 👉 берём АКТУАЛЬНОЕ состояние после await
                start2, partial2, _ = self._context(editor)
                cursor2 = editor._cursor
                buf2 = editor._buffer

                # ==================================================
                # ❗ НЕЛЬЗЯ автодополнять если partial пустой
                # ==================================================
                if not partial2:
                    editor._completions = candidates
                    editor._awaiting_menu = True
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
                        editor._cursor = start2 + len(ins)
                        await ui.redraw(editor)

                    return

                # ==================================================
                # MULTIPLE MATCHES → ТОЛЬКО МЕНЮ
                # ==================================================
                editor._completions = candidates
                editor._awaiting_menu = True

            except asyncio.CancelledError:
                pass

        self._completion_task = asyncio.create_task(worker())

    # ======================================================
    # INLINE HINT
    # ======================================================

    def schedule_inline_hint(self, editor):
        if not self.connector:
            return

        if time.monotonic() - self._last_inline < self._debounce:
            return
        self._last_inline = time.monotonic()

        if self._inline_task and not self._inline_task.done():
            self._inline_task.cancel()

        self._inline_request_id += 1
        req_id = self._inline_request_id

        start, partial, tokens = self._context(editor)

        async def worker():
            try:
                candidates = await self.connector.completion(partial, tokens)

                if req_id != self._inline_request_id:
                    return

                if len(candidates) == 1:
                    full = candidates[0]
                    if full.startswith(partial):
                        editor._inline_hint = full[len(partial):]
                    else:
                        editor._inline_hint = None
                else:
                    editor._inline_hint = None

                await ui.redraw(editor)

            except asyncio.CancelledError:
                pass

        self._inline_task = asyncio.create_task(worker())

    # =======================================================
    # MENU ACCEPT
    # =======================================================
    async def menu_accept(self, editor) -> None:
        if not self.connector:
            return

        # защита от пустого состояния
        if not editor._completions or editor._completion_index is None:
            return

        selected = editor._completions[editor._completion_index]

        start, partial, _ = self._context(editor)

        buf = editor._buffer
        cursor = editor._cursor

        if start > cursor:
            start = cursor

        replacement = split_graphemes(selected)

        buf[start:cursor] = replacement
        editor._cursor = start + len(replacement)

        editor._completions = None
        editor._completion_index = None
        editor._inline_hint = None
        editor._awaiting_menu = False
        editor._history_navigation_active = False

        await ui.redraw(editor)
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