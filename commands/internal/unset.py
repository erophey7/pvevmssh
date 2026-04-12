
from sshserver.commandapi import CommandAPI

async def execute(api: CommandAPI) -> str:
    parser = api.parser("unset", description="Remove environment variable")
    parser.add_argument("vars", nargs="+", help="Variables to unset")

    parsed_args = parser.parse_args(api.args)

    env = api.env
    vars = parsed_args.vars

    for var in vars:
        if env.get(var, None) is not None:
            env.unset(var)
        else:
            await api.write(f"Variable {var} is no setted\r\n")

command = {
    "name": "unset",
    "help": "Remove environment variable",
    "func": execute
}