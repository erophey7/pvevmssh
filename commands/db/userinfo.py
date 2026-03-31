# commands/db/userinfo.py
"""
Show user information from database.
"""

import json
from dataclasses import dataclass
from sshserver.commandapi import CommandAPI, CommandArgumentError

HELP = """Usage: userinfo [OPTIONS] [USERNAME]

Show information about a user. If USERNAME is omitted, shows current user.

Options:
  -a, --all          Show all stored fields (including SSH keys, saved_env, history)
  -h, --help         Show this help
"""


@dataclass
class ParsedArgs:
    username: str | None = None
    all_fields: bool = False
    help: bool = False


def parse_args(args: tuple[str, ...], default_username: str) -> ParsedArgs:
    parsed = ParsedArgs()
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("-h", "--help"):
            parsed.help = True
            i += 1
        elif arg in ("-a", "--all"):
            parsed.all_fields = True
            i += 1
        else:
            if parsed.username is None:
                parsed.username = arg
                i += 1
            else:
                raise CommandArgumentError(f"Unexpected argument: {arg}")
    if parsed.username is None:
        parsed.username = default_username
    return parsed


async def execute(api: CommandAPI) -> str | None:
    api.require_permission("db_viewer")

    parsed = parse_args(api.args, api.username)

    if parsed.help:
        return HELP

    row = await api.fetch_one(
        "SELECT username, group_id, created_at, ssh_keys, saved_env, history "
        "FROM users WHERE username = ?",
        (parsed.username,)
    )

    if not row:
        return f"User {parsed.username} not found.\n"

    db_username, group_id, created_at, ssh_keys_raw, saved_env_raw, history_raw = row

    if parsed.all_fields:
        ssh_keys = json.loads(ssh_keys_raw or "[]")
        saved_env = json.loads(saved_env_raw or "{}")
        history = json.loads(history_raw or "[]")

        output = [
            f"Username: {db_username}",
            f"Group ID: {group_id}",
            f"Created at: {created_at}",
            f"SSH keys count: {len(ssh_keys)}",
            f"Saved env vars: {len(saved_env)}",
            f"History entries: {len(history)}",
        ]
        return "\n".join(output) + "\n"
    else:
        return (
            f"Username: {db_username}\n"
            f"Group ID: {group_id}\n"
            f"Created at: {created_at}\n"
        )


command = {
    "name": "userinfo",
    "help": "Show information about a user",
    "func": execute,
    "permissions": ["db_viewer"]
}