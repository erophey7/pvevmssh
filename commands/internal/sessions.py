"""
List active SSH sessions.
"""

from sshserver.commandapi import CommandAPI
from sshserver.session.manager import SessionStore
import time


async def execute(api: CommandAPI) -> str | None:
    api.require_permission("admin_permission")

    store = SessionStore()
    active = store.list_all()
    if not active:
        return "No active sessions."

    lines = ["Active sessions:"]
    for s in active:
        uptime = int(time.time() - s.start_time)
        lines.append(f"  {s.uuid[:8]}... {s.username}@{s.client_addr} "
                     f"{s.term_type} {s.term_width}x{ s.term_height} uptime: {uptime}s")
    return "\n".join(lines)


command = {
    "name": "sessions",
    "help": "List active SSH sessions",
    "func": execute,
    "permissions": ["admin_permission"]
}