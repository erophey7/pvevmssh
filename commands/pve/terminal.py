"""
########## Terminal Command: Connect to VM Serial Port ##########
"""

import logging
from sshserver.sessions import get_current_session

logger = logging.getLogger(__name__)


async def terminal(username: str, *args):
    """
    Usage: terminal <vmid>

    This command only requests entering terminal mode.
    Actual PTY lifecycle is handled by sshserver.terminal_runtime.
    """
    if not args:
        return "Usage: terminal <vmid>\r\n"

    vmid = args[0]
    session = get_current_session()
    if not session:
        return "No session found.\r\n"

    process = session.extra.get("process")
    if not process:
        return "No process found in session.\r\n"

    channel = process.channel
    if not channel:
        return "No channel available.\r\n"

    try:
        has_pty = hasattr(channel, "set_line_mode") and hasattr(channel, "set_echo")
    except Exception as e:
        logger.error("Error checking PTY support: %s", e)
        return "No PTY available (terminal mode not supported).\r\n"

    if not has_pty:
        return "No PTY available (terminal mode not supported).\r\n"

    if session.extra.get("terminal_mode"):
        return "Already in terminal mode.\r\n"

    session.extra["terminal_mode"] = True
    session.extra["terminal_vmid"] = vmid

    # Important:
    # Returning empty string means handler should switch mode
    # without printing extra output.
    return ""
    

command = {
    "name": "terminal",
    "help": "Open VM serial terminal",
    "func": terminal,
}