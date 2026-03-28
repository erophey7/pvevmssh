"""Types and signals for terminal layer."""

from typing import NewType

# Сигнал завершения ввода (Ctrl+D на пустой строке)
EOF = NewType("EOF", object)
EOF = object()   # singleton

__all__ = ["EOF"]