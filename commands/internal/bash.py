"""
Manual PTY setup for interactive bash.
"""

import asyncio
import os
import fcntl
import termios

from sshserver.commandapi import CommandAPI


def _setup_pty(slave_fd: int):
    """Make slave fd the controlling terminal in the child."""
    os.setsid()
    fcntl.ioctl(slave_fd, termios.TIOCSCTTY, 0)


async def execute(api: CommandAPI) -> None:
    env = api.env
    terminal = api.terminal
    pty = terminal.pty

    

    await pty.ensure()
    slave_fd = pty.get_slave_fd()

    # Собираем окружение для процесса
    process_env = os.environ.copy()
    term = env.get("TERM")
    if term:
        process_env["TERM"] = term
    else:
        process_env.setdefault("TERM", "xterm-256color")

    # получаем размеры окна
    process = terminal.process
    term_size = getattr(process, "term_size", None)
    cols, rows, pixwidth, pixheight = term_size

    # Синхронизируем размер окна
    if term_size:
        await pty.resize(rows, cols, pixwidth, pixheight)

    await api.write("\r\n")

    # Подключаем потоки PTY к SSH
    await pty.attach_streams()

    proc = await asyncio.create_subprocess_exec(
        "bash",
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        env=process_env,
        pass_fds=(slave_fd,),
        preexec_fn=lambda: _setup_pty(slave_fd),
    )

    pty.set_owner_pid(proc.pid)

    # Синхронизируем размер окна
    if term_size:
        await pty.resize(rows, cols, pixwidth, pixheight)

    await proc.wait()
    await pty.detach_streams()
    return None


command = {
    "name": "bash",
    "help": "Start an interactive Bash shell (manual PTY setup)",
    "func": execute,
    "permissions": ["system_permission", "admin_permission"]
}