# commands/pve/bash.py
import asyncio
import os
from sshserver.session.manager import get_current_session

async def execute(username: str, *args) -> None:
    session = get_current_session()
    terminal = session.extra["terminal"]
    pty = terminal.pty
    env = session.extra["env"]

    # Создаём PTY, если ещё не создан
    await pty.ensure()

    # Базовое окружение – копия текущего окружения процесса
    process_env = os.environ.copy()

    # Устанавливаем TERM из сессии или по умолчанию
    term = env.get("TERM")
    if term:
        process_env["TERM"] = term
    else:
        process_env.setdefault("TERM", "xterm-256color")

    # Устанавливаем PS1, если задан
    ps1 = env.get("PS1")
    if ps1:
        process_env["PS1"] = ps1

    # Присоединяем SSH-потоки к PTY
    await pty.attach_streams()

    slave_fd = pty.get_slave_fd()

    # Запускаем bash, используя тот же slave_fd для stdin/out/err
    proc = await asyncio.create_subprocess_exec(
        "bash",
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        env=process_env,
        pass_fds=(slave_fd,),      # не закрывать дескриптор в дочернем процессе
    )

    await proc.wait()
    await pty.detach_streams()

    return None

command = {
    "name": "bash",
    "help": "Start an interactive Bash shell",
    "func": execute,
}