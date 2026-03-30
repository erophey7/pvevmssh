class CommandError(Exception):
    """Базовое исключение команд."""
    pass


class CommandPermissionError(CommandError):
    """Недостаточно прав."""
    pass


class CommandArgumentError(CommandError):
    """Ошибка парсинга аргументов."""
    pass


class CommandAbort(CommandError):
    """Команда прервана пользователем (например, confirm=False)."""
    pass