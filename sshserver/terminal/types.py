"""Types and signals for terminal layer."""

from typing import NewType, Optional
from enum import Enum, auto
from dataclasses import dataclass

# Sentinel for Ctrl+D on empty line
EOF = NewType("EOF", object)
EOF = object()

class Key(Enum):
    # arrows
    UP = auto()
    DOWN = auto()
    LEFT = auto()
    RIGHT = auto()

    SHIFT_UP = auto()
    SHIFT_DOWN = auto()
    SHIFT_LEFT = auto()
    SHIFT_RIGHT = auto()

    CTRL_UP = auto()
    CTRL_DOWN = auto()
    CTRL_LEFT = auto()
    CTRL_RIGHT = auto()

    CTRL_SHIFT_UP = auto()
    CTRL_SHIFT_DOWN = auto()
    CTRL_SHIFT_LEFT = auto()
    CTRL_SHIFT_RIGHT = auto()

    CTRL_ALT_UP = auto()
    CTRL_ALT_DOWN = auto()
    CTRL_ALT_LEFT = auto()
    CTRL_ALT_RIGHT = auto()

    # navigation
    HOME = auto()
    END = auto()

    # delete
    BACKSPACE = auto()
    CTRL_BACKSPACE = auto()
    DEL = auto()
    CTRL_DEL = auto()

    CTRL_U = auto()
    CTRL_K = auto()

    # misc
    ENTER = auto()
    TAB = auto()
    ESC = auto()

    CTRL_L = auto()
    CTRL_C = auto()
    CTRL_D = auto()
    CTRL_R = auto()

    TEXT = auto()


@dataclass
class KeyEvent:
    key: Key
    data: Optional[str] = None


__all__ = [
    "EOF",
]