"""
CommandAPI — единый фасад для всех команд pvevmssh.

Предоставляет полный доступ ко всем возможностям:
  - терминал (вывод, ввод, цвет, очистка)
  - PTY и интерактивные процессы
  - окружение пользователя
  - права доступа
  - база данных (shortcut-методы)
  - криптография
  - мышь
  - альтернативный экран
  - глобальные сервисы
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional, Union

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
from .user import UserContext


# ANSI-цвета для write_success / write_error / write_warning
_ANSI_GREEN  = "\x1b[32m"
_ANSI_RED    = "\x1b[31m"
_ANSI_YELLOW = "\x1b[33m"
_ANSI_RESET  = "\x1b[0m"


class CommandAPI:
    """
    CommandAPI — основной фасад для всех команд.

    Команда получает один объект со всем необходимым:

        async def execute(api: CommandAPI) -> str | None:
            api.require_permission("db_viewer")
            row = await api.fetch_one(
                "SELECT group_id FROM users WHERE username = ?",
                (api.username,)
            )
            return f"Group: {row[0]}\\n" if row else "Not found.\\n"

    Разделы:
      - Права:        has_permission, has_any_permission, require_permission
      - Вывод:        write, writeln, write_line, write_success, write_error,
                      write_warning, clear, flush
      - Ввод:         read_line, prompt, confirm
      - БД:           fetch_one, fetch_all, fetch_val, execute (+ api.db напрямую)
      - Окружение:    env, env_get, env_set, env_unset, env_substitute
      - PTY:          run_interactive, pty
      - Мышь:         mouse, mouse_enable, mouse_disable
      - Экран:        enter_alt_screen, exit_alt_screen
      - Криптография: encrypt, decrypt, db_encrypt, db_decrypt
      - Прочее:       parser, config, global_store, user, logger
    """

    version = "1.0.0"

    def __init__(self, username: str, args: tuple[str, ...]) -> None:
        self.username: str = username
        self.args: tuple[str, ...] = args

        self.session = get_current_session()
        self.terminal: Terminal = self.session.extra["terminal"]
        self.env: UserEnvironment = self.session.extra["env"]
        self.permissions: set[str] = set(self.session.extra.get("permissions", []))

        self.logger: logging.Logger = logging.getLogger(f"cmd.{username}")

        # Lazy-инициализация
        self._db: Database | None = None
        self._user: UserContext | None = None
        self._config = None

    # =========================================================================
    # Свойства — ленивый доступ к сервисам
    # =========================================================================

    @property
    def db(self) -> Database:
        """База данных (SQLite или MariaDB). Инициализируется при первом обращении."""
        if self._db is None:
            self._db = GlobalStore.get().require("db")
        return self._db

    @property
    def pty(self) -> PTYHandler:
        """PTYHandler — для запуска интерактивных приложений (bash, vim, htop ...)."""
        return self.terminal.pty

    @property
    def mouse(self):
        """MouseHandler — управление мышью в TUI-командах."""
        return self.terminal.input.mouse

    @property
    def rows(self) -> int:
        """Текущая высота терминала в строках."""
        return self.session.term_height

    @property
    def cols(self) -> int:
        """Текущая ширина терминала в символах."""
        return self.session.term_width

    @property
    def user(self) -> UserContext:
        """
        Контекст пользователя с удобными методами для работы с данными из БД:
        ssh_keys, history, saved_env.
        """
        if self._user is None:
            self._user = UserContext(self.username, self.db)
        return self._user

    @property
    def config(self):
        """
        Конфигурация сервера (helpers.config.Config).
        Используй api.config.get("pve.main_node_host") и т.п.
        """
        if self._config is None:
            self._config = GlobalStore.get().require("config")
        return self._config

    # =========================================================================
    # Права доступа
    # =========================================================================

    def has_permission(self, perm: str) -> bool:
        """
        Проверяет наличие права у пользователя.
        Право 'admin' даёт доступ ко всему автоматически.

        Пример:
            if api.has_permission("db_viewer"):
                ...
        """
        return "admin" in self.permissions or perm in self.permissions

    def has_any_permission(self, *perms: str) -> bool:
        """
        Проверяет наличие хотя бы одного из перечисленных прав.

        Пример:
            if api.has_any_permission("db_admin", "superuser"):
                ...
        """
        return any(self.has_permission(p) for p in perms)

    def require_permission(self, perm: str) -> None:
        """
        Требует наличие права. Выбрасывает CommandPermissionError если права нет.

        Пример:
            api.require_permission("db_admin")
        """
        if not self.has_permission(perm):
            raise CommandPermissionError(f"Недостаточно прав: требуется '{perm}'")

    # =========================================================================
    # Парсер аргументов
    # =========================================================================

    def parser(self, prog: str | None = None) -> CommandParser:
        """
        Возвращает CommandParser для разбора аргументов команды.

        Пример:
            parser = api.parser("userinfo")
            parser.add_flag("--all", "-a", help="Показать все поля")
            parser.add_option("--user", help="Целевой пользователь")
            ns = parser.parse(api.args)
            if ns.help:
                return HELP
        """
        return CommandParser(prog=prog or self.args[0] if self.args else "command")

    # =========================================================================
    # Глобальные сервисы
    # =========================================================================

    def global_store(self) -> GlobalStore:
        """
        Ссылка на GlobalStore — контейнер глобальных сервисов.
        Используй, если нужно получить сервис, не доступный через api напрямую.

        Пример:
            pve_client = api.global_store().require("pve_client")
        """
        return GlobalStore.get()

    # =========================================================================
    # Криптография
    # =========================================================================

    def encrypt(self, value: str) -> str:
        """
        Шифрует строку с помощью AES-GCM (master key из конфига).
        Результат можно безопасно хранить в БД.

        Пример:
            encrypted = api.encrypt(api_secret)
            await api.execute("UPDATE users SET api_secret = ? WHERE username = ?",
                              (encrypted, api.username))
        """
        from helpers.crypto import encrypt as _encrypt
        return _encrypt(value)

    def decrypt(self, value: str) -> str:
        """
        Расшифровывает строку, зашифрованную через encrypt().

        Пример:
            secret = api.decrypt(row[0])
        """
        from helpers.crypto import decrypt as _decrypt
        return _decrypt(value)

    # Алиасы для явного контекста "шифрование для БД"
    def db_encrypt(self, value: str) -> str:
        """Псевдоним encrypt() — шифрует перед записью в БД."""
        return self.encrypt(value)

    def db_decrypt(self, value: str) -> str:
        """Псевдоним decrypt() — расшифровывает после чтения из БД."""
        return self.decrypt(value)

    # =========================================================================
    # Окружение пользователя
    # =========================================================================

    def env_get(self, key: str, default: Any = None) -> Any:
        """Получить переменную окружения текущей сессии."""
        return self.env.get(key, default)

    def env_set(self, key: str, value: str) -> None:
        """Установить переменную окружения в текущей сессии."""
        self.env.set(key, value)

    def env_unset(self, key: str) -> None:
        """Удалить переменную окружения из текущей сессии."""
        self.env.unset(key)

    def env_substitute(self, text: str) -> str:
        """Подставить $VAR-переменные в строку."""
        return self.env.substitute(text)

    # =========================================================================
    # Вывод
    # =========================================================================

    async def write(self, data: str | bytes) -> None:
        """
        Записать строку или байты в терминал пользователя.

        Пример:
            await api.write("Hello\\n")
            await api.write(b"\\x1b[2J\\x1b[H")
        """
        if isinstance(data, str):
            await self.terminal.output.output_str(data)
        else:
            await self.terminal.output.output_bytes(data)

    async def writeln(self, text: str = "") -> None:
        """
        Записать строку и перевести на новую строку.

        Пример:
            await api.writeln("Done.")
        """
        await self.write(text + "\n")

    # Псевдоним для единообразия
    write_line = writeln

    async def write_success(self, text: str) -> None:
        """
        Вывести сообщение зелёным цветом (операция выполнена успешно).

        Пример:
            await api.write_success("SSH key added.")
        """
        await self.write(f"{_ANSI_GREEN}{text}{_ANSI_RESET}\n")

    async def write_error(self, text: str) -> None:
        """
        Вывести сообщение красным цветом (ошибка).

        Пример:
            await api.write_error("User not found.")
        """
        await self.write(f"{_ANSI_RED}{text}{_ANSI_RESET}\n")

    async def write_warning(self, text: str) -> None:
        """
        Вывести сообщение жёлтым цветом (предупреждение).

        Пример:
            await api.write_warning("No keys configured.")
        """
        await self.write(f"{_ANSI_YELLOW}{text}{_ANSI_RESET}\n")

    async def clear(self) -> None:
        """Очистить экран (ANSI: ED + cursor home)."""
        await self.write(b"\x1b[2J\x1b[H")

    async def flush(self) -> None:
        """Принудительно сбросить буфер вывода (если поддерживается)."""
        if hasattr(self.terminal.output, "flush"):
            await self.terminal.output.flush()

    # =========================================================================
    # Ввод
    # =========================================================================

    async def read_line(self, prompt: str = "") -> str:
        """
        Прочитать одну строку от пользователя.
        Если задан prompt — вывести его перед ожиданием ввода.

        Пример:
            name = await api.read_line("Enter name: ")
        """
        if prompt:
            await self.write(prompt)
        return await self.terminal.input.read_str()

    # Псевдоним
    prompt = read_line

    async def read_line_secret(self, prompt: str = "") -> str:
        """
        Прочитать строку с отключённым эхо (скрытый ввод).
        Полезно для паролей и секретов.

        Пример:
            secret = await api.read_secret("Enter token: ")
        """
        if prompt:
            await self.write(prompt)

        # Сохраняем текущее состояние эхо
        echo_was_enabled = self.terminal.input.editor.echo

        self.terminal.input.editor.echo = False
        try:
            # Читаем строку (эхо отключено)
            result = await self.terminal.input.read_str()
        finally:
            # Восстанавливаем эхо
            if echo_was_enabled:
                self.terminal.input.editor.echo = True

        # Добавляем перевод строки после ввода для красоты
        await self.write("\n")
        return result or ""

    async def confirm(self, prompt: str = "Подтвердить? [y/N]: ") -> bool:
        """
        Запросить подтверждение у пользователя.
        Возвращает True при 'y' / 'yes' / 'да'.
        Выбрасывает CommandAbort при любом другом вводе.

        Пример:
            if not await api.confirm(f"Delete key #{idx}? [y/N]: "):
                return "Cancelled.\\n"
            # или:
            await api.confirm("Continue? [y/N]: ")  # само бросит CommandAbort
        """
        ans = (await self.read_line(prompt)).strip().lower()
        if ans in ("y", "yes", "да"):
            return True
        raise CommandAbort("Операция отменена пользователем")

    # =========================================================================
    # База данных — shortcut-методы
    # =========================================================================

    async def fetch_one(
        self,
        query: str,
        params: tuple | None = None,
    ) -> tuple | None:
        """
        Выполнить SELECT и вернуть одну строку (tuple) или None.

        Важно: строка — это tuple, не dict.
        Используй распаковку:
            row = await api.fetch_one("SELECT a, b FROM t WHERE id = ?", (1,))
            if not row:
                return "Not found.\\n"
            a, b = row

        Пример:
            row = await api.fetch_one(
                "SELECT group_id, created_at FROM users WHERE username = ?",
                (api.username,)
            )
        """
        return await self.db.fetch_one(query, params)

    async def fetch_all(
        self,
        query: str,
        params: tuple | None = None,
    ) -> list[tuple]:
        """
        Выполнить SELECT и вернуть список строк (list of tuples).

        Пример:
            rows = await api.fetch_all("SELECT username FROM users ORDER BY username")
            for (username,) in rows:
                await api.writeln(username)
        """
        return await self.db.fetch_all(query, params)

    async def fetch_val(
        self,
        query: str,
        params: tuple | None = None,
    ) -> Any:
        """
        Выполнить SELECT и вернуть первое поле первой строки.
        Удобно для COUNT, скалярных значений, одного поля.

        Пример:
            count = await api.fetch_val("SELECT COUNT(*) FROM users")
            raw_keys = await api.fetch_val(
                "SELECT ssh_keys FROM users WHERE username = ?", (api.username,)
            )
        """
        return await self.db.fetch_val(query, params)

    async def execute(
        self,
        query: str,
        params: tuple | None = None,
    ) -> Any:
        """
        Выполнить INSERT / UPDATE / DELETE (или любой SQL).
        Для нескольких связанных изменений используй api.db.transaction().

        Пример:
            await api.execute(
                "UPDATE users SET group_id = ? WHERE username = ?",
                (new_group, api.username)
            )
            await api.db.commit()

            # Или через транзакцию:
            async with api.db.transaction():
                await api.execute("UPDATE ...")
                await api.execute("UPDATE ...")
        """
        return await self.db.execute(query, params)

    # =========================================================================
    # PTY — интерактивные процессы
    # =========================================================================

    async def run_interactive(
        self,
        cmd: str = "/bin/bash",
        args: list[str] | None = None,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        alt_screen: bool = True,
    ) -> None:
        """
        Запустить интерактивное приложение через PTY.

        Автоматически:
          - создаёт PTY;
          - синхронизирует размер окна;
          - если alt_screen=True — переключает в альтернативный экран;
          - ожидает завершения процесса;
          - возвращает экран и очищает ресурсы в finally.

        Пример:
            await api.run_interactive("/bin/bash", ["-i"])
            await api.run_interactive("/usr/bin/vim", ["/etc/hosts"])
            await api.run_interactive(cmd="/usr/bin/htop", alt_screen=False)

        Args:
            cmd:        путь к исполняемому файлу.
            args:       список аргументов.
            cwd:        рабочая директория процесса.
            env:        переменные окружения (по умолчанию — из api.env + os.environ).
            alt_screen: переключать ли в альтернативный экран (True по умолчанию).
        """
        if args is None:
            args = []

        # Собираем окружение процесса
        if env is None:
            process_env = os.environ.copy()
            process_env.update(self.env._vars)
        else:
            process_env = env

        # Устанавливаем TERM если не задан
        process_env.setdefault("TERM", self.env.get("TERM", "xterm-256color"))

        await self.pty.ensure()
        await self.pty.resize(self.rows, self.cols)

        try:
            if alt_screen:
                await self.enter_alt_screen()

            proc = await self.pty.spawn(
                cmd,
                *args,
                env=process_env,
                cwd=cwd,
                attach_streams=False,
            )

            await self.pty.attach_streams()
            await proc.wait()

        finally:
            try:
                await self.pty.detach_streams()
            except Exception:
                pass
            if alt_screen:
                await self.exit_alt_screen()

    # =========================================================================
    # Мышь
    # =========================================================================

    async def mouse_enable(self, modes: int | list[int] = 1006) -> None:
        """
        Включить поддержку мыши.

        Рекомендуемые режимы:
          1000 — базовые клики
          1002 — drag/motion
          1006 — SGR-формат (рекомендуется всегда добавлять)

        Пример:
            await api.mouse_enable([1002, 1006])
        """
        await self.mouse.enable(modes)

    async def mouse_disable(self) -> None:
        """
        Отключить все активные режимы мыши.
        Всегда вызывай в finally, если включал мышь.

        Пример:
            await api.mouse_enable([1000, 1006])
            try:
                ...
            finally:
                await api.mouse_disable()
        """
        await self.mouse.disable()

    # =========================================================================
    # Альтернативный экран
    # =========================================================================

    async def enter_alt_screen(self) -> None:
        """
        Переключиться в альтернативный экран (xterm 1049).
        Сохраняет текущее содержимое терминала.

        Всегда вызывай exit_alt_screen() в finally.

        Пример:
            await api.enter_alt_screen()
            try:
                await api.clear()
                await api.writeln("Full-screen mode")
                await api.read_line("Press Enter to exit...")
            finally:
                await api.exit_alt_screen()
        """
        await self.write(b"\x1b[?1049h")

    async def exit_alt_screen(self) -> None:
        """
        Вернуться из альтернативного экрана к основному буферу.
        Вызывай в finally после enter_alt_screen().
        """
        await self.write(b"\x1b[?1049l")