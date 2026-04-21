import logging
import shlex

logger = logging.getLogger(__name__)

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from sshserver.dispatcher import CommandDispatcher
    from sshserver.lsp_engine import LSPEngine

from helpers.text_utils.char_tools import split_graphemes
from sshserver.terminal.line_editor.types import SyntaxToken

class ShellLSP:
    def __init__(self, dispatcher: CommandDispatcher):
        self.dispatcher = dispatcher

    async def __call__(self, ctx):
        parser = self.dispatcher.get_command_parser(ctx.command)
        if not parser:
            return []
        return self._complete(parser, ctx)

    # ==========================================
    # registration
    # ==========================================
    def register(self, engine: LSPEngine):
        self.engine = engine
        for name in self.dispatcher.commands.keys():
            engine.register_command(name)
        engine.register_dynamic_provider(self.complete)
        engine.register_semantic_provider(self.semantic_tokens)

    # ==========================================
    # core completion
    # ==========================================
    async def complete(self, partial: str, previous_tokens: list[str]):
        try:
            if not previous_tokens:
                return []
            cmd_name = previous_tokens[0]
            parser = self.dispatcher.get_command_parser(cmd_name)
            if not parser:
                return []
            return self._complete_with_parser(parser, previous_tokens[1:], partial)
        except Exception:
            logger.exception("ShellLSP completion failed")
            return []

    # ==========================================
    # parser → completion
    # ==========================================
    def _complete_with_parser(self, parser, arg_tokens: list[str], partial: str):
        # 1. SUBCOMMANDS
        if parser._subparsers:
            if not arg_tokens:
                return [
                    name for name in parser._subparsers.keys()
                    if name.startswith(partial)
                ]
            subcmd = arg_tokens[0]
            subparser = parser._subparsers.get(subcmd)
            if subparser:
                return self._complete_with_parser(subparser, arg_tokens[1:], partial)

        # 2. VALUE CONTEXT
        def get_arg(tok: str):
            if tok.startswith("--"):
                return parser._long_map.get(tok[2:])
            if tok.startswith("-") and len(tok) > 1:
                return parser._short_map.get(tok[1:])
            return None

        expecting = None
        if arg_tokens:
            last_token = arg_tokens[-1]
            arg = get_arg(last_token)
            if arg and arg.takes_value:
                expecting = arg

        if expecting:
            choices = expecting.choices or []
            return [
                str(c) for c in choices
                if str(c).startswith(partial)
            ]

        # 3. OPTIONS (флаги)
        results: list[str] = []
        for arg in parser._optionals:
            if partial.startswith("--"):
                names = arg.long_names
            elif partial.startswith("-"):
                names = arg.short_names
            else:
                names = arg.names
            for name in names:
                if name.startswith(partial):
                    results.append(name)

        # 4. POSITIONALS
        for arg in parser._positionals:
            if arg.choices:
                for c in arg.choices:
                    c_str = str(c)
                    if c_str.startswith(partial):
                        results.append(c_str)

        return sorted(set(results))

    # ==========================================
    # SEMANTIC TOKENS (SPAN-BASED)
    # ==========================================
    def semantic_tokens(self, text: str) -> dict:
        if not text:
            return {"tokens": []}

        graphemes = split_graphemes(text)
        n = len(graphemes)
        if n == 0:
            return {"tokens": []}

        def find_unclosed_quote(text: str):
            stack = []
            for i, ch in enumerate(text):
                if ch in ("'", '"'):
                    if stack and stack[-1][0] == ch:
                        stack.pop()
                    else:
                        stack.append((ch, i))
            return stack[-1][1] if stack else None

        try:
            tokens = shlex.split(text, posix=True)
        except Exception:
            quote_pos = find_unclosed_quote(text)
            if quote_pos is not None:
                return {
                    "tokens": [
                        SyntaxToken(quote_pos, n - quote_pos, "SYNTAX_WARNING")
                    ]
                }
            return {"tokens": []}

        if not tokens:
            return {"tokens": []}

        cmd_name = tokens[0]
        parser = self.dispatcher.get_command_parser(cmd_name)

        semantic_tokens: list[SyntaxToken] = []
        gi = 0

        used_optionals = set()
        positional_index = 0
        expecting_value_for = None

        def add_token(start: int, length: int, style: str):
            if length > 0:
                semantic_tokens.append(SyntaxToken(start, length, style))

        def next_grapheme_span(token: str):
            nonlocal gi
            while gi < n and graphemes[gi].isspace():
                gi += 1
            start = gi
            buf = ""
            while gi < n and len(buf) < len(token):
                buf += graphemes[gi]
                gi += 1
            return start, gi - start

        # ==========================================
        # COMMAND (учёт команд без parser)
        # ==========================================
        if cmd_name in self.dispatcher.commands:
            cmd_style = "SYNTAX_COMMAND"
        else:
            cmd_style = "SYNTAX_ERROR"

        # если команда существует, но без parser → fallback
        if cmd_style == "SYNTAX_COMMAND" and not parser:
            for ti, token in enumerate(tokens):
                start, length = next_grapheme_span(token)
                if ti == 0:
                    add_token(start, length, "SYNTAX_COMMAND")
                else:
                    add_token(start, length, "SYNTAX_DEFAULT")
            return {"tokens": semantic_tokens}

        # ==========================================
        # MAIN LOOP
        # ==========================================
        for ti, token in enumerate(tokens):
            start, length = next_grapheme_span(token)

            # COMMAND
            if ti == 0:
                add_token(start, length, cmd_style)
                continue

            # SUBCOMMAND
            if parser and parser._subparsers:
                if token in parser._subparsers:
                    parser = parser._subparsers[token]
                    positional_index = 0
                    add_token(start, length, "SYNTAX_SUBCOMMAND")
                    continue
                elif ti == 1:
                    add_token(start, length, "SYNTAX_ERROR")
                    continue

            # VALUE (ожидаем значение)
            if expecting_value_for:
                valid = True
                if expecting_value_for.choices:
                    valid = token in map(str, expecting_value_for.choices)

                style = "SYNTAX_OPTION" if valid else "SYNTAX_ERROR"
                add_token(start, length, style)
                expecting_value_for = None
                continue

            # FLAG
            if token.startswith("-"):
                arg = None
                if parser:
                    if token.startswith("--"):
                        arg = parser._long_map.get(token[2:])
                    else:
                        arg = parser._short_map.get(token[1:])

                if not arg:
                    add_token(start, length, "SYNTAX_ERROR")
                    continue

                # проверка на повтор (если хочешь строгость)
                if not getattr(arg, "repeatable", True) and arg in used_optionals:
                    add_token(start, length, "SYNTAX_ERROR")
                    continue

                used_optionals.add(arg)

                add_token(start, length, "SYNTAX_FLAG")

                if getattr(arg, "takes_value", False):
                    expecting_value_for = arg

                continue

            # POSITIONAL
            if parser and positional_index < len(parser._positionals):
                arg = parser._positionals[positional_index]

                valid = True
                if arg.choices:
                    valid = token in map(str, arg.choices)

                style = "SYNTAX_POSITIONAL" if valid else "SYNTAX_ERROR"
                add_token(start, length, style)

                positional_index += 1
                continue

            # UNKNOWN
            add_token(start, length, "SYNTAX_ERROR")

        # ==========================================
        # WARNING: unclosed quotes (точечно)
        # ==========================================
        quote_pos = find_unclosed_quote(text)
        if quote_pos is not None:
            semantic_tokens.append(
                SyntaxToken(quote_pos, n - quote_pos, "SYNTAX_WARNING")
            )

        return {"tokens": semantic_tokens}