import asyncssh
import logging
from sshserver.dispatcher import CommandDispatcher
from sshserver.sessions import SessionInfo, SessionStore, current_session

logger = logging.getLogger(__name__)

async def handle_client(process: asyncssh.SSHServerProcess) -> None:
    username = process.get_extra_info("username")
    client_addr = process.get_extra_info("peername")[0] if process.get_extra_info("peername") else "unknown"
    term_type = process.term_type or "unknown"
    term_size = process.term_size or (0, 0, 0, 0)
    width, height, pixwidth, pixheight = term_size

    # Инициализация переменных окружения
    env = {
        'USER': username,
        'HOME': '/home/' + username,
        'SHELL': '/bin/bash',
        'TERM': term_type,
        'PS1': '>>> '   # по умолчанию
    }

    session = SessionInfo(
        username=username,
        client_addr=client_addr,
        term_type=term_type,
        term_width=width,
        term_height=height,
    )
    session.extra['process'] = process
    session.extra['env'] = env
    SessionStore().add(session)

    logger.info("Session started: %s (%s)", session.uuid, username)

    token = current_session.set(session)
    try:
        dispatcher = CommandDispatcher(username)

        # Приветствие
        process.stdout.write(f"Welcome to PVE SSH Server, {username}!\n")
        process.stdout.write("Type 'help' for available commands.\n")

        while True:
            # Выводим приглашение из PS1
            prompt = session.extra['env'].get('PS1', '>>> ')
            process.stdout.write(prompt)

            try:
                line = await process.stdin.readline()
            except asyncssh.TerminalSizeChanged as e:
                session.term_width = e.width
                session.term_height = e.height
                logger.debug("Terminal size changed: %dx%d", e.width, e.height)
                continue

            if not line:
                break
            line = line.rstrip("\n")
            if not line:
                continue

            response = await dispatcher.handle(line)
            process.stdout.write(response)
            process.stdout.write("\n")
    except asyncssh.BreakReceived:
        pass
    except Exception as e:
        logger.exception("Error in handle_client")
        process.stderr.write(f"\r\nError: {e}\r\n")
    finally:
        current_session.reset(token)
        SessionStore().remove(session.uuid)
        logger.info("Session ended: %s (%s)", session.uuid, username)
        process.exit(0)