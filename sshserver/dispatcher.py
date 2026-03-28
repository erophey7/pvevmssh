"""
Command Dispatcher — загрузка и выполнение команд с использованием централизованных путей.
Поддерживает single-file команды и команды-пакеты.
"""

import asyncio
import importlib
import pkgutil
import logging
import shlex
from pathlib import Path
from typing import Any, Dict, Callable

from helpers.globals import GlobalStore
from helpers.path import Paths
from sshserver.session.manager import get_current_session
from sshserver.permissions import has_permission

logger = logging.getLogger(__name__)


class CommandDispatcher:
    def __init__(self, username: str):
        self.username = username
        self.commands: Dict[str, Dict[str, Any]] = {}
        self._load_all_commands()

    def _load_all_commands(self) -> None:
        """Загружает все команды используя централизованные пути из helpers.path"""
        commands_path: Path = Paths.BASE_DIR / "commands"

        if not commands_path.exists():
            logger.error("Commands directory not found: %s", commands_path)
            return

        if not commands_path.is_dir():
            logger.error("Commands path is not a directory: %s", commands_path)
            return

        logger.debug("Scanning commands directory: %s", commands_path)

        # Используем pkgutil для сканирования пакетов и модулей
        for module_info in pkgutil.iter_modules([str(commands_path)]):
            name = module_info.name
            is_package = module_info.ispkg

            if is_package:
                self._load_package_command(name)
            else:
                self._load_single_file_command(name)

        logger.info("Loaded %d commands from %s", len(self.commands), commands_path)

    def _load_single_file_command(self, module_name: str) -> None:
        """Загрузка команды из одиночного .py файла"""
        try:
            full_name = f"commands.{module_name}"
            module = importlib.import_module(full_name)

            if hasattr(module, "command") and isinstance(module.command, dict):
                cmd_config = module.command
                cmd_name = cmd_config.get("name", module_name)

                self.commands[cmd_name] = cmd_config
                logger.debug("Loaded single-file command: %s", cmd_name)
            else:
                logger.debug("Module %s does not define 'command' dict", module_name)
        except Exception as e:
            logger.error("Failed to load single-file command '%s': %s", module_name, e)

    def _load_package_command(self, package_name: str) -> None:
        """Загрузка команды из директории-пакета (commands/mycmd/__init__.py)"""
        try:
            full_name = f"commands.{package_name}"
            package = importlib.import_module(full_name)

            if hasattr(package, "command") and isinstance(package.command, dict):
                cmd_config = package.command
                cmd_name = cmd_config.get("name", package_name)

                self.commands[cmd_name] = cmd_config
                logger.debug("Loaded package command: %s", cmd_name)
            else:
                logger.warning("Package '%s' missing 'command' dict in __init__.py", package_name)
        except Exception as e:
            logger.error("Failed to load package command '%s': %s", package_name, e)

    async def handle(self, input_line: str) -> Any:
        """Обработка введённой пользователем команды"""
        try:
            parts = shlex.split(input_line)
        except ValueError as e:
            return f"Parse error: {e}"

        if not parts:
            return ""

        cmd_name = parts[0]
        args = parts[1:]

        if cmd_name == "help":
            return self._generate_help()

        cmd_config = self.commands.get(cmd_name)
        if not cmd_config:
            return f"Unknown command: '{cmd_name}'. Type 'help' for available commands."

        # Проверка прав доступа
        required_permissions = cmd_config.get("permissions", [])
        session = get_current_session()

        if session and not has_permission(session, required_permissions):
            perm_str = ", ".join(required_permissions) if required_permissions else "none"
            return f"Permission denied. Required: {perm_str}"

        # Выполнение команды
        try:
            func: Callable = cmd_config["func"]

            if asyncio.iscoroutinefunction(func):
                result = await func(self.username, *args)
            else:
                result = func(self.username, *args)

            return result

        except Exception as e:
            logger.exception("Error executing command '%s'", cmd_name)
            return f"Error executing '{cmd_name}': {e}"

    def _generate_help(self) -> str:
        """Генерирует help с информацией о правах"""
        session = get_current_session()
        user_perms = session.extra.get("permissions", set()) if session else set()

        lines = ["Available commands:"]

        for name, cmd in sorted(self.commands.items()):
            help_text = cmd.get("help", "No description")
            required = cmd.get("permissions", [])

            if required:
                has_right = bool(user_perms & set(required))
                status = "✓" if has_right else "✗"
                perm_info = f" [{', '.join(required)}] {status}"
            else:
                perm_info = " [no restrictions]"

            lines.append(f"  {name:<15} - {help_text}{perm_info}")

        lines.append("\nType a command name to execute it.")
        return "\n".join(lines)


# Удобная фабричная функция
def get_command_dispatcher(username: str) -> CommandDispatcher:
    return CommandDispatcher(username)