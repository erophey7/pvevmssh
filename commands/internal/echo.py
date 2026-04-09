r"""
GNU coreutils echo — полный Linux-совместимый вариант.
"""

from sshserver.commandapi import CommandAPI, CommandArgumentError


async def execute(api: CommandAPI) -> str | None:
    parser = api.parser("echo", description="Display text with variable expansion and backslash escapes")
    parser.add_argument("-n", action="store_true", help="do not output the trailing newline")
    parser.add_argument("-e", action="store_true", help="enable interpretation of backslash escapes")
    parser.add_argument("-E", action="store_true", help="disable interpretation of backslash escapes (default)")
    parser.add_argument("text", nargs="*", help="Strings to echo")

    try:
        ns = parser.parse_args(api.args)
    except CommandArgumentError as e:
        return f"Argument error: {e}\n"

    no_newline = ns.n
    interpret_escapes = ns.e
    if ns.E and not interpret_escapes:
        interpret_escapes = False

    output_args = ns.text or []

    
    def expand_vars(text: str) -> str:
        return api.env_substitute(text)

    def strip_quotes(s: str) -> str:
        if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
            return s[1:-1]
        return s

    escapes = {
        "a": "\a", "b": "\b", "e": "\x1b", "f": "\f", "n": "\n",
        "r": "\r", "t": "\t", "v": "\v", "\\": "\\",
    }

    result_parts = []
    for arg in output_args:
        arg = strip_quotes(arg)
        arg = expand_vars(arg)

        if interpret_escapes:
            i = 0
            while i < len(arg):
                if arg[i] == "\\" and i + 1 < len(arg):
                    next_char = arg[i + 1]
                    if next_char in escapes:
                        result_parts.append(escapes[next_char])
                        i += 2
                        continue
                    elif next_char == "0" and i + 3 < len(arg):
                        try:
                            result_parts.append(chr(int(arg[i+2:i+5], 8)))
                            i += 5
                            continue
                        except ValueError:
                            pass
                    elif next_char == "x" and i + 3 < len(arg):
                        try:
                            result_parts.append(chr(int(arg[i+2:i+4], 16)))
                            i += 4
                            continue
                        except ValueError:
                            pass
                    elif next_char == "c":
                        return "".join(result_parts)
                else:
                    result_parts.append(arg[i])
                i += 1
        else:
            result_parts.append(arg)

    output = "".join(result_parts)
    if not no_newline:
        output += "\n"

    return output


command = {
    "name": "echo",
    "help": "Display text with variable expansion and backslash escapes",
    "func": execute,
}