from sshserver.commandapi import CommandAPI


async def execute(api: CommandAPI) -> str | None:
    session = api.session
    username = api.username
    group_name = session.extra.get('group_name', 'Unknown')
    perms = ', '.join(sorted(api.permissions)) if api.permissions else 'none'

    return f"You are {username} (group: {group_name})\nYour permissions: {perms}\n"


command = {
    "name": "whoami",
    "help": "Show current user, group and permissions",
    "func": execute
}