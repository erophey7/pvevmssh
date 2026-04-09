"""
switch terminal echoing
"""

from sshserver.commandapi import CommandAPI, CommandArgumentError


async def execute(api: CommandAPI) -> str | None:
    parser = api.parser("termecho", description="Switch terminal echo")
    parser.add_argument("state", nargs="?", choices=["on", "off"], help="on or off")

    try:
        ns = parser.parse_args(api.args)
    except CommandArgumentError as e:
        return f"Argument error: {e}\n"

    if ns.state:
        echoing = ns.state == "on"
    else:
        echoing = not api.terminal.input.editor.echo

    api.terminal.input.editor.echo = echoing
    api.logger.debug(f"Now terminal echoing is {echoing}")
    return f"Terminal echo switched to {echoing}\n"


command = {
    "name": "termecho",
    "help": "Switch terminal echo",
    "func": execute,
    "permissions": ["tester_permission"]
}