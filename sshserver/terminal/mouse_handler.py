import asyncio
import logging
from dataclasses import dataclass
from typing import Callable, Awaitable, Union, List

logger = logging.getLogger(__name__)


@dataclass
class MouseEvent:
    """Terminal mouse event."""
    button: int      # 0=left, 1=middle, 2=right (wheel not mapped)
    x: int           # 1-based column
    y: int           # 1-based row
    state: str       # 'press', 'release', 'motion'
    modifiers: int = 0
    wheel: int = 0   # 0=none, 1=up, -1=down


class MouseHandler:
    """
    Mouse tracking with support for modes 1000, 1002, 1003, 1006.
    """

    _MODES = {
        1000: (b"\x1b[?1000h", b"\x1b[?1000l"),
        1002: (b"\x1b[?1002h", b"\x1b[?1002l"),
        1003: (b"\x1b[?1003h", b"\x1b[?1003l"),
        1006: (b"\x1b[?1006h", b"\x1b[?1006l"),
    }

    def __init__(self, terminal):
        self.terminal = terminal
        self.active_modes: set[int] = set()
        self._listeners: list[Callable[[MouseEvent], Awaitable[None] | None]] = []

    ########## Mode Control ##########
    async def enable(self, modes: Union[int, str, List[int]] = 1000) -> bool:
        """Enable one or more mouse modes."""
        if isinstance(modes, (int, str)):
            modes = [int(modes)]
        elif not isinstance(modes, list):
            raise TypeError("modes must be int, str or list of ints")

        success = True
        for mode in modes:
            if mode in self.active_modes:
                continue
            if mode not in self._MODES:
                logger.warning(f"Unknown mouse mode {mode}, skipping")
                continue
            try:
                enable_seq, _ = self._MODES[mode]
                await self.terminal.output.output_bytes(enable_seq)
                self.active_modes.add(mode)
                logger.info(f"Mouse mode {mode} enabled")
            except Exception as e:
                logger.error(f"Failed to enable mouse mode {mode}: {e}")
                success = False
        return success

    async def disable(self, modes: Union[int, str, List[int], None] = None) -> bool:
        """Disable specified modes (or all if None)."""
        if modes is None:
            to_disable = list(self.active_modes.copy())
        else:
            if isinstance(modes, (int, str)):
                to_disable = [int(modes)]
            elif isinstance(modes, list):
                to_disable = [int(m) for m in modes]
            else:
                raise TypeError("modes must be int, str, list or None")

        success = True
        for mode in to_disable:
            if mode not in self.active_modes:
                continue
            if mode not in self._MODES:
                continue
            try:
                _, disable_seq = self._MODES[mode]
                await self.terminal.output.output_bytes(disable_seq)
                self.active_modes.discard(mode)
                logger.info(f"Mouse mode {mode} disabled")
            except Exception as e:
                logger.error(f"Failed to disable mouse mode {mode}: {e}")
                success = False
        return success

    ########## Listener Management ##########
    def add_listener(self, callback: Callable[[MouseEvent], Awaitable[None] | None]):
        if callback not in self._listeners:
            self._listeners.append(callback)

    def remove_listener(self, callback):
        if callback in self._listeners:
            self._listeners.remove(callback)

    ########## Parsing ##########
    async def feed(self, seq: bytes) -> bool:
        """Parse mouse event and notify listeners. Returns True if it was a mouse event."""
        if not self.active_modes or not seq.startswith(b'\x1b[<'):
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

            wheel = 0
            if b == 64:
                wheel = 1
            elif b == 65:
                wheel = -1

            button = b & 3
            is_motion = (b & 32) != 0
            is_release = text.endswith("m")

            state = "motion" if is_motion else ("release" if is_release else "press")
            event = MouseEvent(button=button, x=x, y=y, state=state, wheel=wheel)

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