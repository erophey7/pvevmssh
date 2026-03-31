"""
Echo arguments with variable expansion and escape sequence handling.
"""

from sshserver.commandapi import CommandAPI, CommandArgumentError


async def execute(api: CommandAPI) -> str | None:
    args = api.args

    if not args:
        return ""

    no_newline = True
    interpret = True
    output_args = []
    for arg in args:
        if arg == "-n":
            no_newline = False
        elif arg == "-E":
            interpret = False
        else:
            output_args.append(arg)

    def expand_vars(text: str) -> str:
        return api.env_substitute(text)

    def strip_quotes(s: str) -> str:
        if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
            return s[1:-1]
        return s

    result_parts = []
    for arg in output_args:
        arg = strip_quotes(arg)
        arg = expand_vars(arg)
        if interpret:
            arg = arg.replace('\\n', '\n')
            arg = arg.replace('\\t', '\t')
            arg = arg.replace('\\r', '\r')
            arg = arg.replace('\\\\', '\\')
        result_parts.append(arg)

    output = ' '.join(result_parts)
    if not no_newline:
        output += '\n'
    return output


command = {
    "name": "echo",
    "help": "Display arguments with variable expansion (default: interpret escapes)",
    "func": execute
}