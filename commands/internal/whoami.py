# commands/internal/whoami.py
from sshserver.session.manager import get_current_session


async def execute(username: str, *args):
    global terminal
    session = get_current_session()
    terminal = session.extra["terminal"]

    await terminal.output.output_str(f"\r\nYou are {username} (group: {session.extra['group_name']})\r\n")
    await terminal.output.output_str("Your permissions: " + ", ".join(session.extra["permissions"]) + "\r\n")
    

command = {
    "name": "whoami",
    "help": "Show current user, group and permissions",
    "func": execute
}