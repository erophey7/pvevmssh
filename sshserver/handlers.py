import asyncssh
import logging
from sshserver.dispatcher import CommandDispatcher
from sshserver.sessions import SessionInfo, SessionStore, current_session

logger = logging.getLogger(__name__)

########## SSH Client Connection Handler ##########
async def handle_client(process: asyncssh.SSHServerProcess) -> None:
    """
    ########## Main SSH Client Handling Function ##########
    
    Asynchronous function that handles an incoming SSH client connection.
    Initializes session data, processes commands, and manages the terminal session.
    
    Parameters:
        process (asyncssh.SSHServerProcess): The SSH server process for the current connection
    """

    # ########## Extract Connection Information ##########
    username = process.get_extra_info("username")
    client_addr = process.get_extra_info("peername")[0] if process.get_extra_info("peername") else "unknown"
    term_type = process.term_type or "unknown"
    term_size = process.term_size or (0, 0, 0, 0)
    width, height, pixwidth, pixheight = term_size

    # ########## Environment Initialization ##########
    env = {
        'USER': username,
        'TERM': term_type,
        'PS1': '>>> '   # Default prompt
    }

    # ########## Session Creation and Tracking ##########
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

    # ########## Set Current Session Context ##########
    token = current_session.set(session)
    try:
        dispatcher = CommandDispatcher(username)

        # ########## Welcome Message ##########
        process.stdout.write(f"Welcome to PVE SSH Server, {username}!\n")
        process.stdout.write("Type 'help' for available commands.\n")

        while True:
            # ########## Display Prompt ##########
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

            # ########## Command Processing ##########
            response = await dispatcher.handle(line)
            process.stdout.write(response)
            process.stdout.write("\n")
    except asyncssh.BreakReceived:
        pass
    except Exception as e:
        logger.exception("Error in handle_client")
        process.stderr.write(f"\r\nError: {e}\r\n")
    finally:
        # ########## Session Cleanup ##########
        current_session.reset(token)
        SessionStore().remove(session.uuid)
        logger.info("Session ended: %s (%s)", session.uuid, username)
        process.exit(0)