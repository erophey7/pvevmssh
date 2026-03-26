import os
import pty
import fcntl
import termios
import struct
import subprocess
import asyncio
import signal
import logging
from contextlib import suppress
from sshserver.sessions import get_current_session

logger = logging.getLogger(__name__)

########## Terminal Utils ##########

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

########## Terminal Mode ##########

async def terminal(username: str, *args):
    if not args:
        return b"Usage: terminal <vmid>\r\n"

    vmid = args[0]
    session = get_current_session()
    if not session:
        return b"No session found.\r\n"

    process = session.extra.get("process")
    if not process:
        return b"No process found in session.\r\n"

    channel = process.channel
    if not channel:
        return b"No channel available.\r\n"

    if session.extra.get("terminal_mode"):
        return b"Terminal session already active.\r\n"

    # Сохраняем старые режимы
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

        # Запускаем процесс (можно заменить bash на реальный VM serial)
        local_proc = subprocess.Popen(
            ["bash", "-i"],
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            preexec_fn=_pty_preexec(slave_fd),
            close_fds=True,
        )
        os.close(slave_fd)

        # Устанавливаем размер терминала
        term_size = get_normalized_terminal_size(process)
        if term_size:
            rows, cols, xpix, ypix = term_size
            set_winsize(master_fd, rows, cols, xpix, ypix)

        # Отключаем line mode и echo
        with suppress(Exception):
            channel.set_line_mode(False)
        with suppress(Exception):
            channel.set_echo(False)

        # Сохраняем состояние в сессии
        session.extra.update({
            "terminal_mode": True,
            "terminal_master_fd": master_fd,
            "terminal_proc": local_proc,
            "terminal_old_line_mode": old_line_mode,
            "terminal_old_echo": old_echo,
            "terminal_vmid": vmid,
        })

        # Запускаем relay задачки
        loop = asyncio.get_running_loop()
        session.extra["terminal_relay_in_task"] = asyncio.create_task(
            _relay_ssh_to_pty(process, session, master_fd, local_proc)
        )
        session.extra["terminal_relay_out_task"] = asyncio.create_task(
            _relay_pty_to_ssh(process, session, master_fd, local_proc)
        )
        session.extra["terminal_resize_task"] = asyncio.create_task(
            _monitor_terminal_size(process, session, master_fd, local_proc)
        )

        return f"Connecting to VM {vmid} (emulated with bash)...\r\n".encode()

    except Exception as e:
        logger.exception("Terminal init error")
        return f"Terminal init error: {e}\r\n".encode()


########## Relay Functions ##########

async def _relay_ssh_to_pty(process, session, master_fd, local_proc):
    try:
        while local_proc.poll() is None:
            try:
                data = await process.stdin.read(256)
            except (asyncio.CancelledError, BrokenPipeError, OSError):
                break
            if not data:
                continue
            if isinstance(data, str):
                data = data.encode()
            try:
                os.write(master_fd, data)
            except OSError:
                break
    except asyncio.CancelledError:
        pass

async def _relay_pty_to_ssh(process, session, master_fd, local_proc):
    loop = asyncio.get_running_loop()
    try:
        while local_proc.poll() is None:
            try:
                data = await loop.run_in_executor(None, os.read, master_fd, 256)
            except (OSError, asyncio.CancelledError):
                break
            if not data:
                continue
            try:
                process.stdout.write(data)
            except (OSError, BrokenPipeError):
                break
    except asyncio.CancelledError:
        pass

async def _monitor_terminal_size(process, session, master_fd, local_proc):
    current_size = get_normalized_terminal_size(process)
    try:
        while local_proc.poll() is None:
            await asyncio.sleep(0.3)
            new_size = get_normalized_terminal_size(process)
            if new_size and new_size != current_size:
                current_size = new_size
                rows, cols, xpix, ypix = new_size
                with suppress(Exception):
                    set_winsize(master_fd, rows, cols, xpix, ypix)
                with suppress(ProcessLookupError):
                    os.kill(local_proc.pid, signal.SIGWINCH)
    except asyncio.CancelledError:
        pass