from sshserver.commandapi import CommandAPI

def build_parser(parser):
    parser.description=command["help"]
    parser.add_argument("-f", "--flush", help="Flush history [all, runtime, db]")
    parser.add_argument("-s", "--save", action="store_true", help="Save history to db")
    parser.add_argument("-m", "--max", help="Max history to shown")

async def execute(api: CommandAPI) -> str:
    parser = api.parser("history", description=command["help"])

    ns = parser.parse_args(api.args)

    api.logger.debug("executed")


    history = api.history

    if ns.flush:
        store = ns.flush
        if store not in ("all", "runtime", "db"):
            return "Invalid flush target. Use: all, runtime, db\n"
        await history.clear(store=store)
        return f"Flush complete ({store})"

    if ns.save:
        await history.save()
        return "History saved to DB"

    for i, entry in enumerate(history.all()):
        await api.write(f"  {i+1:2}  {entry}\r\n")

    return ""
    

command = {
    "name": "history",
    "help": "Manage your command history",
    "func": execute,
    "build_parser": build_parser
}