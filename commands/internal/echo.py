"""
Echo arguments with variable expansion and escape sequence handling.
"""

from sshserver.session.manager import get_current_session


def echo(username: str, *args) -> str:
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

    session = get_current_session()
    env = session.extra.get('env') if session else None

    def expand_vars(text: str) -> str:
        if not env:
            return text
        if hasattr(env, 'substitute'):
            return env.substitute(text)
        # fallback for dict
        for key, val in env.items():
            text = text.replace(f"${key}", val)
        return text

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
    "func": echo
}