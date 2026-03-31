from __future__ import annotations
import logging
from typing import Any, Dict

from helpers.globals import GlobalStore
from sshserver.session.manager import get_current_session
from sshserver.terminal.base import Terminal
from sshserver.terminal.pty_handler import PTYHandler
from sshserver.session.environment import UserEnvironment

from database.client import Database

from .exceptions import (
    CommandError,
    CommandPermissionError,
    CommandArgumentError,
    CommandAbort,
    CommandRuntimeError,
)
from .parser import CommandParser
from .user import UserContext   # будет создан ниже


class CommandAPI:
    """
    CommandAPI v0.2.1 — основной фасад для всех команд.

    Предоставляет удобный доступ ко всем возможностям проекта.
    """

    version = "0.2.1"

    def __init__(self, username: str, args: tuple[str, ...]):
        self.username = username
        self.args = args

        self.session = get_current_session()
        self.terminal: Terminal = self.session.extra["terminal"]
        self.env: UserEnvironment = self.session.extra["env"]
        self.permissions: set[str] = set(self.session.extra.get("permissions", []))

        self.logger = logging.getLogger(f"cmd.{username}")

        self._db: Database | None = None
        self._user: UserContext | None = None

    # ====================== Свойства ======================

    @property
    def db(self) -> Database:
        """Ссылка на текущую базу данных (SQLite или MariaDB)."""
        if self._db is None:
            self._db = GlobalStore.get().require("db")
        return self._db

    @property
    def pty(self) -> PTYHandler:
        """Ссылка на PTYHandler — для запуска интерактивных приложений (bash, vim и т.д.)."""
        return self.terminal.pty

    @property
    def mouse(self):
        """Ссылка на MouseHandler — управление мышью для TUI и игр."""
        return self.terminal.input.mouse

    @property
    def rows(self) -> int:
        """Текущая высота терминала в строках."""
        return self.terminal.rows

    @property
    def cols(self) -> int:
        """Текущая ширина терминала в символах."""
        return self.terminal.cols

    @property
    def user(self) -> UserContext:
        """Контекст пользователя с удобными методами работы с БД (ssh_keys, history, saved_env)."""
        if self._user is None:
            self._user = UserContext(self.username, self.db)
        return self._user

    # ====================== Права ======================

    def has_permission(self, perm: str) -> bool:
        """Проверяет наличие права (учитывает группу admin)."""
        return "admin" in self.permissions or perm in self.permissions

    def has_any(self, *perms: str) -> bool:
        """Проверяет наличие хотя бы одного из прав."""
        return any(self.has_permission(p) for p in perms)

    def require(self, perm: str) -> None:
        """Выбрасывает исключение, если права недостаточно."""
        if not self.has_permission(perm):
            raise CommandPermissionError(f"Недостаточно прав: требуется '{perm}'")

    # ====================== Парсер ======================

    def parser(self, prog: str | None = None) -> CommandParser:
        """Возвращает собственный парсер аргументов для текущей команды."""
        return CommandParser(prog=prog or (self.args[0] if self.args else "command"))

    # ====================== Глобальное хранилище ======================

    def global_store(self):
        """Ссылка на GlobalStore (конфиг, pve_client и другие глобальные объекты)."""
        return GlobalStore.get()

    # ====================== Криптография ======================

    def encrypt(self, value: str) -> str:
        """Шифрует строку (использует helpers/crypto)."""
        from helpers.crypto import encrypt
        return encrypt(value)

    def decrypt(self, value: str) -> str:
        """Расшифровывает строку."""
        from helpers.crypto import decrypt
        return decrypt(value)

    # ====================== Окружение ======================

    def env_get(self, key: str, default: Any = None) -> Any:
        """Получить переменную окружения пользователя."""
        return self.env.get(key, default)

    def env_set(self, key: str, value: Any) -> None:
        """Установить переменную окружения пользователя."""
        self.env.set(key, value)

    def env_unset(self, key: str) -> None:
        """Удалить переменную окружения."""
        self.env.unset(key)

    def env_substitute(self, text: str) -> str:
        """Подставить $VAR в строку."""
        return self.env.substitute(text)

    # ====================== Вывод и ввод (ссылки на terminal) ======================

    async def write(self, data: str | bytes) -> None:
        """Записать данные в терминал."""
        if isinstance(data, str):
            await self.terminal.output.output_str(data)
        else:
            await self.terminal.output.output_bytes(data)

    async def writeln(self, text: str = "") -> None:
        """Записать строку + перевод строки."""
        await self.write(text + "\n")

    async def clear(self) -> None:
        """Очистить экран."""
        await self.write("\x1b[2J\x1b[H")

    async def flush(self) -> None:
        """Принудительно сбросить буфер вывода."""
        await self.terminal.output.flush()

    async def read_line(self, prompt: str = "") -> str:
        """Прочитать строку от пользователя (использует line editor)."""
        if prompt:
            await self.write(prompt)
        return await self.terminal.input.read_str()

    async def confirm(self, prompt: str = "Подтвердить? [y/N]: ") -> bool:
        """Запрос подтверждения от пользователя."""
        ans = (await self.read_line(prompt)).strip().lower()
        if ans in ("y", "yes", "да"):
            return True
        raise CommandAbort("Операция отменена пользователем")

    # ====================== PTY ======================

    async def run_interactive(self, program: str = "bash", args: list[str] | None = None) -> None:
        """Запустить интерактивное приложение через PTY (bash, vim, htop и т.д.)."""
        if args is None:
            args = []
        await self.pty.ensure()
        await self.pty.resize(self.rows, self.cols)
        await self.pty.spawn(program, args, env=self.env.__dict__.get("_data", {}), attach_streams=True)

    # ====================== Мышь (для TUI) ======================

    async def mouse_enable(self, mode: int = 1006) -> None:
        """Включить поддержку мыши (рекомендуется 1006 для SGR)."""
        await self.mouse.enable(mode)

    async def mouse_disable(self) -> None:
        """Отключить поддержку мыши."""
        await self.mouse.disable()

    # ====================== Дополнительно ======================

    async def alt_screen(self, enter: bool = True) -> None:
        """Переключение в/из alternate screen (удобно для TUI)."""
        code = b"\x1b[?1049h" if enter else b"\x1b[?1049l"
        await self.write(code)