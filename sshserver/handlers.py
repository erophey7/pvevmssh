import asyncssh
import asyncio
import logging
import os
import signal
import fcntl
import termios
import struct
from contextlib import suppress

from sshserver.dispatcher import CommandDispatcher
from sshserver.sessions import SessionInfo, SessionStore, current_session

logger = logging.getLogger(__name__)


def set_winsize(fd: int, rows: int, cols: int, xpixels: int = 0, ypixels: int = 0) -> None:
    winsize = struct.pack("HHHH", rows, cols, xpixels, ypixels)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)


def get_normalized_terminal_size(process):
    term_size = process.get_terminal_size()
    if not term_size:
        return None
    cols, rows, xpix, ypix = term_size
    return rows, cols, xpix, ypix


########## Read One Command Line in Shell Mode ##########
async def read_command_line(process) -> str | None:
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


########## PTY Relay: SSH -> PTY ##########
async def _relay_ssh_to_pty(process, session):
    master_fd = session.extra["terminal_master_fd"]
    local_proc = session.extra["terminal_proc"]

    try:
        while local_proc.poll() is None:
            try:
                data = await process.stdin.read(1024)
            except asyncssh.TerminalSizeChanged:
                continue
            except asyncio.CancelledError:
                break
            except (BrokenPipeError, OSError):
                break

            if not data:
                continue

            try:
                os.write(master_fd, data.encode() if isinstance(data, str) else data)
            except OSError:
                break
    except asyncio.CancelledError:
        pass


########## PTY Relay: PTY -> SSH ##########
async def _relay_pty_to_ssh(process, session):
    master_fd = session.extra["terminal_master_fd"]
    local_proc = session.extra["terminal_proc"]
    loop = asyncio.get_running_loop()

    try:
        while local_proc.poll() is None:
            try:
                data = await loop.run_in_executor(None, os.read, master_fd, 1024)
            except asyncio.CancelledError:
                break
            except OSError:
                break

            if not data:
                break

            try:
                process.stdout.write(data.decode(errors="replace"))
            except (BrokenPipeError, OSError):
                break
    except asyncio.CancelledError:
        pass


########## PTY Resize Monitor ##########
async def _monitor_terminal_size(process, session):
    master_fd = session.extra["terminal_master_fd"]
    local_proc = session.extra["terminal_proc"]

    current_size = get_normalized_terminal_size(process)

    while local_proc.poll() is None:
        await asyncio.sleep(0.3)
        new_size = get_normalized_terminal_size(process)

        if new_size and new_size != current_size:
            current_size = new_size
            rows, cols, xpix, ypix = new_size
            with suppress(Exception):
                set_winsize(master_fd, rows, cols, xpix, ypix)
            with suppress(ProcessLookupError):
                os.kill(local_proc.pid, signal.SIGWINCH)


########## Start PTY Mode ##########
async def start_terminal_mode(process, session):
    if session.extra.get("terminal_tasks_started"):
        return

    relay_in_task = asyncio.create_task(_relay_ssh_to_pty(process, session))
    relay_out_task = asyncio.create_task(_relay_pty_to_ssh(process, session))
    resize_task = asyncio.create_task(_monitor_terminal_size(process, session))

    session.extra["terminal_relay_in_task"] = relay_in_task
    session.extra["terminal_relay_out_task"] = relay_out_task
    session.extra["terminal_resize_task"] = resize_task
    session.extra["terminal_tasks_started"] = True


########## Wait for PTY Exit ##########
async def wait_terminal_mode(process, session):
    local_proc = session.extra.get("terminal_proc")
    if not local_proc:
        return
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, local_proc.wait)


########## Cleanup PTY ##########
async def cleanup_terminal(process, session):
    master_fd = session.extra.get("terminal_master_fd")
    local_proc = session.extra.get("terminal_proc")
    channel = process.channel

    # 1. Завершить PTY-процесс
    if local_proc and local_proc.poll() is None:
        with suppress(ProcessLookupError):
            os.killpg(local_proc.pid, signal.SIGHUP)

        try:
            await asyncio.get_running_loop().run_in_executor(
                None, lambda: local_proc.wait(timeout=1)
            )
        except Exception:
            if local_proc.poll() is None:
                with suppress(ProcessLookupError):
                    os.killpg(local_proc.pid, signal.SIGKILL)

    # 2. Закрыть master_fd
    if master_fd is not None:
        with suppress(OSError):
            os.close(master_fd)

    # 3. Отменить фоновые задачи
    tasks = [
        session.extra.get("terminal_relay_in_task"),
        session.extra.get("terminal_relay_out_task"),
        session.extra.get("terminal_resize_task"),
    ]
    for task in tasks:
        if task:
            task.cancel()

    if any(tasks):
        with suppress(Exception):
            await asyncio.gather(*[t for t in tasks if t], return_exceptions=True)

    # 4. Важное: выключаем terminal_mode
    session.extra["terminal_mode"] = False

    # 5. Восстановить line mode / echo
    old_line_mode = session.extra.get("terminal_old_line_mode", True)
    old_echo = session.extra.get("terminal_old_echo", True)

    with suppress(Exception):
        channel.set_line_mode(old_line_mode)
    with suppress(Exception):
        channel.set_echo(old_echo)

    # 6. Очистить terminal state
    for key in [
        "terminal_master_fd",
        "terminal_proc",
        "terminal_old_line_mode",
        "terminal_old_echo",
        "terminal_vmid",
        "terminal_relay_in_task",
        "terminal_relay_out_task",
        "terminal_resize_task",
        "terminal_tasks_started",
    ]:
        session.extra.pop(key, None)

    # 7. Сообщение о возврате
    with suppress(Exception):
        process.stdout.write("\r\nExited VM terminal. Returning to SSH shell...\r\n")


########## SSH Client Connection Handler ##########
async def handle_client(process: asyncssh.SSHServerProcess) -> None:
    username = process.get_extra_info("username")
    client_addr = process.get_extra_info("peername")[0] if process.get_extra_info("peername") else "unknown"
    term_type = process.term_type or "unknown"
    term_size = process.term_size or (0, 0, 0, 0)
    width, height, pixwidth, pixheight = term_size

    env = {"USER": username, "TERM": term_type, "PS1": ">>> "}

    session = SessionInfo(username=username, client_addr=client_addr,
                          term_type=term_type, term_width=width, term_height=height)
    session.extra["process"] = process
    session.extra["env"] = env
    session.extra["terminal_mode"] = False
    SessionStore().add(session)

    logger.info("Session started: %s (%s)", session.uuid, username)

    token = current_session.set(session)

    try:
        dispatcher = CommandDispatcher(username)

        # Shell-mode приветствие
        process.stdout.write(f"Welcome to PVE SSH Server, {username}!\r\n")
        process.stdout.write("Type 'help' for available commands.\r\n")

        while True:
            if session.extra.get("terminal_mode"):
                try:
                    await start_terminal_mode(process, session)
                    await wait_terminal_mode(process, session)
                finally:
                    if session.extra.get("terminal_mode"):
                        await cleanup_terminal(process, session)
                continue

            prompt = session.extra["env"].get("PS1", ">>> ")
            process.stdout.write(prompt)  # строка, не байты

            line = await read_command_line(process)
            if line is None:
                break
            line = line.strip()
            if not line:
                continue

            try:
                response = await dispatcher.handle(line)
                if response:
                    # commands могут вернуть bytes → декодируем
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
        with suppress(Exception):
            if session.extra.get("terminal_mode"):
                await cleanup_terminal(process, session)
    
        current_session.reset(token)
        SessionStore().remove(session.uuid)
        logger.info("Session ended: %s (%s)", session.uuid, username)
    
        try:
            # Выход только если shell завершился
            if not session.extra.get("terminal_mode"):
                process.exit(0)
        except Exception:
            pass