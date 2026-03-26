"""
########## Terminal Command: Connect to VM Serial Port ##########
"""

import os
import pty
import fcntl
import termios
import struct
import subprocess
import logging
from contextlib import suppress
from sshserver.sessions import get_current_session

logger = logging.getLogger(__name__)


def set_winsize(fd: int, rows: int, cols: int, xpixels: int = 0, ypixels: int = 0) -> None:
    winsize = struct.pack("HHHH", rows, cols, xpixels, ypixels)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)


def get_normalized_terminal_size(process):
    term_size = process.get_terminal_size()
    if not term_size:
        return None

    # asyncssh обычно даёт: cols, rows, xpix, ypix
    cols, rows, xpix, ypix = term_size
    return rows, cols, xpix, ypix


def _pty_preexec(slave_fd: int):
    def inner():
        os.setsid()
        fcntl.ioctl(slave_fd, termios.TIOCSCTTY, 0)
    return inner


async def terminal(username: str, *args):
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

    if session.extra.get("terminal_mode"):
        return "Terminal session already active.\r\n"

    has_pty = hasattr(channel, "set_line_mode") and hasattr(channel, "set_echo")
    if not has_pty:
        return "No PTY available (terminal mode not supported).\r\n"

    old_line_mode = True
    old_echo = True

    if hasattr(channel, "get_line_mode"):
        with suppress(Exception):
            old_line_mode = channel.get_line_mode()

    if hasattr(channel, "get_echo"):
        with suppress(Exception):
            old_echo = channel.get_echo()

    try:
        master_fd, slave_fd = pty.openpty()

        local_proc = subprocess.Popen(
            ["bash", "-i"],
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            preexec_fn=_pty_preexec(slave_fd),
            close_fds=True,
        )

        os.close(slave_fd)

        term_size = get_normalized_terminal_size(process)
        if term_size:
            rows, cols, xpix, ypix = term_size
            set_winsize(master_fd, rows, cols, xpix, ypix)

        with suppress(Exception):
            channel.set_line_mode(False)

        with suppress(Exception):
            channel.set_echo(False)

        session.extra["terminal_mode"] = True
        session.extra["terminal_master_fd"] = master_fd
        session.extra["terminal_proc"] = local_proc
        session.extra["terminal_old_line_mode"] = old_line_mode
        session.extra["terminal_old_echo"] = old_echo
        session.extra["terminal_vmid"] = vmid

        return f"Connecting to VM {vmid} (emulated with bash)...\r\n"

    except Exception as e:
        logger.exception("Terminal init error")
        return f"Terminal init error: {e}\r\n"


command = {
    "name": "terminal",
    "help": "Open VM serial terminal",
    "func": terminal,
}