from sshserver.commandapi import CommandAPI

def build_parser(parser):
    parser.description=command["help"]
    parser.add_argument("-g", "--group", help="Show only users belonging to the given group ID")
    parser.add_argument("-G", "--show-group", action="store_true", help="Include group ID in output")

async def execute(api: CommandAPI) -> str | None:
    api.require_permission("db_viewer")
    parser = api.parser("userlist", description=command["help"])

    parsed_args = parser.parse_args(api.args)


    group_id = None
    if parsed_args.group is not None:
        try:
            group_id = int(parsed_args.group)
        except ValueError:
            return f"Invalid group ID: {parsed_args.group}\n"

    if group_id is not None:
        rows = await api.fetch_all(
            "SELECT username, group_id FROM users WHERE group_id = ? ORDER BY username",
            (group_id,)
        )
    else:
        rows = await api.fetch_all(
            "SELECT username, group_id FROM users ORDER BY username"
        )

    if not rows:
        return "No users found.\n"

    lines = []
    for username, gid in rows:
        if parsed_args.show_group:
            lines.append(f"{username} (group {gid})")
        else:
            lines.append(username)
    return "\n".join(lines) + "\n"


command = {
    "name": "userlist",
    "help": "List users",
    "func": execute,
    "permissions": ["db_viewer"],
    "build_parser": build_parser
}