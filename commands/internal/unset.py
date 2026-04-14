from sshserver.commandapi import CommandAPI

def build_parser(parser):
    parser.description=command["help"]
    parser.add_argument("vars", nargs="+", help="Variables to unset")

async def execute(api: CommandAPI) -> str:
    parser = api.parser("unset", description=command["help"])
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
    "func": execute,
    "build_parser": build_parser
}