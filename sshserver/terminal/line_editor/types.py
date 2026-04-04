from dataclasses import dataclass, field
from ..types import EOF


@dataclass
class VisualCell:
    text: str
    width: int
    buffer_index: int | None


@dataclass
class ScreenPos:
    row: int
    col: int


@dataclass
class Layout:
    rows: list[list[VisualCell]] = field(default_factory=list)
    index_to_pos: list[ScreenPos] = field(default_factory=list)
    cursor_pos: ScreenPos = field(default_factory=lambda: ScreenPos(0, 1))
    end_pos: ScreenPos = field(default_factory=lambda: ScreenPos(0, 1))
    rendered_text: str = ""
    pending_wrap: bool = False

__all__ = [
    "EOF",
    "ScreenPos",
    "VisualCell",
    "Layout",
]