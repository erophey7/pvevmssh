from sshserver.commandapi import CommandAPI

def build_parser(parser):
    parser.description=command["help"]
    parser.add_argument("state", nargs="?", choices=["on", "off"], help="on or off")

async def execute(api: CommandAPI) -> str | None:
    parser = api.parser("termecho", description=command["help"])
    
    parsed_args = parser.parse_args(api.args)

    if parsed_args.state:
        echoing = parsed_args.state == "on"
    else:
        echoing = not api.terminal.input.editor.vpub.echo

    api.terminal.input.editor.vpub.echo = echoing
    api.logger.debug(f"Now terminal echoing is {echoing}")
    return f"Terminal echo switched to {echoing}\n"


command = {
    "name": "termecho",
    "help": "Switch terminal echo",
    "func": execute,
    "permissions": ["tester_permission"],
    "build_parser": build_parser
}