from helpers.globals import GlobalStore
from sshserver.sessions import get_current_session, SessionStore


########## About Command Implementation ##########
def about(username: str, *args) -> str:
    """
    ########## Display Server Information ##########
    
    Generates a formatted string containing information about the PVE SSH server,
    including configuration details, current session data, and active session count.
    
    Parameters:
        username (str): Username of the connected client
        *args: Additional arguments (not used in this implementation)
        
    Returns:
        str: Formatted string with server information
    """
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


########## Command Definition ##########
command = {
    "name": "about",
    "help": "Show server information",
    "func": about
}
