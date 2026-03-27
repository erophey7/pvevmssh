import logging
import asyncio

from sshserver.sessions import SessionInfo, SessionStore, current_session
from sshserver.session_io.base import SessionIOHandler
from sshserver.session_runtime import run_session

logger = logging.getLogger(__name__)


async def handle_client(process):
    username = process.get_extra_info("username")
    client_addr = process.get_extra_info("peername")[0] if process.get_extra_info("peername") else "unknown"

    term_type = process.term_type or "unknown"
    term_size = process.term_size or (0, 0, 0, 0)
    width, height, _, _ = term_size

    session = SessionInfo(
        username=username,
        client_addr=client_addr,
        term_type=term_type,
        term_width=width,
        term_height=height,
    )

    session.extra["process"] = process
    session.extra["env"] = {
        "USER": username,
        "TERM": term_type,
        "PS1": ">>> ",
    }

    SessionStore().add(session)
    token = current_session.set(session)
    logger.info("Session started: %s (%s)", session.uuid, username)

    session_io = SessionIOHandler(process)
    session_io.session = session
    session.extra["io"] = session_io

    channel = process.channel

    try:
        if hasattr(channel, "set_line_mode"):
            channel.set_line_mode(False)
        if hasattr(channel, "set_echo"):
            channel.set_echo(False)
    except Exception:
        pass

    await session_io.start()

    try:
        await run_session(session, session_io)

    except asyncio.CancelledError:
        pass

    except Exception as e:
        logger.exception("Unexpected session error")
        try:
            await session_io.output.error_str(f"\r\nError: {e}\r\n")
        except Exception:
            pass

    finally:
        current_session.reset(token)
        SessionStore().remove(session.uuid)
        logger.info("Session ended: %s (%s)", session.uuid, username)

        try:
            await session_io.stop()
        except Exception:
            pass

        try:
            process.exit(0)
        except Exception:
            pass