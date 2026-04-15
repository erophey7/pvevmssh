"""
Performing silent refactor
in testing
"""


import typing as t
from .types import Key, KeyEvent


class KeymapManager:
    def __init__(self):
        self._default: dict[Key, t.Callable] = {}
        self._active: dict[Key, t.Callable] = {}

    async def _set_default_keymap(self, keymap: dict[Key, t.Callable]):
        self._default = dict(keymap)
        self._active = dict(keymap)

    async def set_keymap(self, keymap: dict[Key, t.Callable], force: bool = False):
        if force:
            self._active = dict(keymap)
        else:
            self._active.update(keymap)

    async def reset_default_keymap(self):
        self._active = dict(self._default)

    async def dispatch(self, event: KeyEvent):
        fn = self._active.get(event.key)
        if fn:
            return await fn(event)