"""SSH connection handler — bootstrap and cleanup only."""

import logging
import asyncio

from sshserver.session.factory import create_session
from sshserver.terminal.base import Terminal
from sshserver.session.runtime import run_session
from sshserver.session.manager import SessionStore, current_session

from sshserver.lsp_engine import LSPEngine
from sshserver.session.shell_lsp import ShellLSP

logger = logging.getLogger(__name__)


########## Main Session Entry Point ##########
async def handle_client(process):
    session = None
    terminal = None

    try:
        actual_username = process.get_extra_info("username")
        process.username = actual_username

        session = await create_session(process)

        terminal = Terminal(process)

        lsp_engine = LSPEngine()
        lsp_engine.add_client("shell", ShellLSP())
        lsp_engine.setup_default("shell")
        terminal.input.editor.set_lsp_engine(lsp_engine)

        terminal.session = session
        session.extra["terminal"] = terminal
        session.extra["lsp_engine"] = lsp_engine
        session.extra["auth_method"] = process.get_extra_info("auth_method")



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
        try:
            await session.extra.get("history").save()
        except Exception as e:
            logger.debug("Error during saving history: %s", e)
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