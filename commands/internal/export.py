"""
Set or display environment variables.
"""

from sshserver.commandapi import CommandAPI


async def execute(api: CommandAPI) -> str | None:
    env = api.env
    args = api.args

    if not args:
        if hasattr(env, 'all'):
            items = env.all().items()
        elif hasattr(env, '_vars'):
            items = env._vars.items()
        else:
            return "Cannot retrieve environment variables.\n"

        lines = [f"{k}={v}" for k, v in items]
        return "\n".join(lines) + "\n" if lines else "No variables set.\n"

    results = []
    for arg in args:
        result = env.export(arg)
        if result:
            results.append(result.rstrip("\n"))

    return "\n".join(results) + "\n" if results else None


command = {
    "name": "export",
    "help": "Set or display environment variables",
    "func": execute
}