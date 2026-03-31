"""Исключения CommandAPI v3.0"""

class CommandError(Exception):
    """Базовое исключение для всех ошибок команд."""
    pass

class CommandPermissionError(CommandError):
    """Недостаточно прав для выполнения действия."""
    pass

class CommandArgumentError(CommandError):
    """Ошибка разбора аргументов команды."""
    pass

class CommandAbort(CommandError):
    """Операция отменена пользователем (confirm, Ctrl+C и т.п.)."""
    pass

class CommandNotFoundError(CommandError):
    """Команда не найдена (внутреннее использование)."""
    pass

class CommandRuntimeError(CommandError):
    """Ошибка во время выполнения (PTY, DB, сеть и т.д.)."""
    pass