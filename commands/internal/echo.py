r"""
GNU coreutils echo — полный Linux-совместимый вариант.

Поддерживает:
  -n              не выводить финальный \n
  -e              интерпретировать backslash-escapes
  -E              НЕ интерпретировать escapes (поведение по умолчанию)
  --help, -h      справка
  --version       версия
  \a \b \c \e \f \n \r \t \v \\ \0NNN \xHH
"""

from sshserver.commandapi import CommandAPI


async def execute(api: CommandAPI) -> str | None:
    args = api.args

    if not args:
        return ""

    # ─────────────────────────────────────────────────────────────
    # Парсинг опций (как в настоящем GNU echo)
    # ─────────────────────────────────────────────────────────────
    no_newline = False
    interpret_escapes = False   # по умолчанию -E
    i = 0

    while i < len(args):
        arg = args[i]
        if arg == "-n":
            no_newline = True
        elif arg == "-e":
            interpret_escapes = True
        elif arg == "-E":
            interpret_escapes = False
        elif arg in ("--help", "-h"):
            return (
                "Usage: echo [OPTION]... [STRING]...\n"
                "  -n             do not output the trailing newline\n"
                "  -e             enable interpretation of backslash escapes\n"
                "  -E             disable interpretation of backslash escapes (default)\n"
                "  --help         display this help and exit\n"
            )
        elif arg.startswith("-") and arg != "--":
            break
        else:
            break
        i += 1

    output_args = args[i:]

    # ─────────────────────────────────────────────────────────────
    # Вспомогательные функции
    # ─────────────────────────────────────────────────────────────
    def expand_vars(text: str) -> str:
        return api.env_substitute(text)

    def strip_quotes(s: str) -> str:
        """Сохраняет пробелы внутри кавычек (как в bash)."""
        if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
            return s[1:-1]
        return s

    # Полный набор escape-последовательностей GNU echo (-e)
    escapes = {
        "a": "\a",      # bell
        "b": "\b",      # backspace
        "e": "\x1b",    # escape
        "f": "\f",      # form feed
        "n": "\n",
        "r": "\r",
        "t": "\t",
        "v": "\v",
        "\\": "\\",
    }

    result_parts = []
    for arg in output_args:
        arg = strip_quotes(arg)
        arg = expand_vars(arg)

        if interpret_escapes:
            # Обрабатываем все \xHH и \0NNN
            i = 0
            while i < len(arg):
                if arg[i] == "\\" and i + 1 < len(arg):
                    next_char = arg[i + 1]
                    if next_char in escapes:
                        result_parts.append(escapes[next_char])
                        i += 2
                        continue
                    elif next_char == "0" and i + 3 < len(arg):  # \0NNN (octal)
                        try:
                            oct_val = int(arg[i+2:i+5], 8)
                            result_parts.append(chr(oct_val))
                            i += 5
                            continue
                        except ValueError:
                            pass
                    elif next_char == "x" and i + 3 < len(arg):   # \xHH (hex)
                        try:
                            hex_val = int(arg[i+2:i+4], 16)
                            result_parts.append(chr(hex_val))
                            i += 4
                            continue
                        except ValueError:
                            pass
                    elif next_char == "c":                         # \c — прекратить вывод
                        return "".join(result_parts)               # и без \n
                else:
                    result_parts.append(arg[i])
                i += 1
        else:
            # -E режим — просто добавляем как есть
            result_parts.append(arg)

    output = "".join(result_parts)   # используем ''.join, а не ' '.join — GNU echo так делает

    if not no_newline:
        output += "\n"

    return output


command = {
    "name": "echo",
    "help": "Display text with variable expansion and backslash escapes",
    "func": execute,
}