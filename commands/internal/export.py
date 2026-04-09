"""
Set or display environment variables.
"""

from sshserver.commandapi import CommandAPI, CommandArgumentError


async def execute(api: CommandAPI) -> str | None:
    parser = api.parser("export", description="Set or display environment variables")
    parser.add_argument("var", nargs="*", help="Variables to export/display")

    try:
        ns = parser.parse_args(api.args)
    except CommandArgumentError as e:
        return f"Argument error: {e}\n"

    env = api.env
    if not ns.var:
        items = env.all().items() if hasattr(env, 'all') else env._vars.items()
        lines = [f"{k}={v}" for k, v in items]
        return "\n".join(lines) + "\n" if lines else "No variables set.\n"

    results = [env.export(v).rstrip("\n") for v in ns.var if env.export(v)]
    return "\n".join(results) + "\n" if results else None


command = {
    "name": "export",
    "help": "Set or display environment variables",
    "func": execute
}