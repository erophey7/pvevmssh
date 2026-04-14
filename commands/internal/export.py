from sshserver.commandapi import CommandAPI

def build_parser(parser):
    parser.description=command["help"]
    parser.add_argument("var", nargs="*", help="Variables to export/display")

async def execute(api: CommandAPI) -> str | None:
    parser = api.parser("export", description=command["help"])
    parsed_args = parser.parse_args(api.args)

    env = api.env
    if not parsed_args.var:
        items = env.all().items() if hasattr(env, 'all') else env._vars.items()
        lines = [f"{k}={v}" for k, v in items]
        return "\n".join(lines) + "\n" if lines else "No variables set.\n"

    results = [env.export(v).rstrip("\n") for v in parsed_args.var if env.export(v)]
    api.session.extra["style"].reload()
    return "\n".join(results) + "\n" if results else None


command = {
    "name": "export",
    "help": "Set or display environment variables",
    "func": execute,
    "build_parser": build_parser
}