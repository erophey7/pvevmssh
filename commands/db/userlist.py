# commands/db/userlist.py
"""
List users from database.
"""

from sshserver.commandapi import CommandAPI, CommandArgumentError


async def execute(api: CommandAPI) -> str | None:
    api.require_permission("db_viewer")

    parser = api.parser("userlist", description="List users")
    parser.add_argument("-g", "--group", help="Show only users belonging to the given group ID")
    parser.add_argument("-G", "--show-group", action="store_true", help="Include group ID in output")

    try:
        ns = parser.parse_args(api.args)
    except CommandArgumentError as e:
        return f"Argument error: {e}\n"

    group_id = None
    if ns.group is not None:
        try:
            group_id = int(ns.group)
        except ValueError:
            return f"Invalid group ID: {ns.group}\n"

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
        if ns.show_group:
            lines.append(f"{username} (group {gid})")
        else:
            lines.append(username)
    return "\n".join(lines) + "\n"


command = {
    "name": "userlist",
    "help": "List users",
    "func": execute,
    "permissions": ["db_viewer"]
}