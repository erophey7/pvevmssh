import logging
logger = logging.getLogger(__name__)
from helpers.text_utils.lexer import (
    lex,
    LexToken,
    TK_BOOL,
    TK_COMMAND,
    TK_COMMENT,
    TK_ENV,
    TK_FLAG,
    TK_KEY,
    TK_NULL,
    TK_NUMBER,
    TK_OPERATOR,
    TK_PATH,
    TK_STRING,
    TK_STRING_UNCLOSED,
    TK_VALUE,
    TK_WORD,
    TK_WS
)
from helpers.lsp.json_rpc_proto import SemanticToken, SemanticTokens

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from sshserver.dispatcher import CommandDispatcher
    from sshserver.lsp_engine import LSPEngine

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

        tokens = lex(text)
        semantic_tokens: SemanticTokens = []

        parser = None
        used_optionals = set()
        positional_index = 0
        expecting_value_for = None

        # ==========================
        # helpers
        # ==========================
        def add(tok: LexToken, style: str):
            semantic_tokens.append(
                SemanticToken(tok.start, tok.length, style)
            )

        # ==========================
        # find command
        # ==========================
        cmd_token = None
        for t in tokens:
            if t.kind == TK_COMMAND:
                cmd_token = t
                break

        if not cmd_token:
            return {"tokens": []}

        cmd_name = cmd_token.text
        parser = self.dispatcher.get_command_parser(cmd_name)

        cmd_style = (
            "SYNTAX_COMMAND"
            if cmd_name in self.dispatcher.commands
            else "SYNTAX_ERROR"
        )

        # ==========================
        # fallback: no parser
        # ==========================
        if cmd_style == "SYNTAX_COMMAND" and not parser:
            for i, t in enumerate(tokens):
                if t.kind == TK_COMMAND:
                    add(t, "SYNTAX_COMMAND")
                elif t.kind == TK_STRING:
                    add(t, "SYNTAX_STRING")
                else:
                    add(t, "SYNTAX_DEFAULT")

            return {"tokens": semantic_tokens}

        # ==========================
        # MAIN LOOP
        # ==========================
        for i, t in enumerate(tokens):

            # COMMAND
            if t.kind == TK_COMMAND:
                add(t, cmd_style)
                continue

            # WHITESPACE / COMMENT ignore
            if t.kind in (TK_WS, TK_COMMENT):
                continue

            # STRING
            if t.kind == TK_STRING:
                if t.kind == TK_STRING:
                    add(t, "SYNTAX_STRING")
                continue

            # STRING UNCLOSED
            if t.kind == TK_STRING_UNCLOSED:
                add(t, "SYNTAX_WARNING")
                continue

            # FLAG
            if t.kind == TK_FLAG:
                arg = None

                if parser:
                    if t.text.startswith("--"):
                        arg = parser._long_map.get(t.text[2:])
                    else:
                        arg = parser._short_map.get(t.text[1:])

                if not arg:
                    add(t, "SYNTAX_ERROR")
                    continue

                if not getattr(arg, "repeatable", True) and id(arg) in used_optionals:
                    add(t, "SYNTAX_ERROR")
                    continue

                used_optionals.add(id(arg))
                add(t, "SYNTAX_FLAG")

                if getattr(arg, "takes_value", False):
                    expecting_value_for = arg

                continue

            # VALUE / KEY / WORD
            if expecting_value_for:
                valid = True
                if expecting_value_for.choices:
                    valid = t.text in map(str, expecting_value_for.choices)

                add(t, "SYNTAX_OPTION" if valid else "SYNTAX_ERROR")
                expecting_value_for = None
                continue

            # KEY=VALUE
            if t.kind == TK_KEY:
                add(t, "SYNTAX_KEY")
                continue

            if t.kind == TK_OPERATOR:
                add(t, "SYNTAX_OPERATOR")
                continue

            # SUBCOMMAND
            if parser and parser._subparsers and t.text in parser._subparsers:
                parser = parser._subparsers[t.text]
                positional_index = 0
                add(t, "SYNTAX_SUBCOMMAND")
                continue

            # POSITIONAL
            if parser and positional_index < len(parser._positionals):
                arg = parser._positionals[positional_index]

                valid = True
                if arg.choices:
                    valid = t.text in map(str, arg.choices)

                add(t, "SYNTAX_POSITIONAL" if valid else "SYNTAX_ERROR")

                positional_index += 1
                continue

            # DEFAULT
            add(t, "SYNTAX_ERROR")

        return {"tokens": semantic_tokens}