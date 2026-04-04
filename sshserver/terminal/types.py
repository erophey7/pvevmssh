"""Types and signals for terminal layer."""

from typing import NewType

# Sentinel for Ctrl+D on empty line
EOF = NewType("EOF", object)
EOF = object()


__all__ = [
    "EOF",
]