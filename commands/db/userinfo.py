import json
from sshserver.commandapi import CommandAPI

def build_parser(parser):
    parser.description=command["help"]
    parser.add_argument("-a", "--all", action="store_true", help="Show all stored fields (including SSH keys, saved_env, history)")
    parser.add_argument("username", nargs="?", help="USERNAME (optional, defaults to current user)")

async def execute(api: CommandAPI) -> str | None:
    api.require_permission("db_viewer")

    parser = api.parser("userinfo", description=command["help"])
    parsed_args = parser.parse_args(api.args)

    target_username = parsed_args.username or api.username

    row = await api.fetch_one(
        "SELECT username, group_id, created_at, ssh_keys, saved_env, history "
        "FROM users WHERE username = ?",
        (target_username,)
    )

    if not row:
        return f"User {target_username} not found.\n"

    db_username, group_id, created_at, ssh_keys_raw, saved_env_raw, history_raw = row

    force_group = api.config.get(f"auth.force_group.{db_username}", None)

    if parsed_args.all:
        ssh_keys = json.loads(ssh_keys_raw or "[]")
        saved_env = json.loads(saved_env_raw or "{}")
        history = json.loads(history_raw or "[]")

        group_line = f"Group ID: {group_id}"
        if force_group is not None:
            group_line += f", forced to {force_group}"

        output = [
            f"Username: {db_username}",
            group_line,
            f"Created at: {created_at}",
            f"SSH keys count: {len(ssh_keys)}",
            f"Saved env vars: {len(saved_env)}",
            f"History entries: {len(history)}",
        ]
        return "\n".join(output) + "\n"
    else:
        group_line = f"Group ID: {group_id}"
        if force_group is not None:
            group_line += f", forced to {force_group}"

        output = [
            f"Username: {db_username}",
            group_line,
            f"Created at: {created_at}",
        ]
        return "\n".join(output) + "\n"


command = {
    "name": "userinfo",
    "help": "Show information about a user",
    "func": execute,
    "permissions": ["db_viewer"],
    "build_parser": build_parser
}