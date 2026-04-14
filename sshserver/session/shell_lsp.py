import shlex
import logging

logger = logging.getLogger(__name__)


class ShellLSP:
    def __init__(self, dispatcher):
        self.dispatcher = dispatcher

    async def __call__(self, ctx):
        parser = self.dispatcher.get_command_parser(ctx.command)
        if not parser:
            return []

        return self._complete(parser, ctx)

    # ==========================================
    # registration
    # ==========================================
    def register(self, engine):
        self.engine = engine

        # регистрируем только команды (без аргументов — они обрабатываются динамически)
        for name in self.dispatcher.commands.keys():
            engine.register_command(name)

        engine.register_dynamic_provider(self.complete)

    # ==========================================
    # core completion
    # ==========================================
    async def complete(self, partial: str, previous_tokens: list[str]):
        """
        previous_tokens — теперь всегда корректные полные токены (благодаря фиксу в lsp_adapter).
        partial — текущий ввод (может начинаться с «--», «-----» и т.д.).
        """
        try:
            if not previous_tokens:
                return []  # команды уже в trie (fallback)

            cmd_name = previous_tokens[0]
            parser = self.dispatcher.get_command_parser(cmd_name)

            if not parser:
                return []

            # Передаём ТОЛЬКО аргументы после имени команды
            # (это ключевое изменение — контекст теперь всегда правильный)
            return self._complete_with_parser(parser, previous_tokens[1:], partial)

        except Exception:
            logger.exception("ShellLSP completion failed")
            return []

    # ==========================================
    # parser → completion (финальная версия)
    # ==========================================
    def _complete_with_parser(self, parser, arg_tokens: list[str], partial: str):
        """
        arg_tokens = все токены после имени команды (или субкоманды)
        partial     = то, что пользователь сейчас печатает
        """
        # ==================================================
        # 1. SUBCOMMANDS
        # ==================================================
        if parser._subparsers:
            if not arg_tokens:
                # ещё не выбрана подкоманда
                return [
                    name for name in parser._subparsers.keys()
                    if name.startswith(partial)
                ]

            subcmd = arg_tokens[0]
            subparser = parser._subparsers.get(subcmd)
            if subparser:
                # рекурсия на следующий уровень
                return self._complete_with_parser(subparser, arg_tokens[1:], partial)

        # ==================================================
        # 2. VALUE CONTEXT (самое важное исправление)
        #    Теперь проверяем ТОЛЬКО последний завершённый токен.
        #    Если он — опция, которая требует значение → предлагаем choices.
        #    После ввода значения (последний токен = значение) expecting = None.
        # ==================================================
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

        # ==================================================
        # 3. OPTIONS (флаги)
        # ==================================================
        results: list[str] = []

        for arg in parser._optionals:
            # выбираем нужный набор имён в зависимости от того, что пользователь начал вводить
            if partial.startswith("--"):
                names = arg.long_names
            elif partial.startswith("-"):
                names = arg.short_names
            else:
                names = arg.names

            for name in names:
                if name.startswith(partial):
                    results.append(name)

        # ==================================================
        # 4. POSITIONALS (если есть choices)
        # ==================================================
        for arg in parser._positionals:
            if arg.choices:
                for c in arg.choices:
                    c_str = str(c)
                    if c_str.startswith(partial):
                        results.append(c_str)

        return sorted(set(results))



#        logger.debug(
#            "LSP state: cmd=%s tokens=%s partial='%s' expecting=%s results=%s",
#            parser.prog,
#            tokens,
#            partial,
#            expecting_value.dest if expecting_value else None,
#            results
#        )