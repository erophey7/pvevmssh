from __future__ import annotations
import logging
from typing import Any

from sshserver.session.manager import get_current_session
from helpers.globals import GlobalStore
from database.client import Database
from sshserver.terminal import Terminal
from sshserver.terminal.pty_handler import PTYHandler
from helpers.crypto import encrypt, decrypt

from .exceptions import CommandPermissionError, CommandError
from .parser import CommandParser
from .user import UserContext


class CommandAPI:
    """Единый стабильный API для всех команд."""

    def __init__(self, username: str, args: tuple[str, ...]):
        self.username = username
        self.args = args
        self.session = get_current_session()
        self.terminal: Terminal = self.session.extra["terminal"]
        self.env = self.session.extra["env"]
        self.permissions: set[str] = set(self.session.extra.get("permissions", []))
        self.logger = logging.getLogger(f"cmd.{username}")

        self._db: Database | None = None
        self._user: UserContext | None = None

    # ==================== Свойства ====================
    @property
    def db(self) -> Database:
        if self._db is None:
            self._db = GlobalStore.get().require("db")
        return self._db

    @property
    def pty(self) -> PTYHandler:
        return self.terminal.pty

    @property
    def mouse(self):
        return self.terminal.input.mouse

    @property
    def rows(self) -> int:
        return self.terminal.rows

    @property
    def cols(self) -> int:
        return self.terminal.cols

    @property
    def user(self) -> UserContext:
        if self._user is None:
            self._user = UserContext(self.username, self.db)
        return self._user

    # ==================== Права ====================
    def has_permission(self, perm: str) -> bool:
        return "admin" in self.permissions or perm in self.permissions

    def has_any_permission(self, *perms: str) -> bool:
        return any(self.has_permission(p) for p in perms)

    def require_permission(self, perm: str) -> None:
        if not self.has_permission(perm):
            raise CommandPermissionError(f"Недостаточно прав: {perm}")

    # ==================== Вывод ====================
    async def write(self, data: str) -> None:
        await self.terminal.output.output_str(data)

    async def writeln(self, text: str = "") -> None:
        await self.write(text + "\n")

    async def write_line(self, text: str = "") -> None:
        await self.writeln(text)

    async def write_success(self, text: str) -> None:
        await self.writeln(f"\x1b[32m{text}\x1b[0m")

    async def write_error(self, text: str) -> None:
        await self.writeln(f"\x1b[31m{text}\x1b[0m")

    async def write_warning(self, text: str) -> None:
        await self.writeln(f"\x1b[33m{text}\x1b[0m")

    async def flush(self) -> None:
        await self.terminal.output.flush()

    async def clear(self) -> None:
        await self.write(b"\x1b[2J\x1b[H")

    async def enter_alt_screen(self) -> None:
        await self.write(b"\x1b[?1049h")

    async def exit_alt_screen(self) -> None:
        await self.write(b"\x1b[?1049l")

    # ==================== Ввод ====================
    async def read_line(self, prompt: str = "") -> str:
        if prompt:
            await self.write(prompt)
        return await self.terminal.input.read_str()

    async def confirm(self, prompt: str = "Подтвердить? [y/N]: ") -> bool:
        answer = await self.read_line(prompt)
        return answer.strip().lower() in ("y", "yes")

    async def prompt(self, prompt: str) -> str:
        return await self.read_line(prompt)

    # ==================== PTY ====================
    async def run_interactive(
        self,
        cmd: str = None,
        args: list[str] | None = None,
        cwd: str | None = None,
        env: dict | None = None,
    ) -> None:
        """Запускает интерактивный процесс и отдаёт ему управление."""
        if args is None:
            args = ["-i"]
        if env is None:
            env = self.env.as_dict()

        await self.pty.ensure()
        await self.pty.resize(self.rows, self.cols)

        await self.enter_alt_screen()
        try:
            await self.pty.spawn(cmd, args, env=env, cwd=cwd)
            await self.pty.attach_streams()
        finally:
            await self.exit_alt_screen()

    # ==================== Парсер ====================
    def parser(self, prog: str | None = None) -> CommandParser:
        if prog is None:
            prog = self.args[0] if self.args else "command"
        return CommandParser(prog=prog)

    # ==================== DB shortcuts ====================
    async def fetch_one(self, query: str, params: tuple | list | None = None):
        return await self.db.fetch_one(query, params)

    async def fetch_all(self, query: str, params: tuple | list | None = None):
        return await self.db.fetch_all(query, params)

    async def execute(self, query: str, params: tuple | list | None = None):
        return await self.db.execute(query, params)
    
    # =================== DB crypt =====================

    def db_encrypt(self, prompt: str = "") -> str:
        return encrypt(prompt)

    def db_decrypt(self, prompt: str = "") -> str:
        return decrypt(prompt)