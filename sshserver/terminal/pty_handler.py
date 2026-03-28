import asyncio
import fcntl
import logging
import os
import pty
import signal
import struct
import termios
from contextlib import suppress

logger = logging.getLogger(__name__)


def _set_winsize(fd: int, rows: int, cols: int, xpixels: int = 0, ypixels: int = 0) -> None:
    winsize = struct.pack("HHHH", rows, cols, xpixels, ypixels)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)


class PTYHandler:
    """
    Управление единственным PTY внутри SSH-сессии.

    Этот PTY можно:
    - отдать subprocess
    - подключить к сокету
    - использовать как raw terminal backend
    """

    def __init__(self, session_io):
        self.session_io = session_io

        self.master_fd: int | None = None
        self.slave_fd: int | None = None
        self.owner_pid: int | None = None

        self._read_task: asyncio.Task | None = None
        self._write_task: asyncio.Task | None = None
        self._attached = False

    async def ensure(self):
        """Создать PTY, если ещё не создан"""
        if self.master_fd is not None and self.slave_fd is not None:
            return

        self.master_fd, self.slave_fd = pty.openpty()
        logger.debug("PTY created: master=%s slave=%s", self.master_fd, self.slave_fd)

        # При создании сразу применим текущий размер SSH-терминала
        process = self.session_io.process
        term_size = getattr(process, "term_size", None)

        if term_size:
            cols, rows, pixwidth, pixheight = term_size
            with suppress(Exception):
                _set_winsize(self.master_fd, rows, cols, pixwidth, pixheight)

    async def resize(self, rows: int, cols: int, xpixels: int = 0, ypixels: int = 0):
        """Изменить размер PTY"""
        if self.master_fd is None:
            return

        _set_winsize(self.master_fd, rows, cols, xpixels, ypixels)

        if self.owner_pid:
            with suppress(ProcessLookupError):
                os.kill(self.owner_pid, signal.SIGWINCH)

        logger.debug(
            "PTY resized: rows=%s cols=%s xpixels=%s ypixels=%s",
            rows, cols, xpixels, ypixels
        )

    async def attach_streams(self):
        """
        Прямой bridge:
        SSH input -> PTY
        PTY output -> SSH output
        """
        await self.ensure()

        if self._attached:
            return

        self._attached = True
        self._read_task = asyncio.create_task(self._pty_to_ssh())
        self._write_task = asyncio.create_task(self._ssh_to_pty())

    async def detach_streams(self):
        """Отключить bridge PTY <-> SSH"""
        self._attached = False

        for task in (self._read_task, self._write_task):
            if task:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task

        self._read_task = None
        self._write_task = None

    async def _pty_to_ssh(self):
        """PTY stdout -> SSH output"""
        loop = asyncio.get_running_loop()

        try:
            while self._attached and self.master_fd is not None:
                data = await loop.run_in_executor(None, os.read, self.master_fd, 4096)
                if not data:
                    break
                await self.session_io.output.output_bytes(data)

        except asyncio.CancelledError:
            raise

        except Exception as e:
            logger.exception("PTY -> SSH bridge error: %s", e)

    async def _ssh_to_pty(self):
        """SSH input -> PTY stdin"""
        loop = asyncio.get_running_loop()

        try:
            while self._attached and self.master_fd is not None:
                data = await self.session_io.input.read_bytes()
                if data is None:
                    break

                await loop.run_in_executor(None, os.write, self.master_fd, data)

        except asyncio.CancelledError:
            raise

        except Exception as e:
            logger.exception("SSH -> PTY bridge error: %s", e)

    def get_slave_fd(self) -> int | None:
        """Вернуть slave fd для subprocess/socket attach"""
        return self.slave_fd

    def set_owner_pid(self, pid: int | None):
        """PID процесса, которому надо слать SIGWINCH"""
        self.owner_pid = pid

    async def close(self):
        """Полная очистка PTY"""
        await self.detach_streams()

        for fd_name in ("master_fd", "slave_fd"):
            fd = getattr(self, fd_name)
            if fd is not None:
                with suppress(OSError):
                    os.close(fd)
                setattr(self, fd_name, None)

        self.owner_pid = None

        

    async def spawn(self, program: str, *args, env=None, cwd=None, attach_streams=True, **kwargs):
        """
        Запускает процесс с использованием PTY как управляющего терминала.

        Параметры:
            program (str): путь к исполняемому файлу
            *args: аргументы командной строки
            env (dict, optional): окружение для процесса (по умолчанию копия os.environ)
            cwd (str, optional): рабочая директория
            attach_streams (bool): если True, автоматически связывает SSH-потоки с PTY
            **kwargs: дополнительные параметры для asyncio.create_subprocess_exec
                        (например, limit, start_new_session и т.д.)

        Возвращает:
            asyncio.subprocess.Process: запущенный процесс
        """
        await self.ensure()
        slave_fd = self.slave_fd

        # Определяем функцию настройки терминала в дочернем процессе
        def _child_setup():
            os.setsid()
            fcntl.ioctl(slave_fd, termios.TIOCSCTTY, 0)
            # Если передан пользовательский preexec_fn, вызываем его
            user_preexec = kwargs.pop('preexec_fn', None)
            if user_preexec:
                user_preexec()

        # Подготавливаем окружение
        if env is None:
            process_env = os.environ.copy()
        else:
            process_env = env.copy()

        # Запускаем процесс
        proc = await asyncio.create_subprocess_exec(
            program, *args,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            env=process_env,
            cwd=cwd,
            pass_fds=(slave_fd,),
            preexec_fn=_child_setup,
            **kwargs
        )

        # Устанавливаем owner PID для SIGWINCH
        self.set_owner_pid(proc.pid)

        # При необходимости прикрепляем потоки SSH <-> PTY
        if attach_streams:
            await self.attach_streams()

        return proc