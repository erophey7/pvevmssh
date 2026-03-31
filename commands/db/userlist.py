# commands/db/userlist.py
"""
List users from database.
"""

from dataclasses import dataclass
from sshserver.commandapi import CommandAPI, CommandArgumentError

HELP = """Usage: userlist [OPTIONS]

List users.

Options:
  -g GROUP, --group GROUP   Show only users belonging to the given group ID
  --show-group              Include group ID in output
  -h, --help                Show this help
"""


@dataclass
class ParsedArgs:
    group_id: int | None = None
    show_group: bool = False
    help: bool = False


def parse_args(args: tuple[str, ...]) -> ParsedArgs:
    parsed = ParsedArgs()
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("-h", "--help"):
            parsed.help = True
            i += 1
        elif arg == "--show-group":
            parsed.show_group = True
            i += 1
        elif arg in ("-g", "--group"):
            if i + 1 >= len(args):
                raise CommandArgumentError(f"{arg} requires a value")
            try:
                parsed.group_id = int(args[i + 1])
            except ValueError:
                raise CommandArgumentError(f"Invalid group ID: {args[i+1]}")
            i += 2
        else:
            raise CommandArgumentError(f"Unknown argument: {arg}")
    return parsed


async def execute(api: CommandAPI) -> str | None:
    api.require_permission("db_viewer")

    parsed = parse_args(api.args)

    if parsed.help:
        return HELP

    if parsed.group_id is not None:
        rows = await api.fetch_all(
            "SELECT username, group_id FROM users WHERE group_id = ? ORDER BY username",
            (parsed.group_id,)
        )
    else:
        rows = await api.fetch_all(
            "SELECT username, group_id FROM users ORDER BY username"
        )

    if not rows:
        return "No users found.\n"

    lines = []
    for username, group_id in rows:
        if parsed.show_group:
            lines.append(f"{username} (group {group_id})")
        else:
            lines.append(username)
    return "\n".join(lines) + "\n"


command = {
    "name": "userlist",
    "help": "List users",
    "func": execute,
    "permissions": ["db_viewer"]
}