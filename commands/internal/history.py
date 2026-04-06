from sshserver.commandapi import CommandAPI, CommandArgumentError

HELP = """ Usage history [OPTIONS] [ARGS]

Manage your command history.

Options:
  -h, --help            Show this help
  -f, --flush           Flush history [all, runtime, db]
  -s, --save            Save history to db
  -m, --max             Max history to shown

"""

async def execute(api: CommandAPI) -> str:
    parser = api.parser("history")
    parser.add_flag("-h", "--help", help="Show this help")
    parser.add_option("-f", "--flush", help="Flush history [all, runtime, db]")
    parser.add_flag("-s", "--save", help="Save history to db")
    parser.add_option("-m", "--max", help="Max history to shown")

    try:
        ns = parser.parse(api.args)
    except CommandArgumentError as e:
        return f"Argument error: {e}\n"
    
    if hasattr(ns, "help") and ns.help:
        return HELP
    
    history = api.history
    
    if hasattr(ns, "flush") and ns.flush:
        if ns.flush == "all":
            await history.clear(store="all")
            return "Flush complete"
        elif ns.flush == ns.flush == "runtime":
            await history.clear(store="runtime")
            return "Flush complete"
        elif ns.flush == ns.flush == "db":
            await history.clear(store="db")
            return "Flush complete"
        else:
            return "Argument error"
        

    for i, n in enumerate(history.all()):
        await api.write(f"  {i+1}  {n}\r\n")

    if hasattr(ns, "save") and ns.save:
        await history.save()
        return "history saved"


command = {
    "name": "history",
    "help": "Manage your command history",
    "func": execute
}