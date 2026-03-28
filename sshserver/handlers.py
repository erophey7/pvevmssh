"""SSH connection handler — bootstrap and cleanup only."""

import logging
import asyncio

from sshserver.session.factory import create_session
from sshserver.terminal.base import Terminal
from sshserver.session.runtime import run_session
from sshserver.session.manager import SessionStore, current_session

logger = logging.getLogger(__name__)


async def handle_client(process):
    """
    Основная точка входа для новой SSH-сессии.
    Только bootstrap + cleanup. Вся логика создания сессии вынесена в factory.
    """
    session = None
    terminal = None

    try:
        session = await create_session(process)

        # Создаём терминальный слой
        terminal = Terminal(process)
        terminal.session = session
        session.extra["terminal"] = terminal

        # Переводим канал в raw-режим
        channel = process.channel
        try:
            if hasattr(channel, "set_line_mode"):
                channel.set_line_mode(False)
            if hasattr(channel, "set_echo"):
                channel.set_echo(False)
        except Exception:
            pass

        await terminal.start()

        # Запускаем основной цикл сессии
        await run_session(session, terminal)

    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.exception("Unexpected session error")
        if terminal is not None:
            try:
                await terminal.output.error_str(f"\r\nError: {e}\r\n")
            except Exception:
                pass
    finally:
            # === Cleanup ===
            try:
                # Сбрасываем контекстную переменную
                if current_session.get() is not None:
                    current_session.set(None)   

                # Удаляем сессию из глобального хранилища
                if session is not None:
                    SessionStore().remove(session.uuid)
                    logger.info("Session ended: %s (%s)", session.uuid, session.username)

            except Exception as e:
                logger.debug("Error during session cleanup: %s", e)

            # Останавливаем терминал
            if terminal is not None:
                try:
                    await terminal.stop()
                except Exception as e:
                    logger.debug("Error stopping terminal: %s", e)

            # Завершаем SSH процесс
            try:
                process.exit(0)
            except Exception:
                pass