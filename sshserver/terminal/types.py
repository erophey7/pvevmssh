"""Types and signals for terminal layer."""

from typing import NewType

# Sentinel for Ctrl+D on empty line
EOF = NewType("EOF", object)
EOF = object()   # singleton

__all__ = ["EOF"]