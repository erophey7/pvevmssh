from __future__ import annotations
import argparse
from typing import Any

from .exceptions import CommandArgumentError


class CommandParser:
    def __init__(self, prog: str | None = None):
        self.parser = argparse.ArgumentParser(
            prog=prog,
            exit_on_error=False,
            add_help=False
        )
        self.subparsers = None

    def add_flag(self, *names: str, help: str = "") -> CommandParser:
        self.parser.add_argument(*names, action="store_true", help=help)
        return self

    def add_option(self, *names: str, help: str = "", default: Any = None) -> CommandParser:
        self.parser.add_argument(*names, help=help, default=default)
        return self

    def add_argument(self, name: str, help: str = "", required: bool = False) -> CommandParser:
        self.parser.add_argument(name, help=help, required=required)
        return self

    def add_subcommand(self, name: str, help: str = "") -> CommandParser:
        if self.subparsers is None:
            self.subparsers = self.parser.add_subparsers(dest="subcommand", required=True)
        self.subparsers.add_parser(name, help=help)
        return self

    def parse(self, args: tuple[str, ...]) -> argparse.Namespace:
        try:
            parsed, unknown = self.parser.parse_known_args(args)
            if unknown:
                raise CommandArgumentError(f"Неизвестные аргументы: {' '.join(unknown)}")
            return parsed
        except SystemExit:
            raise CommandArgumentError(self.parser.format_help())

    def help(self) -> str:
        return self.parser.format_help()