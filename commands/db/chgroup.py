# commands/db/chgroup.py
"""
Change group for users.
"""

from sshserver.commandapi import CommandAPI, CommandArgumentError


async def execute(api: CommandAPI) -> str | None:
    api.require_permission("db_admin")

    parser = api.parser("chgroup", description="Change group ID for one or more users")
    parser.add_argument("group_id", help="Group ID")
    parser.add_argument("users", nargs="+", help="One or more usernames")

    try:
        ns = parser.parse_args(api.args)
    except CommandArgumentError as e:
        return f"Argument error: {e}\n"

    try:
        group_id = int(ns.group_id)
    except ValueError:
        return "Group ID must be a number.\n"

    placeholders = ",".join("?" * len(ns.users))
    rows = await api.fetch_all(
        f"SELECT username FROM users WHERE username IN ({placeholders})",
        tuple(ns.users)
    )
    existing = {row[0] for row in rows}
    missing = [u for u in ns.users if u not in existing]
    if missing:
        return f"User(s) not found: {', '.join(missing)}\n"

    try:
        async with api.db.transaction():
            for user in ns.users:
                await api.execute(
                    "UPDATE users SET group_id = ? WHERE username = ?",
                    (group_id, user)
                )
    except Exception as e:
        api.logger.exception("Failed to change groups")
        return f"Database error: {e}\n"

    api.logger.info("User %s changed groups of %s to %d", api.username, ", ".join(ns.users), group_id)
    return f"Group of users: {', '.join(ns.users)} set to {group_id}\n"


command = {
    "name": "chgroup",
    "help": "Change group of one or more users",
    "func": execute,
    "permissions": ["db_admin"]
}