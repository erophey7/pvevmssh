# sshserver/lsp_engine.py
import typing as t
from collections import defaultdict
import logging
import asyncio
import inspect

logger = logging.getLogger(__name__)


class TrieNode:
    def __init__(self):
        self.children: dict[str, "TrieNode"] = {}
        self.is_end_of_word: bool = False

    def insert(self, word: str) -> None:
        node = self
        for char in word:
            if char not in node.children:
                node.children[char] = TrieNode()
            node = node.children[char]
        node.is_end_of_word = True

    def collect(self, prefix: str) -> list[str]:
        node = self
        for char in prefix:
            if char not in node.children:
                return []
            node = node.children[char]
        return self._collect_words(node, prefix)

    def _collect_words(self, node: "TrieNode", prefix: str) -> list[str]:
        results: list[str] = []

        if node.is_end_of_word:
            results.append(prefix)

        for char, child in sorted(node.children.items()):
            results.extend(child._collect_words(child, prefix + char))

        return results


class LSPEngine:
    def __init__(self):
        self._command_trie = TrieNode()
        self._arg_tries = defaultdict(TrieNode)
        self._global_words: set[str] = set()

        self._dynamic_providers: list[t.Callable] = []
        self._semantic_providers: list[t.Callable] = []

        self._clients: dict[str, t.Any] = {}
        self._default_client: str | None = None
        self._active_clients: set[str] = set()


    # ======================================================
    # utils
    # ======================================================

    async def _maybe_await(self, fn, *args, **kwargs):
        if inspect.iscoroutinefunction(fn):
            return await fn(*args, **kwargs)
        return fn(*args, **kwargs)

    # ======================================================
    # registration
    # ======================================================

    def register_command(self, command: str, arguments: list[str] | None = None):
        logger.debug(f"Register command: {command} args={arguments}")

        self._command_trie.insert(command)

        if arguments:
            for arg in arguments:
                self._arg_tries[command].insert(arg)

    def register_global_words(self, words: list[str] | str):
        if isinstance(words, str):
            words = [words]

        cleaned = [w.strip() for w in words if w.strip()]
        self._global_words.update(cleaned)

    def register_dynamic_provider(self, provider):
        self._dynamic_providers.append(provider)

    def register_semantic_provider(self, provider):
        """Регистрирует провайдер, который умеет возвращать semantic_tokens(text)"""
        self._semantic_providers.append(provider)

    # ======================================================
    # clients
    # ======================================================

    def add_client(self, name: str, client):
        if name in self._clients:
            raise ValueError(f"Client '{name}' already exists")

        self._clients[name] = client

        if hasattr(client, "register"):
            # sync or async safe
            if inspect.iscoroutinefunction(client.register):
                asyncio.create_task(client.register(self))
            else:
                client.register(self)

        return self

    def del_client(self, name: str):
        self._clients.pop(name, None)
        self._active_clients.discard(name)

        if name == self._default_client:
            self._default_client = None

    def setup_default(self, name: str):
        if name not in self._clients:
            raise ValueError(f"Client '{name}' not registered")
        self._default_client = name

    def set_active(self, names: list[str]):
        self._active_clients = set(names)

    def _get_active_clients(self):
        if self._active_clients:
            return [self._clients[n] for n in self._active_clients]

        if self._default_client:
            return [self._clients[self._default_client]]

        return []

    # ======================================================
    # completion core (ASYNC)
    # ======================================================

    async def get_completions(self, partial: str, previous_tokens: list[str] | None = None):
        if previous_tokens is None:
            previous_tokens = []

        candidates = []

        for provider in self._dynamic_providers:
            try:
                res = await self._maybe_await(provider, partial, previous_tokens)
                if res:
                    candidates.extend(res)
            except Exception:
                pass

        for client in self._get_active_clients():
            try:
                if hasattr(client, "get_completions"):
                    res = await self._maybe_await(
                        client.get_completions,
                        partial,
                        previous_tokens,
                    )
                    if res:
                        candidates.extend(res)
            except Exception:
                pass

        if not candidates:
            if not previous_tokens:
                candidates.extend(
                    await asyncio.to_thread(self._command_trie.collect, partial)
                )
            elif previous_tokens[0] in self._arg_tries:
                candidates.extend(
                    await asyncio.to_thread(
                        self._arg_tries[previous_tokens[0]].collect,
                        partial,
                    )
                )

            candidates.extend(
                [w for w in self._global_words if w.startswith(partial)]
            )

        return sorted(set(candidates))
    
    async def get_semantic_tokens(self, text: str) -> dict:
        """Вызывает все зарегистрированные semantic-провайдеры"""
        for provider in self._semantic_providers:
            try:
                res = await self._maybe_await(provider, text)
                if isinstance(res, dict) and "styles" in res:
                    return res
            except Exception as e:
                logger.debug("semantic provider failed", exc_info=True)
                continue
        return {"tokens": []}

    async def _maybe_await(self, fn, *args):
        if inspect.iscoroutinefunction(fn):
            return await fn(*args)
        return fn(*args)
    
    # ======================================================
    # LSP LAYER (NEW)
    # ======================================================
    
    async def on_initialize(self, params: dict):
        return {
            "capabilities": {
                "textDocumentSync": 1,
                "completionProvider": {"triggerCharacters": [" "]},
                "hoverProvider": True,
            }
        }

    async def on_initialized(self, params: dict):
        return None

    async def on_did_open(self, params: dict):
        return None

    async def on_did_change(self, params: dict):
        return None

    async def on_did_close(self, params: dict):
        return None

    async def on_completion(self, params: dict):
        partial = params["partial"]
        tokens = params.get("tokens", [])
        return await self.get_completions(partial, tokens)

    async def on_hover(self, params: dict):
        text = params["text"]
        pos = params["position"]

        return {
            "contents": {
                "kind": "markdown",
                "value": f"```text\n{text}\n```",
            }
        }
    
    async def on_semantic_tokens(self, params: dict):
        text = params.get("text", "")
        return await self.get_semantic_tokens(text)