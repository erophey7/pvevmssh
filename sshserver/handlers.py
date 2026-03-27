import asyncssh
import logging
from contextlib import suppress

from sshserver.dispatcher import CommandDispatcher
from sshserver.sessions import SessionInfo, SessionStore, current_session
from sshserver.shell_input import read_command_line
from sshserver.terminal_runtime import run_terminal_session

logger = logging.getLogger(__name__)


async def handle_client(process: asyncssh.SSHServerProcess) -> None:
    username = process.get_extra_info("username")
    client_addr = process.get_extra_info("peername")[0] if process.get_extra_info("peername") else "unknown"
    term_type = process.term_type or "unknown"
    term_size = process.term_size or (0, 0, 0, 0)
    width, height, pixwidth, pixheight = term_size

    env = {
        "USER": username,
        "TERM": term_type,
        "PS1": ">>> ",
    }

    session = SessionInfo(
        username=username,
        client_addr=client_addr,
        term_type=term_type,
        term_width=width,
        term_height=height,
    )
    session.extra["process"] = process
    session.extra["env"] = env
    session.extra["terminal_mode"] = False

    SessionStore().add(session)
    logger.info("Session started: %s (%s)", session.uuid, username)

    token = current_session.set(session)

    try:
        dispatcher = CommandDispatcher(username)

        process.stdout.write(f"Welcome to PVE SSH Server, {username}!\r\n")
        process.stdout.write("Type 'help' for available commands.\r\n")

        while True:
            # ============================================================
            # Terminal mode
            # ============================================================
            if session.extra.get("terminal_mode"):
                await run_terminal_session(process, session)
                continue

            # ============================================================
            # Shell mode
            # ============================================================
            prompt = session.extra["env"].get("PS1", ">>> ")
            process.stdout.write(prompt)

            line = await read_command_line(process)
            if line is None:
                break

            line = line.strip()
            if not line:
                continue

            try:
                response = await dispatcher.handle(line)

                # If command switched us into terminal mode, don't print anything
                if session.extra.get("terminal_mode"):
                    continue

                if response:
                    if isinstance(response, bytes):
                        response = response.decode(errors="replace")

                    process.stdout.write(response)

                    if not response.endswith(("\n", "\r\n")):
                        process.stdout.write("\r\n")

            except (BrokenPipeError, OSError):
                break

            except Exception as e:
                logger.exception("Command execution error")
                try:
                    process.stderr.write(f"\r\nCommand error: {e}\r\n")
                except (BrokenPipeError, OSError):
                    break

    except asyncssh.BreakReceived:
        pass

    except Exception as e:
        logger.exception("Error in handle_client")
        try:
            process.stderr.write(f"\r\nError: {e}\r\n")
        except (BrokenPipeError, OSError):
            pass

    finally:
        current_session.reset(token)
        SessionStore().remove(session.uuid)
        logger.info("Session ended: %s (%s)", session.uuid, username)

        try:
            process.exit(0)
        except Exception:
            pass