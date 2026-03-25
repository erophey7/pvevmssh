from helpers.globals import GlobalStore
from sshserver.sessions import get_current_session, SessionStore

def about(username: str, *args) -> str:
    config = GlobalStore.get().require("config")
    current = get_current_session()

    lines = [
        "PVE SSH Server v0.1",
        f"User: {username}",
        f"Authentication: password (temporary)",
        f"Listen: {config.get('ssh.bind')}",
    ]

    if current:
        lines.extend([
            f"Session UUID: {current.uuid}",
            f"Client address: {current.client_addr}",
            f"Terminal: {current.term_type} {current.term_width}x{current.term_height}",
            f"Connected since: {current.start_time:.0f}",
        ])

    active = SessionStore().count()
    lines.append(f"Active sessions: {active}")

    return "\n".join(lines)

command = {
    "name": "about",
    "help": "Show server information",
    "func": about
}