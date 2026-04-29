from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..types import ScreenPos


@dataclass(frozen=True)
class ScreenCell:
    """Одна графема на экране (zsh-style cell)."""
    text: str
    width: int
    buffer_index: int | None = None
    style: str = ""
    highlight: bool = False


@dataclass
class ScreenLine:
    cells: list[ScreenCell] = field(default_factory=list)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ScreenLine):
            return NotImplemented
        return self.cells == other.cells


@dataclass
class ScreenBuffer:
    """Живое представление экрана терминала."""
    lines: list[ScreenLine] = field(default_factory=list)
    index_to_pos: list["ScreenPos"] = field(default_factory=list)
    cursor_pos: "ScreenPos" = field(default_factory=lambda: ScreenPos(0, 1))
    end_pos: "ScreenPos" = field(default_factory=lambda: ScreenPos(0, 1))
    pending_wrap: bool = False
    menu_grid: tuple[int, int] = (0, 0)
    # backward-compatible fields
    rendered_ansi: str = ""
    menu_ansi: str = ""
    menu_start_col: int = 1