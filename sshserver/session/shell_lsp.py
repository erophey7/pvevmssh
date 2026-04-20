import logging
import shlex

logger = logging.getLogger(__name__)

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from sshserver.dispatcher import CommandDispatcher
    from sshserver.lsp_engine import LSPEngine

from sshserver.terminal.line_editor.text_utils import split_graphemes


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
    # SEMANTIC TOKENS 
    # ==========================================
    def semantic_tokens(self, text: str) -> dict:
        if not text:
            return {"styles": []}

        graphemes = split_graphemes(text)
        n = len(graphemes)
        styles = ["SYNTAX_DEFAULT"] * n

        try:
            tokens = shlex.split(text, posix=True)
        except Exception:
            return {"styles": ["SYNTAX_WARNING"] * n}

        if not tokens:
            return {"styles": styles}

        parser = self.dispatcher.get_command_parser(tokens[0])

        gi = 0
        expect_command = True
        expecting_value_for = None

        def write(start, end, style):
            for i in range(start, min(end, n)):
                styles[i] = style

        for ti, token in enumerate(tokens):
            # skip spaces
            while gi < n and graphemes[gi].isspace():
                gi += 1

            start = gi
            buf = ""

            while gi < n and len(buf) < len(token):
                buf += graphemes[gi]
                gi += 1

            end = gi

            # =========================
            # COMMAND
            # =========================
            if expect_command:
                expect_command = False

                if ti == 0:
                    if not parser:
                        write(start, end, "SYNTAX_ERROR")
                    else:
                        write(start, end, "SYNTAX_COMMAND")
                else:
                    # subcommand check
                    if parser and parser._subparsers:
                        if token in parser._subparsers:
                            write(start, end, "SYNTAX_SUBCOMMAND")
                            parser = parser._subparsers[token]
                        else:
                            write(start, end, "SYNTAX_ERROR")
                    else:
                        write(start, end, "SYNTAX_ERROR")

                continue

            # =========================
            # FLAG
            # =========================
            if token.startswith("-"):
                arg = None
                if parser:
                    if token.startswith("--"):
                        arg = parser._long_map.get(token[2:])
                    else:
                        arg = parser._short_map.get(token[1:])

                if arg:
                    write(start, end, "SYNTAX_FLAG")
                    if getattr(arg, "takes_value", False):
                        expecting_value_for = arg
                else:
                    write(start, end, "SYNTAX_ERROR")

                continue

            # =========================
            # VALUE
            # =========================
            if expecting_value_for:
                write(start, end, "SYNTAX_OPTION")
                expecting_value_for = None
                continue

            # =========================
            # fallback
            # =========================
            write(start, end, "SYNTAX_DEFAULT")

        # =========================
        # WARNING: unclosed quote
        # =========================
        if text.count('"') % 2 != 0 or text.count("'") % 2 != 0:
            styles[-1] = "SYNTAX_WARNING"

        return {"styles": styles}