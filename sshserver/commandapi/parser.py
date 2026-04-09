from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple


from .exceptions import CommandArgumentError


# ============================================================
# Exceptions
# ============================================================

class HelpRequested(Exception):
    """Internal signal for help display."""


# ============================================================
# Namespace
# ============================================================

class Namespace:
    """Simple argparse-like namespace."""

    def __init__(self, **kwargs: Any) -> None:
        self.__dict__.update(kwargs)

    def __repr__(self) -> str:
        items = sorted(self.__dict__.items())
        if not items:
            return "Namespace()"
        return "Namespace(" + ", ".join(f"{k}={v!r}" for k, v in items) + ")"


# ============================================================
# Argument model
# ============================================================

@dataclass
class Argument:
    names: List[str]
    dest: str
    positional: bool = False
    action: str = "store"     # store, store_true, append, count
    nargs: Optional[str] = None   # None, ?, *, +
    default: Any = None
    required: bool = False
    arg_type: Optional[Callable[[str], Any]] = None
    choices: Optional[Sequence[Any]] = None
    help: str = ""
    metavar: Optional[str] = None

    @property
    def long_names(self) -> List[str]:
        return [n for n in self.names if n.startswith("--")]

    @property
    def short_names(self) -> List[str]:
        return [n for n in self.names if n.startswith("-") and not n.startswith("--")]

    @property
    def display_name(self) -> str:
        if self.positional:
            return self.metavar or self.dest
        return ", ".join(self.names)

    @property
    def takes_value(self) -> bool:
        return self.action in ("store", "append")

    @property
    def usage_fragment(self) -> str:
        if self.positional:
            name = self.metavar or self.dest
            if self.nargs == "?":
                return f"[{name}]"
            if self.nargs == "*":
                return f"[{name} ...]"
            if self.nargs == "+":
                return f"{name} [{name} ...]"
            return name

        label = self.names[-1] if self.long_names else self.names[0]
        value_name = self.metavar or self.dest.upper()

        if self.action in ("store_true", "count"):
            return f"[{label}]"

        if self.nargs == "?":
            return f"[{label} [{value_name}]]"
        if self.nargs in ("*", "+"):
            return f"[{label} {value_name} ...]"
        return f"[{label} {value_name}]"


# ============================================================
# Subparsers
# ============================================================

class SubParsersAction:
    def __init__(self, parent: "ArgumentParser", dest: str = "command", required: bool = False) -> None:
        self._parent = parent
        self.dest = dest
        self.required = required

    def add_parser(
        self,
        name: str,
        *,
        help: str = "",
        description: str = "",
    ) -> "ArgumentParser":
        parser = ArgumentParser(
            prog=f"{self._parent.prog} {name}",
            description=description,
            parent=self._parent,
        )
        parser._subcommand_help = help
        self._parent._subparsers[name] = parser
        self._parent._subparsers_dest = self.dest
        self._parent._subparsers_required = self.required
        return parser


# ============================================================
# Parser
# ============================================================

class ArgumentParser:
    def __init__(
        self,
        prog: Optional[str] = None,
        description: str = "",
        parent: Optional["ArgumentParser"] = None,
        add_help: bool = True,
    ) -> None:
        self.prog = prog or "command"
        self.description = description
        self._parent = parent

        self._arguments: List[Argument] = []
        self._positionals: List[Argument] = []
        self._optionals: List[Argument] = []

        self._long_map: Dict[str, Argument] = {}
        self._short_map: Dict[str, Argument] = {}

        self._subparsers: Dict[str, ArgumentParser] = {}
        self._subparsers_dest: str = "command"
        self._subparsers_required: bool = False
        self._subcommand_help: str = ""

        if add_help:
            self.add_argument("-h", "--help", action="store_true", help="show this help message and exit")

    # --------------------------------------------------------
    # Public API
    # --------------------------------------------------------

    def add_argument(
        self,
        *names: str,
        action: str = "store",
        nargs: Optional[str] = None,
        default: Any = None,
        type: Optional[Callable[[str], Any]] = None,
        required: bool = False,
        choices: Optional[Sequence[Any]] = None,
        help: str = "",
        metavar: Optional[str] = None,
        dest: Optional[str] = None,
    ) -> Argument:
        if not names:
            raise ValueError("at least one argument name is required")

        positional = not names[0].startswith("-")

        self._validate_action(action)
        self._validate_nargs(nargs, action)

        if positional:
            if len(names) != 1:
                raise CommandArgumentError("positional argument can only have one name")

            name = names[0]
            dest = dest or name

            arg = Argument(
                names=[name],
                dest=dest,
                positional=True,
                action="store",
                nargs=nargs,
                default=default,
                required=(nargs not in ("?", "*")),
                arg_type=type,
                choices=choices,
                help=help,
                metavar=metavar,
            )
            self._positionals.append(arg)
            self._arguments.append(arg)
            return arg

        # optional
        parsed_names = list(names)
        for name in parsed_names:
            if not self._is_valid_optional_name(name):
                raise CommandArgumentError(f"invalid option name: {name}")

        if dest is None:
            long_name = next((n for n in parsed_names if n.startswith("--")), None)
            if long_name:
                dest = long_name[2:].replace("-", "_")
            else:
                dest = parsed_names[0][1:]

        if action == "store_true":
            default = False if default is None else default
        elif action == "count":
            default = 0 if default is None else default
        elif action == "append":
            default = [] if default is None else default

        arg = Argument(
            names=parsed_names,
            dest=dest,
            positional=False,
            action=action,
            nargs=nargs,
            default=default,
            required=required,
            arg_type=type,
            choices=choices,
            help=help,
            metavar=metavar,
        )

        self._optionals.append(arg)
        self._arguments.append(arg)

        for name in parsed_names:
            if name.startswith("--"):
                self._long_map[name[2:]] = arg
            else:
                self._short_map[name[1:]] = arg

        return arg

    def add_subparsers(self, *, dest: str = "command", required: bool = False) -> SubParsersAction:
        return SubParsersAction(self, dest=dest, required=required)

    def parse_args(self, args: Optional[Sequence[str]] = None) -> Namespace:
        namespace, unknown = self.parse_known_args(args)
        if unknown:
            raise CommandArgumentError(f"unrecognized arguments: {' '.join(unknown)}")
        return namespace

    def parse_known_args(self, args: Optional[Sequence[str]] = None) -> Tuple[Namespace, List[str]]:
        if args is None:
            args = sys.argv[1:]

        tokens = list(args)
        result = Namespace()
        unknown: List[str] = []

        self._apply_defaults(result)

        i = 0
        positional_idx = 0

        while i < len(tokens):
            token = tokens[i]

            if token in ("-h", "--help"):
                raise CommandArgumentError(self.format_help())

            if token == "--":
                i += 1
                while i < len(tokens):
                    positional_idx = self._consume_positional(result, tokens[i], positional_idx)
                    i += 1
                break

            # subcommands
            if token in self._subparsers:
                setattr(result, self._subparsers_dest, token)
                subparser = self._subparsers[token]
                sub_ns, sub_unknown = subparser.parse_known_args(tokens[i + 1:])
                for key, value in sub_ns.__dict__.items():
                    setattr(result, key, value)
                unknown.extend(sub_unknown)
                self._validate_required(result)
                return result, unknown

            # long option
            if token.startswith("--") and len(token) > 2:
                consumed = self._try_parse_long_option(tokens, i, result)
                if consumed is None:
                    unknown.append(token)
                    i += 1
                else:
                    i = consumed
                continue

            # short option(s)
            if token.startswith("-") and len(token) > 1:
                consumed = self._try_parse_short_options(tokens, i, result)
                if consumed is None:
                    unknown.append(token)
                    i += 1
                else:
                    i = consumed
                continue

            # positional
            try:
                positional_idx = self._consume_positional(result, token, positional_idx)
            except CommandArgumentError:
                unknown.append(token)
            i += 1

        self._validate_required(result)
        return result, unknown

    def format_help(self) -> str:
        lines: List[str] = []

        usage_parts = [self.prog]

        for opt in self._optionals:
            if opt.dest == "help":
                continue
            usage_parts.append(opt.usage_fragment)

        for pos in self._positionals:
            usage_parts.append(pos.usage_fragment)

        if self._subparsers:
            if self._subparsers_required:
                usage_parts.append("<subcommand>")
            else:
                usage_parts.append("[<subcommand>]")

        lines.append("usage: " + " ".join(usage_parts))

        if self.description:
            lines.append("")
            lines.append(self.description)

        if self._positionals:
            lines.append("")
            lines.append("positional arguments:")
            for arg in self._positionals:
                lines.append(f"  {arg.display_name:<24} {self._build_help_text(arg)}")

        if self._optionals:
            lines.append("")
            lines.append("options:")
            for arg in self._optionals:
                lines.append(f"  {arg.display_name:<24} {self._build_help_text(arg)}")

        if self._subparsers:
            lines.append("")
            lines.append("subcommands:")
            for name, parser in self._subparsers.items():
                lines.append(f"  {name:<24} {parser._subcommand_help}")

        return "\n".join(lines)

    def print_help(self) -> None:
        print(self.format_help())

    # --------------------------------------------------------
    # Internal helpers
    # --------------------------------------------------------

    def _apply_defaults(self, result: Namespace) -> None:
        for arg in self._arguments:
            if arg.action == "append":
                setattr(result, arg.dest, list(arg.default))
            elif arg.nargs == "*":
                if arg.default is None:
                    setattr(result, arg.dest, [])
                else:
                    setattr(result, arg.dest, list(arg.default))
            else:
                setattr(result, arg.dest, arg.default)

    def _try_parse_long_option(self, tokens: List[str], i: int, result: Namespace) -> Optional[int]:
        raw = tokens[i][2:]

        if "=" in raw:
            key, inline_value = raw.split("=", 1)
        else:
            key, inline_value = raw, None

        arg = self._long_map.get(key)
        if arg is None:
            return None

        if arg.action == "store_true":
            if inline_value is not None:
                raise CommandArgumentError(f"flag '--{key}' does not take a value")
            setattr(result, arg.dest, True)
            return i + 1

        if arg.action == "count":
            current = getattr(result, arg.dest, 0)
            setattr(result, arg.dest, current + 1)
            return i + 1

        if arg.nargs in ("*", "+"):
            values: List[str] = []
            if inline_value is not None:
                values.append(inline_value)

            j = i + 1
            while j < len(tokens) and not self._looks_like_option(tokens[j]):
                values.append(tokens[j])
                j += 1

            if arg.nargs == "+" and not values:
                raise CommandArgumentError(f"option '--{key}' requires at least one value")

            converted = [self._convert_value(arg, v) for v in values]
            self._store_value(result, arg, converted)
            return j

        if inline_value is None:
            i += 1
            if i >= len(tokens):
                if arg.nargs == "?":
                    self._store_value(result, arg, None)
                    return i
                raise CommandArgumentError(f"option '--{key}' requires a value")
            inline_value = tokens[i]

        value = self._convert_value(arg, inline_value) if inline_value is not None else None
        self._store_value(result, arg, value)
        return i + 1

    def _try_parse_short_options(self, tokens: List[str], i: int, result: Namespace) -> Optional[int]:
        cluster = tokens[i][1:]
        j = 0

        while j < len(cluster):
            short = cluster[j]
            arg = self._short_map.get(short)
            if arg is None:
                return None

            if arg.action == "store_true":
                setattr(result, arg.dest, True)
                j += 1
                continue

            if arg.action == "count":
                current = getattr(result, arg.dest, 0)
                setattr(result, arg.dest, current + 1)
                j += 1
                continue

            # option with value
            attached = cluster[j + 1:]

            if arg.nargs in ("*", "+"):
                values: List[str] = []
                if attached:
                    values.append(attached)

                k = i + 1
                while k < len(tokens) and not self._looks_like_option(tokens[k]):
                    values.append(tokens[k])
                    k += 1

                if arg.nargs == "+" and not values:
                    raise CommandArgumentError(f"option '-{short}' requires at least one value")

                converted = [self._convert_value(arg, v) for v in values]
                self._store_value(result, arg, converted)
                return k

            if attached:
                value = self._convert_value(arg, attached)
                self._store_value(result, arg, value)
                return i + 1

            i += 1
            if i >= len(tokens):
                if arg.nargs == "?":
                    self._store_value(result, arg, None)
                    return i
                raise CommandArgumentError(f"option '-{short}' requires a value")

            value = self._convert_value(arg, tokens[i])
            self._store_value(result, arg, value)
            return i + 1

        return i + 1

    def _consume_positional(self, result: Namespace, token: str, positional_idx: int) -> int:
        if positional_idx >= len(self._positionals):
            raise CommandArgumentError(f"extra positional argument: {token}")

        arg = self._positionals[positional_idx]

        if arg.nargs == "*":
            current = getattr(result, arg.dest, [])
            current.append(self._convert_value(arg, token))
            setattr(result, arg.dest, current)
            return positional_idx

        if arg.nargs == "+":
            current = getattr(result, arg.dest, None)
            if current is None:
                current = []
            current.append(self._convert_value(arg, token))
            setattr(result, arg.dest, current)
            return positional_idx

        value = self._convert_value(arg, token)
        self._store_value(result, arg, value)
        return positional_idx + 1

    def _store_value(self, result: Namespace, arg: Argument, value: Any) -> None:
        if arg.action == "append":
            current = getattr(result, arg.dest, None)
            if current is None:
                current = []
            current.append(value)
            setattr(result, arg.dest, current)
            return

        setattr(result, arg.dest, value)

    def _convert_value(self, arg: Argument, raw: str) -> Any:
        value: Any = raw

        if arg.arg_type is not None:
            try:
                value = arg.arg_type(raw)
            except (TypeError, ValueError) as e:
                raise CommandArgumentError(
                    f"invalid value for '{arg.dest}': {raw!r}"
                ) from e

        if arg.choices is not None and value not in arg.choices:
            raise CommandArgumentError(
                f"invalid choice for '{arg.dest}': {value!r} "
                f"(choose from {', '.join(map(repr, arg.choices))})"
            )

        return value

    def _validate_required(self, result: Namespace) -> None:
        for arg in self._optionals:
            if arg.dest == "help":
                continue

            value = getattr(result, arg.dest, None)

            if arg.required:
                if arg.action == "store_true" and value is False:
                    raise CommandArgumentError(f"missing required argument: {arg.display_name}")
                if value is None:
                    raise CommandArgumentError(f"missing required argument: {arg.display_name}")
                if arg.action == "append" and not value:
                    raise CommandArgumentError(f"missing required argument: {arg.display_name}")

        for arg in self._positionals:
            value = getattr(result, arg.dest, None)

            if arg.nargs == "*":
                continue
            if arg.nargs == "?":
                continue
            if arg.nargs == "+":
                if not value:
                    raise CommandArgumentError(f"missing positional argument: {arg.dest}")
                continue
            if value is None:
                raise CommandArgumentError(f"missing positional argument: {arg.dest}")

        if self._subparsers and self._subparsers_required:
            if not hasattr(result, self._subparsers_dest):
                raise CommandArgumentError("missing required subcommand")

    def _build_help_text(self, arg: Argument) -> str:
        text = arg.help or ""
        meta: List[str] = []

        if arg.required and not arg.positional:
            meta.append("required")
        if arg.default not in (None, False, [], 0):
            meta.append(f"default: {arg.default}")
        if arg.choices:
            meta.append("choices: " + ", ".join(map(str, arg.choices)))

        if meta:
            if text:
                text += " "
            text += f"({' ; '.join(meta)})"

        return text

    @staticmethod
    def _is_valid_optional_name(name: str) -> bool:
        if name.startswith("--") and len(name) > 2:
            return True
        if name.startswith("-") and len(name) == 2:
            return True
        return False

    @staticmethod
    def _looks_like_option(token: str) -> bool:
        return token.startswith("-") and token != "-"

    @staticmethod
    def _validate_action(action: str) -> None:
        allowed = {"store", "store_true", "append", "count"}
        if action not in allowed:
            raise CommandArgumentError(f"unsupported action: {action}")

    @staticmethod
    def _validate_nargs(nargs: Optional[str], action: str) -> None:
        allowed = {None, "?", "*", "+"}
        if nargs not in allowed:
            raise CommandArgumentError(f"unsupported nargs: {nargs}")

        if action in ("store_true", "count") and nargs is not None:
            raise CommandArgumentError(f"action '{action}' does not support nargs")