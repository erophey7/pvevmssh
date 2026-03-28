"""Core terminal handler for SSH session.

Orchestrates input, output, line editing and PTY management.
"""

import asyncio
import logging
from contextlib import suppress

import asyncssh

from .input_handler import InputHandler
from .output_handler import OutputHandler
from .pty_handler import PTYHandler
from sshserver.session.manager import get_current_session

logger = logging.getLogger(__name__)


class Terminal:
    """
    Главный терминал сессии.
    
    Содержит:
    - input_queue
    - InputHandler (с LineEditor)
    - OutputHandler
    - PTYHandler
    """

    def __init__(self, process):
        self.process = process

        self.input_queue: asyncio.Queue[bytes | None] = asyncio.Queue()
        self.output_lock = asyncio.Lock()

        # Компоненты терминала
        self.input = InputHandler(self)
        self.output = OutputHandler(self)
        self.pty = PTYHandler(self)

        self._input_task: asyncio.Task | None = None
        self._running = False

        # Ссылка на сессию будет установлена позже
        self.session = None

    async def start(self):
        """Запуск фонового чтения stdin → input_queue"""
        if self._running:
            return

        self._running = True
        self._input_task = asyncio.create_task(self._feed_input())

    async def stop(self):
        """Остановка терминала и очистка ресурсов"""
        self._running = False

        if self._input_task:
            self._input_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._input_task

        await self.pty.close()

        # Разбудить всех, кто ждёт ввода
        with suppress(Exception):
            await self.input_queue.put(None)

    async def _feed_input(self):
        """Фоновое чтение данных из SSH stdin"""
        try:
            while self._running:
                try:
                    data = await self.process.stdin.read(1024)

                except asyncssh.TerminalSizeChanged as exc:
                    await self._handle_terminal_resize(exc)
                    continue

                except (BrokenPipeError, OSError):
                    break

                except asyncio.CancelledError:
                    raise

                except Exception as e:
                    logger.exception("Input feed error: %s", e)
                    break

                if data in (b"", None, ""):
                    break

                if isinstance(data, str):
                    data = data.encode("utf-8", errors="replace")

                if data:
                    await self.input_queue.put(data)

        finally:
            self._running = False
            with suppress(Exception):
                await self.input_queue.put(None)

    async def _handle_terminal_resize(self, exc: asyncssh.TerminalSizeChanged):
        """Обработка изменения размера терминала"""
        try:
            cols = getattr(exc, "width", 80)
            rows = getattr(exc, "height", 24)
            pixwidth = getattr(exc, "pixwidth", 0)
            pixheight = getattr(exc, "pixheight", 0)
        except Exception:
            # fallback
            cols, rows, pixwidth, pixheight = 80, 24, 0, 0

        logger.info("Terminal resized: %dx%d", cols, rows)

        # Обновляем информацию в сессии
        session = get_current_session()
        if session:
            session.term_width = cols
            session.term_height = rows
            session.extra["term_pixwidth"] = pixwidth
            session.extra["term_pixheight"] = pixheight

        # Пробрасываем resize в PTY
        with suppress(Exception):
            await self.pty.resize(rows, cols, pixwidth, pixheight)