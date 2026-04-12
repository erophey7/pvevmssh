# sshserver/terminal/line_editor/lsp_adapter.py
import typing as t
import logging
import asyncio
import time

from .text_utils import char_class, split_graphemes
from . import ui

logger = logging.getLogger(__name__)


class LSPAdapter:
    def __init__(self):
        self.lsp_server = None

        # Level 2 state
        self._completion_task: asyncio.Task | None = None
        self._request_id = 0
        self._last_tab_time = 0.0
        self._debounce_interval = 0.08  # 80ms

    def set_engine(self, engine):
        self.lsp_server = engine

    async def tab_complete(self, editor: "LineEditor") -> None: # type: ignore
        import asyncio

        if not self.lsp_server:
            return

        # -------------------------------------------------
        # debounce
        # -------------------------------------------------
        if self._should_debounce():
            return

        # -------------------------------------------------
        # cancel previous task
        # -------------------------------------------------
        if self._completion_task and not self._completion_task.done():
            self._completion_task.cancel()

        self._request_id += 1
        request_id = self._request_id

        buf = editor._buffer
        c = editor._cursor

        # -------------------------------------------------
        # find word start
        # -------------------------------------------------
        start = c
        while start > 0 and char_class(buf[start - 1]) == "word":
            start -= 1

        partial = "".join(buf[start:c])

        # -------------------------------------------------
        # context tokens
        # -------------------------------------------------
        prev = buf[:start]
        tokens = []
        current = []

        for g in prev:
            if char_class(g) == "word":
                current.append(g)
            elif current:
                tokens.append("".join(current))
                current = []

        if current:
            tokens.append("".join(current))

        editor._history_navigation_active = False

        # -------------------------------------------------
        # async worker
        # -------------------------------------------------
        async def worker():
            try:
                candidates = await self.lsp_server.get_completions(
                    partial,
                    tokens
                )

                # -------------------------------------------------
                # race condition guard
                # -------------------------------------------------
                if request_id != self._request_id:
                    return

                if not candidates:
                    return

                # SINGLE
                if len(candidates) == 1:
                    full = candidates[0]

                    del buf[start:c]
                    insert = split_graphemes(full)

                    buf[start:start] = insert
                    editor._cursor = start + len(insert)

                    await ui.redraw(editor)
                    return

                # MULTI
                common = self._common_prefix(candidates)

                if common.startswith(partial) and len(common) > len(partial):
                    to_insert = common[len(partial):]
                    insert = split_graphemes(to_insert)

                    buf[c:c] = insert
                    editor._cursor += len(insert)

                    await ui.redraw(editor)

            except asyncio.CancelledError:
                return
            except Exception:
                import logging
                logging.exception("tab completion failed")

        # -------------------------------------------------
        # schedule
        # -------------------------------------------------
        self._completion_task = asyncio.create_task(worker())

    @staticmethod
    def _common_prefix(words: list[str]) -> str:
        if not words:
            return ""

        prefix = words[0]

        for w in words[1:]:
            i = 0
            while i < len(prefix) and i < len(w) and prefix[i] == w[i]:
                i += 1
            prefix = prefix[:i]

            if not prefix:
                break

        return prefix
    
    def _should_debounce(self) -> bool:
        now = time.monotonic()
        if now - self._last_tab_time < self._debounce_interval:
            return True

        self._last_tab_time = now
        return False