import logging

from sshserver.dispatcher import CommandDispatcher

logger = logging.getLogger(__name__)


async def run_session(session, session_io) -> None:
    """
    Основной цикл пользовательской SSH-сессии.
    """

    username = session.username
    dispatcher = CommandDispatcher(username)

    await session_io.output.output_str(f"Welcome to PVE SSH Server, {username}!\r\n")
    await session_io.output.output_str("Type 'help' for available commands.\r\n")

    while True:
        prompt = session.extra["env"].get("PS1", ">>> ")
        await session_io.output.output_str(prompt)

        line = await session_io.input.read_str()
        if line is None:
            break

        line = line.strip()
        if not line:
            continue

        try:
            response = await dispatcher.handle(line)

            if response:
                if isinstance(response, bytes):
                    await session_io.output.output_bytes(response)
                    if not response.endswith((b"\n", b"\r\n")):
                        await session_io.output.output_str("\r\n")
                else:
                    await session_io.output.output_str(response)
                    if not response.endswith(("\n", "\r\n")):
                        await session_io.output.output_str("\r\n")

        except (BrokenPipeError, OSError):
            break

        except Exception as e:
            logger.exception("Command execution error")
            await session_io.output.error_str(f"\r\nCommand error: {e}\r\n")