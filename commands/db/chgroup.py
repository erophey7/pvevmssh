from sshserver.commandapi import CommandAPI

def build_parser(parser):
    parser.description=command["help"]
    parser.add_argument("group_id", help="Group ID")
    parser.add_argument("users", nargs="+", help="One or more usernames")


async def execute(api: CommandAPI) -> str | None:
    api.require_permission("db_admin")

    parser = api.parser("chgroup", description=command["help"])
    parsed_args = parser.parse_args(api.args)

    try:
        group_id = int(parsed_args.group_id)
    except ValueError:
        return "Group ID must be a number.\n"

    placeholders = ",".join("?" * len(parsed_args.users))
    rows = await api.fetch_all(
        f"SELECT username FROM users WHERE username IN ({placeholders})",
        tuple(parsed_args.users)
    )
    existing = {row[0] for row in rows}
    missing = [u for u in parsed_args.users if u not in existing]
    if missing:
        return f"User(s) not found: {', '.join(missing)}\n"

    try:
        async with api.db.transaction():
            for user in parsed_args.users:
                await api.execute(
                    "UPDATE users SET group_id = ? WHERE username = ?",
                    (group_id, user)
                )
    except Exception as e:
        api.logger.exception("Failed to change groups")
        return f"Database error: {e}\n"

    api.logger.info("User %s changed groups of %s to %d", api.username, ", ".join(parsed_args.users), group_id)
    return f"Group of users: {', '.join(parsed_args.users)} set to {group_id}\n"


command = {
    "name": "chgroup",
    "help": "Change group of one or more users",
    "func": execute,
    "permissions": ["db_admin"]
}