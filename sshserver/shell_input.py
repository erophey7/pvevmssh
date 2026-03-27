import asyncssh


async def read_command_line(process) -> str | None:
    """
    Read one command line in normal shell mode.

    Returns:
        str   -> entered command
        ""    -> Ctrl+C
        None  -> EOF / shell exit
    """
    buffer = ""

    while True:
        try:
            chunk = await process.stdin.read(1)
        except asyncssh.TerminalSizeChanged:
            continue
        except (BrokenPipeError, OSError):
            return None

        if chunk == "":
            return None

        # Backspace / DEL
        if chunk in ("\x08", "\x7f"):
            if buffer:
                buffer = buffer[:-1]
            continue

        # Enter
        if chunk in ("\r", "\n"):
            return buffer

        # Ctrl+C
        if chunk == "\x03":
            process.stdout.write("^C\r\n")
            return ""

        # Ctrl+D at empty prompt = exit shell
        if chunk == "\x04":
            if not buffer:
                return None
            continue

        buffer += chunk