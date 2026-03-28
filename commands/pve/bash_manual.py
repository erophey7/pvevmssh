# commands/pve/bash_manual.py
import asyncio
import os
import fcntl
import termios
import logging
from sshserver.session.manager import get_current_session

logger = logging.getLogger(__name__)

def _setup_pty(slave_fd: int):
    """В дочернем процессе: стать лидером сессии и назначить slave_fd управляющим терминалом."""
    os.setsid()
    fcntl.ioctl(slave_fd, termios.TIOCSCTTY, 0)

async def execute(username: str, *args) -> None:
    session = get_current_session()
    terminal = session.extra["terminal"]
    pty = terminal.pty
    env = session.extra["env"]

    await pty.ensure()
    slave_fd = pty.get_slave_fd()

    # Окружение для bash
    process_env = os.environ.copy()
    term = env.get("TERM")
    if term:
        process_env["TERM"] = term
    else:
        process_env.setdefault("TERM", "xterm-256color")

    # Присоединяем потоки SSH <-> PTY
    await pty.attach_streams()

    # Запускаем bash с настройкой управляющего терминала
    proc = await asyncio.create_subprocess_exec(
        "bash",
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        env=process_env,
        pass_fds=(slave_fd,),
        preexec_fn=lambda: _setup_pty(slave_fd),
    )

    # Устанавливаем owner PID для корректной обработки SIGWINCH
    pty.set_owner_pid(proc.pid)

    await proc.wait()
    await pty.detach_streams()
    return None

command = {
    "name": "bash",
    "help": "Start an interactive Bash shell (manual PTY setup)",
    "func": execute,
}