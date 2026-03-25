"""
Команда terminal: подключение к последовательному порту виртуальной машины.
Создаёт полноценный PTY и передаёт управление дочернему процессу (bash).
Поддерживает изменение размера окна (SIGWINCH).
"""

import asyncio
import pty
import subprocess
import os
import fcntl
import termios
import signal
import struct
import logging
from sshserver.sessions import get_current_session

logger = logging.getLogger(__name__)


def set_winsize(fd: int, rows: int, cols: int, xpixels: int = 0, ypixels: int = 0) -> None:
    """Устанавливает размер окна PTY через ioctl."""
    winsize = struct.pack("HHHH", rows, cols, xpixels, ypixels)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)


async def terminal(username: str, *args):
    """
    Использование: terminal <vmid>
    Подключается к агенту на ноде, где находится VM, и передаёт данные терминала.
    """
    if not args:
        return "Usage: terminal <vmid>\n"

    vmid = args[0]
    session = get_current_session()
    if not session:
        return "No session found.\n"

    process = session.extra.get('process')
    if not process:
        return "No process found in session.\n"

    channel = process.channel
    if not channel:
        return "No channel available.\n"

    # Проверяем поддержку PTY
    if not (hasattr(channel, 'set_line_mode') and hasattr(channel, 'set_echo')):
        return "No PTY available (terminal mode not supported).\n"

    # Сохраняем текущие настройки
    try:
        old_line_mode = channel.get_line_mode()
    except AttributeError:
        old_line_mode = True
    try:
        old_echo = channel.get_echo()
    except AttributeError:
        old_echo = True

    try:
        process.stderr.write(f"Connecting to VM {vmid} (emulated with bash)...\n")

        # Отключаем line editor и echo
        channel.set_line_mode(False)
        channel.set_echo(False)

        # Создаём PTY
        master_fd, slave_fd = pty.openpty()

        # Запускаем bash с slave как терминал
        local_proc = subprocess.Popen(
            ["bash", "-i"],
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            start_new_session=True,
            close_fds=True,
        )
        os.close(slave_fd)                     # закрываем slave в родителе
        # Открываем master как обычные файлы
        stdin_file = open(master_fd, 'wb', buffering=0)
        stdout_file = open(master_fd, 'rb', buffering=0)

        # Устанавливаем начальный размер окна
        term_size = process.get_terminal_size()
        if term_size:
            rows, cols, xpix, ypix = term_size
            # Клиент передаёт (cols x rows), а PTY ожидает (rows, cols)
            set_winsize(master_fd, cols, rows, xpix, ypix)

        # Запускаем мониторинг изменения размера окна
        loop = asyncio.get_running_loop()
        monitor_task = asyncio.create_task(
            _monitor_size(process, master_fd, local_proc)
        )

        # Перенаправляем потоки SSH-сессии в PTY
        await process.redirect(
            stdin=stdin_file,
            stdout=stdout_file,
            stderr=stdout_file
        )

        # Ждём завершения bash
        await loop.run_in_executor(None, local_proc.wait)

        # Отменяем мониторинг
        monitor_task.cancel()
        await asyncio.gather(monitor_task, return_exceptions=True)

    except Exception as e:
        logger.exception("Terminal error")
        try:
            process.stderr.write(f"Terminal error: {e}\n")
        except:
            pass
    finally:
        # Восстанавливаем настройки
        try:
            channel.set_line_mode(old_line_mode)
        except:
            pass
        try:
            channel.set_echo(old_echo)
        except:
            pass
        # Выводим сообщение, игнорируя ошибки закрытого канала
        try:
            process.stdout.write("\nTerminal session ended. Returning to shell.\n")
        except (BrokenPipeError, OSError):
            pass
        # Возвращаем None, чтобы dispatcher не пытался писать ответ
        return None


async def _monitor_size(process, master_fd, local_proc):
    """Фоновая задача: отслеживает изменение размера окна и посылает SIGWINCH."""
    current_size = process.get_terminal_size()
    while local_proc.poll() is None:
        await asyncio.sleep(0.5)
        new_size = process.get_terminal_size()
        if new_size and new_size != current_size:
            current_size = new_size
            rows, cols, xpix, ypix = new_size
            # Клиент передаёт (cols x rows), а PTY ожидает (rows, cols)
            set_winsize(master_fd, cols, rows, xpix, ypix)
            try:
                os.kill(local_proc.pid, signal.SIGWINCH)
            except ProcessLookupError:
                break


command = {
    "name": "terminal",
    "help": "Open VM serial terminal",
    "func": terminal
}