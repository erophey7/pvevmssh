"""Types and signals for terminal layer."""

from typing import NewType
from dataclasses import dataclass, field

# Sentinel for Ctrl+D on empty line
EOF = NewType("EOF", object)
EOF = object()


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
    "VisualCell",
    "ScreenPos",
    "Layout",
]