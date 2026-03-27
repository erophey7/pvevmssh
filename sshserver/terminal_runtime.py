import asyncio
import pty
import subprocess
import os
import fcntl
import termios
import signal
import struct
import logging
from contextlib import suppress

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


async def monitor_size(process, master_fd, local_proc):
    current_size = get_normalized_terminal_size(process)

    try:
        while local_proc.poll() is None:
            await asyncio.sleep(0.5)
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


async def run_terminal_session(process, session):
    """
    Runs one full PTY-backed interactive terminal session.

    This is the ONLY place responsible for:
    - PTY creation
    - child process launch
    - SSH <-> PTY redirect
    - resize monitoring
    - line mode / echo switching
    - cleanup
    """
    channel = process.channel
    vmid = session.extra.get("terminal_vmid", "unknown")

    # AsyncSSH SSHServerChannel often doesn't expose get_line_mode/get_echo
    old_line_mode = True
    old_echo = True

    if hasattr(channel, "get_line_mode"):
        with suppress(Exception):
            old_line_mode = channel.get_line_mode()

    if hasattr(channel, "get_echo"):
        with suppress(Exception):
            old_echo = channel.get_echo()

    master_fd = None
    slave_fd = None
    stdin_file = None
    stdout_file = None
    local_proc = None
    monitor_task = None

    session.extra["terminal_old_line_mode"] = old_line_mode
    session.extra["terminal_old_echo"] = old_echo

    try:
        with suppress(Exception):
            process.stderr.write(f"Connecting to VM {vmid} (emulated with bash)...\r\n")

        channel.set_line_mode(False)
        channel.set_echo(False)

        master_fd, slave_fd = pty.openpty()

        local_proc = subprocess.Popen(
            ["bash", "-i"],
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            start_new_session=True,
            close_fds=True,
        )

        session.extra["terminal_proc"] = local_proc
        session.extra["terminal_master_fd"] = master_fd

        os.close(slave_fd)
        slave_fd = None

        stdin_file = os.fdopen(os.dup(master_fd), "wb", buffering=0)
        stdout_file = os.fdopen(os.dup(master_fd), "rb", buffering=0)

        term_size = get_normalized_terminal_size(process)
        if term_size:
            rows, cols, xpix, ypix = term_size
            set_winsize(master_fd, rows, cols, xpix, ypix)

        loop = asyncio.get_running_loop()
        monitor_task = asyncio.create_task(monitor_size(process, master_fd, local_proc))

        await process.redirect(
            stdin=stdin_file,
            stdout=stdout_file,
            stderr=stdout_file,
        )

        await loop.run_in_executor(None, local_proc.wait)

    except Exception as e:
        logger.exception("Terminal session error")
        with suppress(Exception):
            process.stderr.write(f"Terminal error: {e}\r\n")

    finally:
        if monitor_task:
            monitor_task.cancel()
            with suppress(Exception):
                await monitor_task

        if local_proc and local_proc.poll() is None:
            with suppress(ProcessLookupError):
                os.killpg(local_proc.pid, signal.SIGHUP)

            with suppress(Exception):
                local_proc.wait(timeout=1)

            if local_proc.poll() is None:
                with suppress(ProcessLookupError):
                    os.killpg(local_proc.pid, signal.SIGKILL)

        for f in (stdin_file, stdout_file):
            if f:
                with suppress(Exception):
                    f.close()

        if slave_fd is not None:
            with suppress(OSError):
                os.close(slave_fd)

        if master_fd is not None:
            with suppress(OSError):
                os.close(master_fd)

        with suppress(Exception):
            channel.set_line_mode(old_line_mode)

        with suppress(Exception):
            channel.set_echo(old_echo)

        session.extra["terminal_mode"] = False

        for key in [
            "terminal_proc",
            "terminal_master_fd",
            "terminal_old_line_mode",
            "terminal_old_echo",
            "terminal_vmid",
        ]:
            session.extra.pop(key, None)

        with suppress(BrokenPipeError, OSError, Exception):
            process.stdout.write("\r\nTerminal session ended. Returning to shell.\r\n")