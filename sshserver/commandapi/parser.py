from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple, Union

from .exceptions import CommandArgumentError


class Namespace:
    """Simple namespace object for storing parsed arguments."""

    def __init__(self, **kwargs: Any) -> None:
        self.__dict__.update(kwargs)

    def __repr__(self) -> str:
        items = sorted(self.__dict__.items())
        if not items:
            return "Namespace()"
        return "Namespace(" + ", ".join(f"{k}={v!r}" for k, v in items) + ")"


class CommandParser:
    """
    Own simple and extensible argument parser.
    Supports flags, named options, positional arguments, subcommands,
    short and long flags/options, and grouped short flags.
    """

    def __init__(self, prog: str | None = None, parent: Optional[CommandParser] = None) -> None:
        self.prog = prog or "command"
        self.description: str = ""
        self._parent = parent               # for subcommand nesting
        self._flags: Dict[str, Dict[str, str]] = {}      # long_name -> {'short': short, 'help': help}
        self._options: Dict[str, Dict[str, Any]] = {}    # long_name -> {'short': short, 'default': default, 'help': help}
        self._positional: List[Dict[str, str]] = []      # [{'name': name, 'help': help}]
        self._subcommands: Dict[str, CommandParser] = {} # name -> CommandParser
        self._short_to_long_flag: Dict[str, str] = {}    # short -> long
        self._short_to_long_opt: Dict[str, str] = {}     # short -> long

    def add_flag(self, *names: str, help: str = "") -> CommandParser:
        """Add a flag. Example: add_flag('-v', '--verbose')"""
        if not names:
            raise ValueError("at least one flag name required")
        long_name = None
        short_name = None
        for name in names:
            if name.startswith('--'):
                if long_name is not None:
                    raise CommandArgumentError("multiple long names not allowed")
                long_name = name[2:]
            elif name.startswith('-') and len(name) == 2:
                if short_name is not None:
                    raise CommandArgumentError("multiple short names not allowed")
                short_name = name[1:]
            else:
                raise CommandArgumentError(f"invalid flag name: {name}")
        if not long_name:
            # if only short given, we need a canonical long name (use short as long)
            long_name = short_name
        # store
        self._flags[long_name] = {'short': short_name, 'help': help}
        if short_name:
            self._short_to_long_flag[short_name] = long_name
        return self

    def add_option(self, *names: str, default: Any = None, help: str = "") -> CommandParser:
        """Add an option with a value. Example: add_option('-c', '--count', default=5)"""
        if not names:
            raise ValueError("at least one option name required")
        long_name = None
        short_name = None
        for name in names:
            if name.startswith('--'):
                if long_name is not None:
                    raise CommandArgumentError("multiple long names not allowed")
                long_name = name[2:]
            elif name.startswith('-') and len(name) == 2:
                if short_name is not None:
                    raise CommandArgumentError("multiple short names not allowed")
                short_name = name[1:]
            else:
                raise CommandArgumentError(f"invalid option name: {name}")
        if not long_name:
            long_name = short_name
        self._options[long_name] = {'short': short_name, 'default': default, 'help': help}
        if short_name:
            self._short_to_long_opt[short_name] = long_name
        return self

    def add_positional(self, name: str, help: str = "") -> CommandParser:
        """Add a positional argument."""
        self._positional.append({'name': name, 'help': help})
        return self

    def add_subcommand(self, name: str, help: str = "") -> CommandParser:
        """Add a subcommand and return its parser."""
        subparser = CommandParser(prog=f"{self.prog} {name}", parent=self)
        self._subcommands[name] = subparser
        # We'll handle help in help() method
        return subparser

    def parse(self, args: Optional[Union[Tuple[str, ...], List[str]]] = None) -> Namespace:
        """
        Parse arguments and return a Namespace object.
        If args is None, sys.argv[1:] is used.
        """
        if args is None:
            import sys
            args = sys.argv[1:]
        args = list(args)

        result = Namespace()
        # global defaults
        for long_name, opt in self._options.items():
            setattr(result, long_name, opt['default'])
        for long_name in self._flags:
            setattr(result, long_name, False)

        i = 0
        positional_idx = 0
        subcommand_used = None

        while i < len(args):
            arg = args[i]

            # Stop parsing after '--'
            if arg == '--':
                i += 1
                # treat remaining as positional
                while i < len(args):
                    if positional_idx < len(self._positional):
                        setattr(result, self._positional[positional_idx]['name'], args[i])
                        positional_idx += 1
                    else:
                        raise CommandArgumentError(f"extra positional argument: {args[i]}")
                    i += 1
                break

            # Long option or flag
            if arg.startswith('--'):
                # --option value
                key = arg[2:]
                if key in self._options:
                    i += 1
                    if i < len(args):
                        setattr(result, key, args[i])
                    else:
                        raise CommandArgumentError(f"option '{arg}' requires a value")
                elif key in self._flags:
                    setattr(result, key, True)
                else:
                    raise CommandArgumentError(f"unknown option: {arg}")
                i += 1
                continue

            # Short flags/options (starting with '-', not '--')
            if arg.startswith('-') and len(arg) > 1:
                # Check for combined short flags like -abc
                # We'll parse from left to right, if we encounter an option that expects a value,
                # the rest of the string is the value.
                j = 1
                while j < len(arg):
                    short = arg[j]
                    # Check if this short is an option (expects value)
                    if short in self._short_to_long_opt:
                        # It's an option
                        long_name = self._short_to_long_opt[short]
                        # The value may be attached after the flag (e.g., -c5)
                        value_part = arg[j+1:]
                        if value_part:
                            # value is in the same token
                            setattr(result, long_name, value_part)
                            j = len(arg)  # consume all
                        else:
                            # value is in next token
                            i += 1
                            if i < len(args):
                                setattr(result, long_name, args[i])
                            else:
                                raise CommandArgumentError(f"option '-{short}' requires a value")
                        break  # after an option we stop processing this token (remaining chars are its value)
                    elif short in self._short_to_long_flag:
                        # It's a flag
                        long_name = self._short_to_long_flag[short]
                        setattr(result, long_name, True)
                        j += 1
                    else:
                        raise CommandArgumentError(f"unknown short flag/option: -{short}")
                i += 1
                continue

            # Subcommand detection
            if not subcommand_used and arg in self._subcommands:
                subcommand_used = arg
                setattr(result, 'subcommand', arg)
                # parse remaining arguments with subcommand's parser
                subparser = self._subcommands[arg]
                sub_args = args[i+1:]
                sub_result = subparser.parse(sub_args)
                # Merge sub_result into main result (all attributes are top-level)
                for key, value in sub_result.__dict__.items():
                    setattr(result, key, value)
                break  # subcommand consumes all remaining args

            # Positional argument
            if positional_idx < len(self._positional):
                setattr(result, self._positional[positional_idx]['name'], arg)
                positional_idx += 1
            else:
                raise CommandArgumentError(f"extra positional argument: {arg}")
            i += 1

        # Check required positional arguments
        for pos in self._positional:
            if not hasattr(result, pos['name']):
                raise CommandArgumentError(f"missing positional argument: {pos['name']}")

        return result

    def help(self) -> str:
        """Return help string."""
        lines = [f"Usage: {self.prog} [options]"]
        if self.description:
            lines.append(self.description)

        if self._flags:
            lines.append("\nFlags:")
            for long_name, info in self._flags.items():
                short = info['short']
                help_text = info['help']
                if short:
                    lines.append(f"  -{short}, --{long_name}  {help_text}")
                else:
                    lines.append(f"  --{long_name}  {help_text}")

        if self._options:
            lines.append("\nOptions:")
            for long_name, info in self._options.items():
                short = info['short']
                default = info['default']
                help_text = info['help']
                if short:
                    lines.append(f"  -{short}, --{long_name}={default}  {help_text} (default: {default})")
                else:
                    lines.append(f"  --{long_name}={default}  {help_text} (default: {default})")

        if self._positional:
            lines.append("\nPositional arguments:")
            for pos in self._positional:
                lines.append(f"  {pos['name']}  {pos['help']}")

        if self._subcommands:
            lines.append("\nSubcommands:")
            for name, subparser in self._subcommands.items():
                # TODO: store help for subcommand
                lines.append(f"  {name}")

        return "\n".join(lines)