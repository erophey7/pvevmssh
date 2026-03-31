"""
switch terminal echoing
"""

from sshserver.commandapi import CommandAPI

async def execute(api: CommandAPI) -> str | None:
    args = api.args
    terminal = api.terminal


    if not args:
        match terminal.input.editor.echo:
            case True:
                echoing = False

            case False:
                echoing = True
    else:
        if args[0].lower() == "on":
            echoing = True
        elif args[0].lower() == "off":
            echoing = False

    terminal.input.editor.echo = echoing
    api.logger.debug(f"Now terminal echoing is {terminal.input.editor.echo}")
    return f"Terminal echo switched to {echoing}"


command = {
    "name": "termecho",
    "help": "Switchin terminal echo",
    "func": execute,
    "permisson": ["tester_perminssion"]
}