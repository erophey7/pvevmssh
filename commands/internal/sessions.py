from sshserver.session.manager import SessionStore
import time


########## List Active SSH Sessions ##########
def sessions(username: str, *args) -> str:
    """
    ########## Display Active SSH Sessions ##########
    
    Lists all currently active SSH sessions with details including session ID,
    username, client address, terminal type, dimensions, and uptime.
    """

    store = SessionStore()
    active = store.list_all()
    if not active:
        return "No active sessions."

    lines = ["Active sessions:"]
    for s in active:
        # Calculate session uptime in seconds
        uptime = int(time.time() - s.start_time)
        lines.append(f"  {s.uuid[:8]}... {s.username}@{s.client_addr} "
                     f"{s.term_type} {s.term_width}x{s.term_height} uptime: {uptime}s")
    return "\n".join(lines)


########## Command Definition ##########
command = {
    "name": "sessions",
    "help": "List active SSH sessions",
    "func": sessions
}
