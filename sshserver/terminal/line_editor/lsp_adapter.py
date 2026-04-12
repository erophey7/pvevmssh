# sshserver/terminal/line_editor/lsp_adapter.py
import typing as t
import logging

from .text_utils import char_class, split_graphemes
from . import ui

logger = logging.getLogger(__name__)


class LSPAdapter:
    def __init__(self):
        self.lsp_server = None

    def set_engine(self, engine):
        self.lsp_server = engine

    async def tab_complete(self, editor: "LineEditor") -> None: # type: ignore
        buf = editor._buffer
        c = editor._cursor

        logger.debug(f"tab: buffer={buf} cursor={c}")

        # find word start
        start = c
        while start > 0 and char_class(buf[start - 1]) == "word":
            start -= 1

        partial = "".join(buf[start:c])

        # tokenize context
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

        if not self.lsp_server:
            return

        candidates = await self.lsp_server.get_completions(partial, tokens)
        if not candidates:
            return

        editor._history_navigation_active = False

        # single result
        if len(candidates) == 1:
            full = candidates[0]
            del buf[start:c]

            insert = split_graphemes(full)
            buf[start:start] = insert
            editor._cursor = start + len(insert)

            await ui.redraw(editor)
            return

        # multiple results → common prefix
        common = self._common_prefix(candidates)

        if common.startswith(partial) and len(common) > len(partial):
            to_insert = common[len(partial):]
            insert = split_graphemes(to_insert)

            buf[c:c] = insert
            editor._cursor += len(insert)

            await ui.redraw(editor)

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