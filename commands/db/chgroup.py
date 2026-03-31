# commands/db/chgroup.py
"""
Change group for users.
"""

import logging
from dataclasses import dataclass
from sshserver.commandapi import CommandAPI, CommandArgumentError

HELP = """Usage: chgroup <group_id> <user1> [user2...]

Change group ID for one or more users. Requires db_admin permission.

Example:
  chgroup 10 alice bob
"""


@dataclass
class ParsedArgs:
    group_id: int | None = None
    users: list[str] | None = None
    help: bool = False


def parse_args(args: tuple[str, ...]) -> ParsedArgs:
    parsed = ParsedArgs()
    if not args:
        parsed.help = True
        return parsed

    # First argument is group_id
    try:
        parsed.group_id = int(args[0])
    except ValueError:
        parsed.help = True  # malformed
        return parsed

    # Rest are usernames
    parsed.users = list(args[1:])
    if not parsed.users:
        parsed.help = True
    return parsed


async def execute(api: CommandAPI) -> str | None:
    api.require_permission("db_admin")

    parsed = parse_args(api.args)

    if parsed.help:
        return HELP

    if parsed.group_id is None or not parsed.users:
        return HELP

    # Check that all target users exist
    placeholders = ",".join("?" * len(parsed.users))
    rows = await api.fetch_all(
        f"SELECT username FROM users WHERE username IN ({placeholders})",
        tuple(parsed.users)
    )
    existing = {row[0] for row in rows}
    missing = [u for u in parsed.users if u not in existing]
    if missing:
        return f"User(s) not found: {', '.join(missing)}\n"

    # Perform update in transaction
    try:
        async with api.db.transaction():
            for user in parsed.users:
                await api.execute(
                    "UPDATE users SET group_id = ? WHERE username = ?",
                    (parsed.group_id, user)
                )
    except Exception as e:
        api.logger.exception("Failed to change groups")
        return f"Database error: {e}\n"

    api.logger.info("User %s changed groups of %s to %d", api.username, ", ".join(parsed.users), parsed.group_id)
    return f"Group of users: {', '.join(parsed.users)} set to {parsed.group_id}\n"


command = {
    "name": "chgroup",
    "help": "Change group of one or more users",
    "func": execute,
    "permissions": ["db_admin"]
}