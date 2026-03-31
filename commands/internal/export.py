"""
Set or display environment variables.
"""

from sshserver.commandapi import CommandAPI


async def execute(api: CommandAPI) -> str | None:
    env = api.env
    args = api.args

    if not args:
        # Показать все переменные окружения
        if hasattr(env, 'as_dict'):
            items = env.as_dict().items()
        elif hasattr(env, '_vars'):
            items = env._vars.items()
        else:
            return "Cannot retrieve environment variables.\n"
        lines = [f"{k}={v}" for k, v in items]
        return "\n".join(lines) + "\n" if lines else "No variables set.\n"

    results = []
    for arg in args:
        if "=" not in arg:
            continue
        key, value = arg.split("=", 1)
        api.env_set(key, value)
        results.append(f"{key}={value}")

    return "Environment variables set: " + ", ".join(results) + "\n"


command = {
    "name": "export",
    "help": "Set or display environment variables",
    "func": execute
}