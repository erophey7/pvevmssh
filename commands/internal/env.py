from sshserver.commandapi import CommandAPI


def shell_escape(value: str) -> str:
    return (
        value
        .replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )

def build_parser(parser):
    parser.description=command["help"]
    parser.add_argument("-f", "--flush", help="Flush env [all, runtime, db]")
    parser.add_argument("-s", "--save", action="store_true", help="Save env to db")


async def execute(api: CommandAPI) -> str:
    parser = api.parser("env", description=command["help"])
    parsed_args = parser.parse_args(api.args)

    env = api.env

    if parsed_args.flush:
        store = parsed_args.flush
        if store not in ("all", "runtime", "db"):
            await api.write_error("Invalid flush target. Use: all, runtime, db\n")
        else:
            await env.clear(store=store)
            await api.write_success(f"Flush complete ({store})\n")
        return ""

    if parsed_args.save:
        await env.save()
        await api.write_success("Environment saved\n")
        return ""

    for key in env.all():
        value = env.get(key, "")
        await api.write(f"{key}={shell_escape(value)}\r\n")

    return ""
    

command = {
    "name": "env",
    "help": "Manage your environment",
    "func": execute,
    "build_parser": build_parser
}