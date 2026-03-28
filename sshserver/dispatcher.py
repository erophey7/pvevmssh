"""
Advanced Command Dispatcher with support for categories, single-file and module commands.
Supports permission inheritance from parent categories.
"""

import asyncio
import importlib
import pkgutil
import logging
import shlex
from pathlib import Path
from typing import Any, Dict, Callable, Set, List

from helpers.globals import GlobalStore
from helpers.path import Paths
from sshserver.session.manager import get_current_session
from sshserver.permissions import has_permission

logger = logging.getLogger(__name__)


class CommandDispatcher:
    def __init__(self, username: str):
        self.username = username
        self.commands: Dict[str, Dict[str, Any]] = {}
        self._load_commands_recursively()

    def _load_commands_recursively(self, base_path: Path | None = None, parent_permissions: Set[str] = None):
        """
        Рекурсивная загрузка команд с наследованием прав.
        """
        if base_path is None:
            base_path = Paths.BASE_DIR / "commands"

        if parent_permissions is None:
            parent_permissions = set()

        if not base_path.exists():
            logger.warning("Commands directory not found: %s", base_path)
            return

        for item in pkgutil.iter_modules([str(base_path)]):
            name = item.name
            is_package = item.ispkg
            full_path = base_path / name

            if is_package:
                # Это либо категория, либо command module
                self._load_package(full_path, name, parent_permissions)
            else:
                # Single-file команда
                self._load_single_file(full_path, name, parent_permissions)

    def _load_single_file(self, file_path: Path, module_name: str, parent_perms: Set[str]):
        """Загрузка single-file команды (xxx.py)"""
        try:
            full_name = f"commands.{module_name}"
            if file_path.parent.name != "commands":
                # Для вложенных — строим правильный путь импорта
                rel_path = file_path.relative_to(Paths.BASE_DIR)
                full_name = ".".join(rel_path.with_suffix('').parts)

            module = importlib.import_module(full_name)

            if hasattr(module, "command") and isinstance(module.command, dict):
                cmd = module.command.copy()
                cmd_name = cmd.get("name", module_name)

                # Наследуем права от родительской категории, если не переопределены
                if "permissions" not in cmd or not cmd["permissions"]:
                    cmd["permissions"] = list(parent_perms)
                else:
                    cmd["permissions"] = list(set(cmd["permissions"]) | parent_perms)

                self.commands[cmd_name] = cmd
                logger.debug("Loaded single-file command: %s (perms: %s)", cmd_name, cmd.get("permissions"))
        except Exception as e:
            logger.error("Failed to load single-file command %s: %s", module_name, e)

    def _load_package(self, package_path: Path, package_name: str, parent_perms: Set[str]):
        """Загрузка пакета — может быть категорией или command module"""
        try:
            # Строим правильный импорт-путь
            rel_path = package_path.relative_to(Paths.BASE_DIR)
            full_name = ".".join(rel_path.parts)
            package = importlib.import_module(full_name)

            cmd_config = getattr(package, "command", None)

            if cmd_config and isinstance(cmd_config, dict) and cmd_config.get("type") == "command":
                # Это command module (команда-пакет)
                cmd = cmd_config.copy()
                cmd_name = cmd.get("name", package_name)

                if "permissions" not in cmd or not cmd["permissions"]:
                    cmd["permissions"] = list(parent_perms)
                else:
                    cmd["permissions"] = list(set(cmd["permissions"]) | parent_perms)

                self.commands[cmd_name] = cmd
                logger.debug("Loaded command module: %s", cmd_name)

            else:
                # Это обычная категория (group)
                category_perms = set(cmd_config.get("permissions", [])) if cmd_config else set()
                current_perms = parent_perms | category_perms

                logger.debug("Entering category: %s (inherited perms: %s)", package_name, current_perms)

                # Рекурсивно загружаем содержимое категории
                self._load_commands_recursively(package_path, current_perms)

        except Exception as e:
            logger.error("Failed to load package %s: %s", package_name, e)

    async def handle(self, input_line: str) -> Any:
        """Основная обработка команды"""
        try:
            parts = shlex.split(input_line)
        except ValueError as e:
            return f"Parse error: {e}"

        if not parts:
            return ""

        cmd_name = parts[0]
        args = parts[1:]

        if cmd_name == "help":
            if args:                          # help <command>
                return self._help_specific(args[0])
            return self._generate_help()      # обычный help

        cmd_config = self.commands.get(cmd_name)
        if not cmd_config:
            return f"Unknown command: '{cmd_name}'. Type 'help' for available commands."

        # Проверка прав
        required = cmd_config.get("permissions", [])
        session = get_current_session()

        if session and not has_permission(session, required):
            return f"Permission denied. Required: {required or 'none'}"

        # Выполнение
        try:
            func = cmd_config["func"]
            if asyncio.iscoroutinefunction(func):
                return await func(self.username, *args)
            else:
                return func(self.username, *args)
        except Exception as e:
            logger.exception("Error in command '%s'", cmd_name)
            return f"Error in command '{cmd_name}': {e}"

    def _generate_help(self) -> str:
        """Красивый общий help с группировкой по категориям и статусом прав"""
        session = get_current_session()
        user_perms = session.extra.get("permissions", set()) if session else set()

        lines = [
            "╔══════════════════════════════════════════════════════════════╗",
            "║                      Available Commands                      ║",
            "╚══════════════════════════════════════════════════════════════╝",
            ""
        ]

        # Группируем команды (пока просто по алфавиту, позже можно по категориям)
        sorted_cmds = sorted(self.commands.items())

        for name, cmd in sorted_cmds:
            help_text = cmd.get("help", cmd.get("desc", "No description"))
            required = cmd.get("permissions", [])

            if required:
                has_access = bool(user_perms & set(required))
                status = "✅" if has_access else "❌"
                perm_info = f" [{', '.join(required)}] {status}"
            else:
                status = "🌐"
                perm_info = " [available to everyone]"

            lines.append(f"  {status}  {name:<15} — {help_text}{perm_info}")

        lines.extend([
            "",
            "Usage:",
            "  help                  — show this help",
            "  help <command>        — show detailed help for specific command",
            "  Type command name to execute it.",
            ""
        ])

        return "\n".join(lines)
    
    def _help_specific(self, command_name: str) -> str:
        """Подробная справка по конкретной команде"""
        cmd = self.commands.get(command_name)
        if not cmd:
            return f"Command '{command_name}' not found."

        help_text = cmd.get("help", cmd.get("desc", "No description"))
        required = cmd.get("permissions", [])

        lines = [
            f"Command: {command_name}",
            f"Description: {help_text}",
            ""
        ]

        if required:
            session = get_current_session()
            user_perms = session.extra.get("permissions", set()) if session else set()
            has_access = bool(user_perms & set(required))

            lines.append("Required permissions:")
            for p in sorted(required):
                status = "✅ You have this permission" if p in user_perms else "❌ You don't have this permission"
                lines.append(f"  • {p}  {status}")
        else:
            lines.append("Permissions: Available to all users")

        lines.append("")
        lines.append("Usage: just type the command name.")

        return "\n".join(lines)


def get_command_dispatcher(username: str) -> CommandDispatcher:
    return CommandDispatcher(username)