"""Core terminal handler — orchestrates input, output, and PTY."""

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
    Main terminal for a session.
    Holds input queue, input/output handlers, and PTY.
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
        self.session = None

    ########## Lifecycle ##########
    async def start(self):
        """Start background reading from SSH stdin."""
        if self._running:
            return
        self._running = True
        self._input_task = asyncio.create_task(self._feed_input())

    async def stop(self):
        """Stop terminal and clean up resources."""
        self._running = False
        if self._input_task:
            self._input_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._input_task
        await self.pty.close()
        with suppress(Exception):
            await self.input_queue.put(None)

    ########## Input Feeder ##########
    async def _feed_input(self):
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

    ########## Terminal Resize Handling ##########
    async def _handle_terminal_resize(self, exc: asyncssh.TerminalSizeChanged):
        try:
            cols = getattr(exc, "width", 80)
            rows = getattr(exc, "height", 24)
            pixwidth = getattr(exc, "pixwidth", 0)
            pixheight = getattr(exc, "pixheight", 0)
        except Exception:
            cols, rows, pixwidth, pixheight = 80, 24, 0, 0

        logger.info("Terminal resized: %dx%d", cols, rows)

        session = get_current_session()
        if session:
            session.term_width = cols
            session.term_height = rows
            session.extra["term_pixwidth"] = pixwidth
            session.extra["term_pixheight"] = pixheight

        with suppress(Exception):
            await self.pty.resize(rows, cols, pixwidth, pixheight)