import os
import pty
import fcntl
import termios
import struct
import subprocess
import logging
import signal
import asyncio
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
    cols, rows, xpix, ypix = term_size
    return rows, cols, xpix, ypix


def _pty_preexec(slave_fd: int):
    def inner():
        os.setsid()
        fcntl.ioctl(slave_fd, termios.TIOCSCTTY, 0)
    return inner


async def _relay_ssh_to_pty(session, process):
    master_fd = session.extra["terminal_master_fd"]
    try:
        while session.extra.get("terminal_mode") and not session.extra["terminal_proc"].poll():
            try:
                data = await process.stdin.read(1024)
            except (asyncio.CancelledError, BrokenPipeError, OSError):
                break
            if not data:
                break
            os.write(master_fd, data.encode() if isinstance(data, str) else data)
    except Exception:
        pass


async def _relay_pty_to_ssh(session, process):
    master_fd = session.extra["terminal_master_fd"]
    loop = asyncio.get_running_loop()
    try:
        while session.extra.get("terminal_mode") and not session.extra["terminal_proc"].poll():
            try:
                data = await loop.run_in_executor(None, os.read, master_fd, 1024)
            except (asyncio.CancelledError, OSError):
                break
            if not data:
                break
            if isinstance(data, bytes):
                data = data.decode(errors="replace")
            process.stdout.write(data)
    except Exception:
        pass


async def _monitor_terminal_resize(session, process):
    master_fd = session.extra["terminal_master_fd"]
    local_proc = session.extra["terminal_proc"]
    current_size = get_normalized_terminal_size(process)
    while session.extra.get("terminal_mode") and not local_proc.poll():
        await asyncio.sleep(0.3)
        new_size = get_normalized_terminal_size(process)
        if new_size and new_size != current_size:
            current_size = new_size
            rows, cols, xpix, ypix = new_size
            with suppress(Exception):
                set_winsize(master_fd, rows, cols, xpix, ypix)
            with suppress(ProcessLookupError):
                os.kill(local_proc.pid, signal.SIGWINCH)


async def terminal(username: str, *args):
    if not args:
        return "Usage: terminal <vmid>\r\n"

    vmid = args[0]
    session = get_current_session()
    if not session:
        return "No session found.\r\n"

    process = session.extra.get("process")
    if not process or not process.channel:
        return "No valid SSH channel found.\r\n"

    channel = process.channel
    if session.extra.get("terminal_mode"):
        return "Terminal session already active.\r\n"

    # Сохраняем старый режим
    old_line_mode, old_echo = True, True
    with suppress(Exception):
        old_line_mode = channel.get_line_mode()
    with suppress(Exception):
        old_echo = channel.get_echo()

    try:
        # открываем PTY
        master_fd, slave_fd = pty.openpty()
        env = os.environ.copy()
        env.update({
            "TERM": process.term_type or "xterm-256color",
            "COLORTERM": "truecolor",
            "TERM_PROGRAM": "kitty" if "kitty" in (process.term_type or "").lower() else "",
            "KITTY_WINDOW_ID": os.environ.get("KITTY_WINDOW_ID", ""),
            "KITTY_LISTEN_ON": os.environ.get("KITTY_LISTEN_ON", ""),
            "USER": session.username,
            "HOME": os.path.expanduser("~"),
            "SHELL": "/bin/bash",
        })

        # отключаем line mode и echo перед запуском
        with suppress(Exception):
            channel.set_line_mode(False)
        with suppress(Exception):
            channel.set_echo(False)

        local_proc = subprocess.Popen(
            ["bash", "-i"],
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            preexec_fn=_pty_preexec(slave_fd),
            close_fds=True,
            env=env,
        )
        os.close(slave_fd)

        term_size = get_normalized_terminal_size(process)
        if term_size:
            rows, cols, xpix, ypix = term_size
            set_winsize(master_fd, rows, cols, xpix, ypix)

        session.extra.update({
            "terminal_mode": True,
            "terminal_master_fd": master_fd,
            "terminal_proc": local_proc,
            "terminal_old_line_mode": old_line_mode,
            "terminal_old_echo": old_echo,
            "terminal_vmid": vmid,
        })

        # запускаем relay задачи
        asyncio.create_task(_relay_ssh_to_pty(session, process))
        asyncio.create_task(_relay_pty_to_ssh(session, process))
        asyncio.create_task(_monitor_terminal_resize(session, process))

        return f"Connecting to VM {vmid} (emulated with bash)...\r\n"

    except Exception as e:
        logger.exception("Terminal init error")
        return f"Terminal init error: {e}\r\n"


command = {
    "name": "terminal",
    "help": "Open VM serial terminal",
    "func": terminal,
}