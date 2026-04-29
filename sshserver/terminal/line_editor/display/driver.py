import logging
import re
from typing import TYPE_CHECKING

from . import ansi

if TYPE_CHECKING:
    from sshserver.terminal import Terminal

logger = logging.getLogger(__name__)


class TerminalDriver:
    """
    Полноценный драйвер терминала.
    Инкапсулирует вывод, CPR, размеры и абсолютную позицию курсора.
    """

    def __init__(self, terminal: "Terminal"):
        self.terminal = terminal
        self._abs_pos: tuple[int, int] | None = None  # 1-based (row, col)

    # -- state -----------------------------------------------------
    @property
    def abs_pos(self) -> tuple[int, int] | None:
        return self._abs_pos

    def set_abs_pos(self, row: int, col: int) -> None:
        self._abs_pos = (row, col)

    def clear_abs_pos(self) -> None:
        self._abs_pos = None

    def get_size(self) -> tuple[int, int]:
        return self.terminal.session.term_width, self.terminal.session.term_height

    # -- output ----------------------------------------------------
    async def write(self, data: bytes | str) -> None:
        if isinstance(data, str):
            data = data.encode("utf-8", "replace")
        await self.terminal.output.output_bytes(data)

    # -- cursor ----------------------------------------------------
    def move_cursor(self, row_0based: int, col_1based: int) -> bytes:
        return ansi.move_cursor(row_0based, col_1based)

    # -- clearing --------------------------------------------------
    def clear_screen(self) -> bytes:
        self._abs_pos = (1, 1)
        return ansi.CLEAR_SCREEN + ansi.CURSOR_HOME

    def clear_to_end_of_line(self) -> bytes:
        return ansi.CLEAR_TO_END_OF_LINE

    def clear_to_end_of_screen(self) -> bytes:
        return ansi.CLEAR_TO_END_OF_SCREEN

    # -- CPR -------------------------------------------------------
    async def request_cursor_position(self, timeout: float = 0.05) -> tuple[int, int] | None:
        await self.write(ansi.REQUEST_CURSOR_POSITION)
        try:
            response = await self.terminal.input.read_until(b"R", timeout=timeout)
        except Exception:
            logger.debug("CPR timeout")
            return None

        if not response:
            return None

        match = re.search(rb"\x1b\[(\d+);(\d+)R", response)
        if not match:
            return None

        row = int(match.group(1))
        col = int(match.group(2))
        self._abs_pos = (row, col)
        logger.debug("CPR: row=%d col=%d", row, col)
        return row, col