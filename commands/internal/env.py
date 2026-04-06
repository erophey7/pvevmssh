from sshserver.commandapi import CommandAPI, CommandArgumentError

HELP = """ Usage env [OPTIONS] [ARGS]

Manage your enviromnet.

Options:
  -h, --help            Show this help
  -f, --flush           Flush env [all, runtime, db]
  -s, --save            Save env to db

"""


def shell_escape(value: str) -> str:
    """
    Escape control characters for safe one-line shell-style output.
    """
    return (
        value
        .replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )


async def execute(api: CommandAPI) -> str:
    parser = api.parser("env")
    parser.add_flag("-h", "--help", help="Show this help")
    parser.add_option("-f", "--flush", help="Flush env [all, runtime, db]")
    parser.add_flag("-s", "--save", help="Save env to db")

    try:
        ns = parser.parse(api.args)
    except CommandArgumentError as e:
        return f"Argument error: {e}\n"

    if hasattr(ns, "help") and ns.help:
        return HELP

    env = api.env

    if hasattr(ns, "flush") and ns.flush:
        if ns.flush == "all":
            await env.clear(store="all")
            await api.write_success("Flush complete\n")
        elif ns.flush == "runtime":
            await env.clear(store="runtime")
            await api.write_success("Flush complete\n")
        elif ns.flush == "db":
            await env.clear(store="db")
            await api.write_success("Flush complete\n")
        else:
            await api.write_error("Argument error\n")

    if hasattr(ns, "save") and ns.save:
        await env.save()
        await api.write_success("Env saved")
        return

    for key in env.all():
        value = env.get(key, "")
        await api.write(f"{key}={shell_escape(value)}\r\n")

    return ""
    

command = {
    "name": "env",
    "help": "Manage your Enviromnet",
    "func": execute
}