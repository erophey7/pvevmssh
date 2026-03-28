"""SSH connection handler — bootstrap and cleanup only."""

import logging
import asyncio

from sshserver.session.factory import create_session
from sshserver.terminal.base import Terminal
from sshserver.session.runtime import run_session
from sshserver.session.manager import SessionStore, current_session

logger = logging.getLogger(__name__)


########## Main Session Entry Point ##########
async def handle_client(process):
    session = None
    terminal = None

    try:
        session = await create_session(process)

        terminal = Terminal(process)
        terminal.session = session
        session.extra["terminal"] = terminal

        # Switch to raw mode to handle input ourselves
        channel = process.channel
        try:
            if hasattr(channel, "set_line_mode"):
                channel.set_line_mode(False)
            if hasattr(channel, "set_echo"):
                channel.set_echo(False)
        except Exception:
            pass

        await terminal.start()

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
        # Cleanup
        try:
            if current_session.get() is not None:
                current_session.set(None)

            if session is not None:
                SessionStore().remove(session.uuid)
                logger.info("Session ended: %s (%s)", session.uuid, session.username)

        except Exception as e:
            logger.debug("Error during session cleanup: %s", e)

        if terminal is not None:
            try:
                await terminal.stop()
            except Exception as e:
                logger.debug("Error stopping terminal: %s", e)

        try:
            process.exit(0)
        except Exception:
            pass