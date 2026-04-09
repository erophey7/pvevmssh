from sshserver.commandapi import CommandAPI

import json

def safe_serialize(obj):
    try:
        return json.dumps(obj, ensure_ascii=False, indent=2)
    except TypeError:
        return str(obj)

async def execute(api: CommandAPI) -> None:
    parser = api.parser("sessioninfo")
    
    parser.add_argument("-a", "--all", action="store_true", help="show all")
    parser.add_argument("params", nargs="*", help="shown list")
    

    parsed_args = parser.parse_args(api.args)

    session = api.session

    session_obj = object.__repr__(session)
    session_keys = list(session.__dataclass_fields__.keys())

    await api.write(f"obj: {session_obj}\r\n")

    await api.write(f"keys: {session_keys}\r\n")

    # all
    if parsed_args.all:
        for key in (k for k in session_keys if k != "extra"):
            await api.write(f"{key} - {getattr(session, key)}\r\n")

        safe_extra = {k: (v if isinstance(v, (str, int, float, bool, list, dict, type(None))) else str(v))
                      for k, v in session.extra.items()}

        await api.write(f"extra - {json.dumps(safe_extra, ensure_ascii=False, indent=2)}\r\n")

    # standalone params
    else:
        for key in (k for k in parsed_args.params if k != "extra"):
            if key in session_keys:
                await api.write(f"{key} - {getattr(session, key)}\r\n")
            else:
                await api.write(f"{key} not found\r\n")

        if "extra" in parsed_args.params:
            safe_extra = {k: (v if isinstance(v, (str, int, float, bool, list, dict, type(None))) else str(v))
                      for k, v in session.extra.items()}

            await api.write(f"extra - {json.dumps(safe_extra, ensure_ascii=False, indent=2)}\r\n")


command = {
    "name": "sessioninfo",
    "help": "list of session params",
    "func": execute,
}