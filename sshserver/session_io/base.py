import asyncio
import logging
from contextlib import suppress

import asyncssh

from sshserver.session_io.input_handler import InputHandler
from sshserver.session_io.output_handler import OutputHandler
from sshserver.session_io.pty_handler import PTYHandler
from sshserver.sessions import get_current_session

logger = logging.getLogger(__name__)


class SessionIOHandler:
    """
    Корневой обработчик IO сессии.

    Вся работа идёт в байтах.
    На его основе строятся:
    - input handler
    - output handler
    - PTY handler
    """

    def __init__(self, process):
        self.process = process

        self.input_queue: asyncio.Queue[bytes | None] = asyncio.Queue()
        self.output_lock = asyncio.Lock()

        self.input = InputHandler(self)
        self.output = OutputHandler(self)
        self.pty = PTYHandler(self)

        self._input_task: asyncio.Task | None = None
        self._running = False

    async def start(self):
        """Запуск фонового чтения stdin -> input_queue"""
        if self._running:
            return

        self._running = True
        self._input_task = asyncio.create_task(self._feed_input())

    async def stop(self):
        """Остановка IO handler"""
        self._running = False

        if self._input_task:
            self._input_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._input_task

        await self.pty.close()

        # Разбудить ожидающих читателей
        with suppress(Exception):
            await self.input_queue.put(None)

    async def _feed_input(self):
        """
        Фоновое чтение stdin SSH-сессии.

        ВАЖНО:
        - resize окна приходит через asyncssh.TerminalSizeChanged
        - это НЕ ошибка
        """
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

                if data in (b"", ""):
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
        """
        Обработка resize окна терминала.
        """
        try:
            cols, rows, pixwidth, pixheight = exc.width, exc.height, exc.pixwidth, exc.pixheight
        except AttributeError:
            # fallback на случай другой версии asyncssh
            try:
                cols, rows, pixwidth, pixheight = exc.args[0]
            except Exception:
                logger.warning("Failed to parse TerminalSizeChanged: %r", exc)
                return

        logger.info(
            "Terminal resized: cols=%s rows=%s px=%s py=%s",
            cols, rows, pixwidth, pixheight
        )

        session = get_current_session()
        if session:
            session.term_width = cols
            session.term_height = rows
            session.extra["term_pixwidth"] = pixwidth
            session.extra["term_pixheight"] = pixheight

        # Пробрасываем resize в PTY, если он сейчас существует
        with suppress(Exception):
            await self.pty.resize(rows, cols, pixwidth, pixheight)