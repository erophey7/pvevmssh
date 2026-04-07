"""Main execution loop for user SSH session."""

import logging

from sshserver.dispatcher import CommandDispatcher
from sshserver.terminal import EOF
from .prompt import expand_ps1

logger = logging.getLogger(__name__)


async def run_session(session, terminal) -> None:
    """
    Main session loop: prompt, read line, dispatch, output result.
    """
    username = session.username
    dispatcher = CommandDispatcher(username)

    env = session.extra.get("env")
    if env.get("HELLOMSG", False):
        hellomsg = env.substitute(env.get("HELLOMSG"))
        if not hellomsg.endswith(("\n", "\r")):
            hellomsg += "\r\n"
        await terminal.output.output_str(hellomsg)
    else:
        await terminal.output.output_str(f"Welcome to PVE SSH Server, {username}!\r\n")
        await terminal.output.output_str("Type 'help' for available commands.\r\n")

    while True:
        env = session.extra.get("env")
        prompt = env.get("PS1", ">>> ") if hasattr(env, "get") else ">>> "

        await terminal.output.output_str(expand_ps1(prompt, session, env))

        line = await terminal.input.read_str()

        try:
            line = env.substitute(line)
        except Exception as e:
            logger.debug("Substutution error: %s", e)

        if line is EOF:
            await terminal.output.output_str("\r\n")
            break

        if line is None:
            break

        line = line.strip()
        if not line:
            continue

        try:
            response = await dispatcher.handle(line)

            if response:
                if isinstance(response, bytes):
                    await terminal.output.output_bytes(response)
                    if not response.endswith((b"\n", b"\r\n")):
                        await terminal.output.output_str("\r\n")
                else:
                    resp_str = str(response)
                    await terminal.output.output_str(resp_str)
                    if not resp_str.endswith(("\n", "\r\n")):
                        await terminal.output.output_str("\r\n")

        except (BrokenPipeError, OSError):
            break
        except Exception as e:
            logger.exception("Command execution error")
            await terminal.output.error_str(f"\r\nCommand error: {e}\r\n")