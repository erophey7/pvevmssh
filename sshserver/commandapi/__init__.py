"""
CommandAPI v3.0 — единый стабильный фасад для всех команд pvevmssh.

Предоставляет удобный доступ ко всем возможностям терминала, PTY, окружения,
базы данных, прав и глобального хранилища.
Поддерживает сценарии от простых команд до полноценных TUI-игр.
"""

from .api import CommandAPI
from .exceptions import (
    CommandError,
    CommandPermissionError,
    CommandArgumentError,
    CommandAbort,
    CommandNotFoundError,
    CommandRuntimeError,
)
from .parser import ArgumentParser

__all__ = [
    "CommandAPI",
    "CommandError",
    "CommandPermissionError",
    "CommandArgumentError",
    "CommandAbort",
    "CommandNotFoundError",
    "CommandRuntimeError",
    "ArgumentParser",
]

__version__ = "3.0.0"