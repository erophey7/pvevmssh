# sshserver/terminal/line_editor/lsp_adapter.py
import typing as t
import logging
import asyncio
import time

from .text_utils import char_class, split_graphemes
from . import ui

logger = logging.getLogger(__name__)

if t.TYPE_CHECKING:
    from .core import LineEditorCore as LineEditor


class LSPAdapter:
    def __init__(self):
        self.lsp_server = None

        # Level 2 state
        self._completion_task: asyncio.Task | None = None
        self._request_id = 0
        self._last_tab_time = 0.0

        # Inline hint (отдельный debounce + task)
        self._inline_task: asyncio.Task | None = None
        self._inline_request_id: int = 0
        self._last_inline_time: float = 0.0

        self._debounce_interval = 0.08  # 80ms

    def set_engine(self, engine):
        self.lsp_server = engine

    # ===================================================================
    # Общий helper (используется и Tab, и inline)
    # ===================================================================
    @staticmethod
    def _compute_completion_context(editor: "LineEditor") -> tuple[int, str, list[str]]:
        buf = editor._buffer
        c = editor._cursor
        start = c
        while start > 0 and char_class(buf[start - 1]) == "word":
            start -= 1

        partial = "".join(buf[start:c])

        # context tokens
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

        return start, partial, tokens

    # ===================================================================
    # TAB (полностью оригинальное поведение)
    # ===================================================================
    async def tab_complete(self, editor: "LineEditor") -> None:
        if not self.lsp_server:
            return

        if self._should_debounce_tab():
            return

        if self._completion_task and not self._completion_task.done():
            self._completion_task.cancel()

        self._request_id += 1
        request_id = self._request_id

        start, partial, tokens = self._compute_completion_context(editor)
        buf = editor._buffer
        c = editor._cursor

        editor._history_navigation_active = False

        async def worker():
            try:
                candidates = await self.lsp_server.get_completions(partial, tokens)

                if request_id != self._request_id:
                    return

                if not candidates:
                    return

                # SINGLE — оригинальное авто-вставление (не трогаем)
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
                inserted = False
                if common.startswith(partial) and len(common) > len(partial):
                    to_insert = common[len(partial):]
                    insert = split_graphemes(to_insert)
                    buf[c:c] = insert
                    editor._cursor += len(insert)
                    inserted = True
                    await ui.redraw(editor)

                if len(candidates) > 1:
                    editor._completions = candidates[:]
                    editor._completion_index = 0
                    editor._awaiting_menu = True
                    if not inserted:
                        await ui.redraw(editor)

                return

            except asyncio.CancelledError:
                return
            except Exception:
                import logging
                logging.exception("tab completion failed")

        self._completion_task = asyncio.create_task(worker())

    # ===================================================================
    # INLINE HINT (автоматически, без блокировки ввода)
    # ===================================================================
    def schedule_inline_hint(self, editor: "LineEditor") -> None:
        """Вызывается синхронно из feed_text под lock — мгновенно."""
        if not self.lsp_server:
            return

        if self._should_debounce_inline():
            return

        if self._inline_task and not self._inline_task.done():
            self._inline_task.cancel()

        self._inline_request_id += 1
        request_id = self._inline_request_id

        start, partial, tokens = self._compute_completion_context(editor)

        async def inline_worker():
            try:
                candidates = await self.lsp_server.get_completions(partial, tokens)

                if request_id != self._inline_request_id:
                    return

                if not candidates or len(candidates) != 1:
                    if editor._inline_hint is not None:
                        editor._inline_hint = None
                        await ui.redraw(editor)
                    return

                full = candidates[0]
                if full.startswith(partial) and len(full) > len(partial):
                    editor._inline_hint = full[len(partial):]
                else:
                    editor._inline_hint = None

                await ui.redraw(editor)

            except asyncio.CancelledError:
                return
            except Exception:
                import logging
                logging.exception("inline hint failed")

        self._inline_task = asyncio.create_task(inline_worker())

    def _should_debounce_tab(self) -> bool:
        now = time.monotonic()
        if now - self._last_tab_time < self._debounce_interval:
            return True
        self._last_tab_time = now
        return False

    def _should_debounce_inline(self) -> bool:
        now = time.monotonic()
        if now - self._last_inline_time < self._debounce_interval:
            return True
        self._last_inline_time = now
        return False

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