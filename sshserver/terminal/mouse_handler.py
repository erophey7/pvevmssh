"""
Minimal Mouse Handler — only parsing and mode control.
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Callable, Awaitable

logger = logging.getLogger(__name__)


@dataclass
class MouseEvent:
    """Представляет событие мыши в терминале."""
    button: int      # 0 = left, 1 = middle, 2 = right
    x: int           # column (1-based)
    y: int           # row (1-based)
    state: str       # 'press', 'release', 'motion'
    modifiers: int = 0


class MouseHandler:
    """
    Лёгкий обработчик мыши.
    Предоставляет минимальный API для включения/выключения и подписки на события.
    """

    def __init__(self, terminal):
        self.terminal = terminal
        self.enabled = False
        self._listeners: list[Callable[[MouseEvent], Awaitable[None] | None]] = []

    async def enable(self, mode: int = 1006) -> bool:
        """Включает режим отслеживания мыши."""
        if self.enabled:
            return True

        try:
            await self.terminal.output.output_str(f"\x1b[?{mode}h")
            await self.terminal.output.output_str("\x1b[?1006h")  # SGR Extended
            self.enabled = True
            logger.info(f"Mouse tracking enabled (SGR mode {mode})")
            return True
        except Exception as e:
            logger.error(f"Failed to enable mouse: {e}")
            return False

    async def disable(self) -> bool:
        """Выключает режим отслеживания мыши."""
        if not self.enabled:
            return True

        try:
            await self.terminal.output.output_str("\x1b[?1000l")
            await self.terminal.output.output_str("\x1b[?1006l")
            self.enabled = False
            logger.info("Mouse tracking disabled")
            return True
        except Exception as e:
            logger.error(f"Failed to disable mouse: {e}")
            return False

    def add_listener(self, callback: Callable[[MouseEvent], Awaitable[None] | None]):
        """Подписаться на события мыши."""
        if callback not in self._listeners:
            self._listeners.append(callback)

    def remove_listener(self, callback):
        """Отписаться от событий мыши."""
        if callback in self._listeners:
            self._listeners.remove(callback)

    async def feed(self, seq: bytes) -> bool:
        """Парсит последовательность и вызывает слушателей. Возвращает True, если это было mouse событие."""
        if not self.enabled or not seq.startswith(b'\x1b[<'):
            return False

        try:
            text = seq.decode("ascii", errors="replace")
            content = text[3:].rstrip("mM")
            parts = content.split(";")

            if len(parts) < 3:
                return False

            b = int(parts[0])
            x = int(parts[1])
            y = int(parts[2])

            button = b & 3
            is_motion = (b & 32) != 0
            is_release = text.endswith("m")

            state = "motion" if is_motion else ("release" if is_release else "press")

            event = MouseEvent(button=button, x=x, y=y, state=state)

            # Вызываем всех слушателей
            for cb in self._listeners[:]:
                try:
                    result = cb(event)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as e:
                    logger.exception("Mouse listener error")

            return True

        except Exception as e:
            logger.debug(f"Failed to parse mouse event: {e}")
            return False