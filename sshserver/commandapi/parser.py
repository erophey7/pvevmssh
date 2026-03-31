from __future__ import annotations
from typing import Any, Dict, List, Tuple

from .exceptions import CommandArgumentError


class CommandParser:
    """
    Собственный простой и расширяемый парсер аргументов.
    Не зависит от argparse. Поддерживает флаги, именованные опции и позиционные аргументы.
    """

    def __init__(self, prog: str | None = None):
        self.prog = prog or "command"
        self.description: str = ""
        self._flags: List[str] = []
        self._options: Dict[str, Any] = {}
        self._positional: List[str] = []

    def add_flag(self, name: str, help: str = "") -> CommandParser:
        """Добавляет флаг (--verbose, -v)."""
        self._flags.append(name.lstrip("-"))
        return self

    def add_option(self, name: str, default: Any = None, help: str = "") -> CommandParser:
        """Добавляет именованную опцию (--count 5)."""
        clean_name = name.lstrip("-")
        self._options[clean_name] = default
        return self

    def add_positional(self, name: str, help: str = "") -> CommandParser:
        """Добавляет позиционный аргумент."""
        self._positional.append(name)
        return self

    def parse(self, args: tuple[str, ...] | list[str]) -> Dict[str, Any]:
        """Парсит аргументы и возвращает словарь."""
        result: Dict[str, Any] = {name: default for name, default in self._options.items()}
        result.update({flag: False for flag in self._flags})

        i = 0
        positional_idx = 0
        while i < len(args):
            arg = args[i]
            if arg.startswith("--"):
                key = arg[2:]
                if key in self._options:
                    i += 1
                    if i < len(args):
                        result[key] = args[i]
                    else:
                        result[key] = True
                elif key in self._flags:
                    result[key] = True
                else:
                    raise CommandArgumentError(f"Неизвестная опция: {arg}")
            elif arg.startswith("-") and len(arg) > 1:
                # короткие флаги -v -h пока не поддерживаются в полной мере
                raise CommandArgumentError("Короткие флаги пока не поддерживаются")
            else:
                # позиционный аргумент
                if positional_idx < len(self._positional):
                    result[self._positional[positional_idx]] = arg
                    positional_idx += 1
                else:
                    raise CommandArgumentError(f"Лишний позиционный аргумент: {arg}")
            i += 1

        # проверка обязательных позиционных
        for pos in self._positional:
            if pos not in result:
                raise CommandArgumentError(f"Отсутствует обязательный аргумент: {pos}")

        return result

    def help(self) -> str:
        """Возвращает строку помощи."""
        lines = [f"Usage: {self.prog} [options]"]
        if self.description:
            lines.append(self.description)
        if self._flags:
            lines.append("\nFlags:")
            for f in self._flags:
                lines.append(f"  --{f}")
        if self._options:
            lines.append("\nOptions:")
            for opt, default in self._options.items():
                lines.append(f"  --{opt} (default: {default})")
        if self._positional:
            lines.append("\nPositional arguments:")
            for p in self._positional:
                lines.append(f"  {p}")
        return "\n".join(lines)