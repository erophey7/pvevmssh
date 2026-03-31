from __future__ import annotations
import argparse
from typing import Any

from .exceptions import CommandArgumentError


class CommandParser:
    def __init__(self, prog: str | None = None, _parser: argparse.ArgumentParser | None = None):
        self.parser = _parser or argparse.ArgumentParser(
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

    def add_argument(self, *names: str, **kwargs: Any) -> CommandParser:
        self.parser.add_argument(*names, **kwargs)
        return self

    def add_subcommand(self, name: str, help: str = "") -> CommandParser:
        if self.subparsers is None:
            self.subparsers = self.parser.add_subparsers(dest="subcommand", required=True)

        subparser = self.subparsers.add_parser(
            name,
            help=help,
            description=help,
            exit_on_error=False,
            add_help=False
        )
        return CommandParser(_parser=subparser)

    def parse(self, args: tuple[str, ...] | list[str]) -> argparse.Namespace:
        try:
            parsed, unknown = self.parser.parse_known_args(args)
            if unknown:
                raise CommandArgumentError(f"Неизвестные аргументы: {' '.join(unknown)}")
            return parsed
        except argparse.ArgumentError as e:
            raise CommandArgumentError(str(e))
        except SystemExit:
            raise CommandArgumentError(self.parser.format_help())

    def help(self) -> str:
        return self.parser.format_help()