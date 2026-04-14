from __future__ import annotations

import asyncio
import typing as t
import inspect
import logging

logger = logging.getLogger(__name__)


class InCodeLSPConnector:
    """
    Async in-process LSP bridge:
    Client ⇄ Connector ⇄ LSPEngine
    """

    def __init__(self, server):
        self.server = server

        self._loop = asyncio.get_event_loop()
        self._req_id = 0
        self._pending: dict[int, asyncio.Future] = {}

    # ======================================================
    # REQUEST
    # ======================================================

    async def request(self, method: str, params: dict) -> t.Any:
        self._req_id += 1
        req_id = self._req_id

        fut = self._loop.create_future()
        self._pending[req_id] = fut

        try:
            result = await self._dispatch(method, params)
            fut.set_result(result)
        except Exception as e:
            fut.set_exception(e)
        finally:
            self._pending.pop(req_id, None)

        return await fut

    # ======================================================
    # NOTIFY
    # ======================================================

    async def notify(self, method: str, params: dict) -> None:
        try:
            await self._dispatch(method, params)
        except Exception:
            logger.exception(f"notification failed: {method}")

    # ======================================================
    # DISPATCH
    # ======================================================

    async def _dispatch(self, method: str, params: dict):

        handler_name = self._map(method)

        if not hasattr(self.server, handler_name):
            raise ValueError(f"Unsupported LSP method: {method}")

        handler = getattr(self.server, handler_name)

        if inspect.iscoroutinefunction(handler):
            return await handler(params)
        return handler(params)

    # ======================================================
    # METHOD MAP
    # ======================================================

    def _map(self, method: str) -> str:
        return {
            "initialize": "on_initialize",
            "initialized": "on_initialized",

            "textDocument/didOpen": "on_did_open",
            "textDocument/didChange": "on_did_change",
            "textDocument/didClose": "on_did_close",

            "textDocument/completion": "on_completion",
            "textDocument/hover": "on_hover",
        }.get(method, "on_" + method.replace("/", "_"))

    # ======================================================
    # CLIENT API (used by LSPAdapter)
    # ======================================================

    async def completion(self, partial: str, tokens: list[str]) -> list[str]:
        logger.debug("Complete request: partial=%s | tokens=%s", partial, tokens)
        answer = await self.request(
            "textDocument/completion",
            {"partial": partial, "tokens": tokens},
        )
        logger.debug(f"Complete answer: {answer}")
        return answer

    async def hover(self, text: str, position: int):
        logger.debug("Hover request: text=%s | position=%s", text, position)
        answer = await self.request(
            "textDocument/hover",
            {"text": text, "position": position},
        )
        logger.debug(f"Hover answer: {answer}")
        return answer