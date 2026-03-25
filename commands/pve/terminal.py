"""
########## Terminal Command: Connect to VM Serial Port ##########
"""

import asyncio
import pty
import subprocess
import os
import fcntl
import termios
import signal
import struct
import logging
from sshserver.sessions import get_current_session

logger = logging.getLogger(__name__)


########## Helper Function for Setting Window Size ##########
def set_winsize(fd: int, rows: int, cols: int, xpixels: int = 0, ypixels: int = 0) -> None:
    """
    ########## Set Terminal Window Size ##########
    
    Sets the terminal window size using ioctl.
    This is necessary for proper terminal resizing support (SIGWINCH).
    """
    winsize = struct.pack("HHHH", rows, cols, xpixels, ypixels)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)


########## Main Terminal Command Implementation ##########
async def terminal(username: str, *args):
    """
    ########## Connect to VM Serial Port ##########
    
    Usage: terminal <vmid>
    This command connects to the serial port of a virtual machine,
    creating a full PTY (pseudo-terminal) and launching bash as the shell.
    Supports window resizing through SIGWINCH signal.
    """

    if not args:
        return "Usage: terminal <vmid>\n"

    vmid = args[0]
    session = get_current_session()
    if not session:
        return "No session found.\n"

    process = session.extra.get('process')
    if not process:
        return "No process found in session.\n"

    channel = process.channel
    if not channel:
        return "No channel available.\n"

    # ########## Check for PTY Support ##########
    try:
        has_pty = hasattr(channel, 'set_line_mode') and hasattr(channel, 'set_echo')
    except Exception as e:
        logger.error("Error checking PTY support: %s", e)
        return "No PTY available (terminal mode not supported).\n"

    if not has_pty:
        return "No PTY available (terminal mode not supported).\n"

    # ########## Save Current Terminal Settings ##########
    try:
        old_line_mode = channel.get_line_mode()
    except Exception as e:
        logger.warning("Error getting line mode: %s", e)
        old_line_mode = True

    try:
        old_echo = channel.get_echo()
    except Exception as e:
        logger.warning("Error getting echo status: %s", e)
        old_echo = True

    try:
        process.stderr.write(f"Connecting to VM {vmid} (emulated with bash)...\n")
        
        # ########## Disable Line Editor and Echo ##########
        channel.set_line_mode(False)
        channel.set_echo(False)

        # ########## Create PTY ##########
        master_fd, slave_fd = pty.openpty()

        # ########## Spawn Bash Process ##########
        local_proc = subprocess.Popen(
            ["bash", "-i"],
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            start_new_session=True,
            close_fds=True
        )
        os.close(slave_fd)  # Close slave in parent

        # ########## Open Master File Descriptors ##########
        stdin_file = open(master_fd, 'wb', buffering=0)
        stdout_file = open(master_fd, 'rb', buffering=0)

        # ########## Set Initial Window Size ##########
        term_size = process.get_terminal_size()
        if term_size:
            rows, cols, xpix, ypix = term_size
            set_winsize(master_fd, cols, rows, xpix, ypix)

        # ########## Start Monitoring Window Resizing ##########
        loop = asyncio.get_running_loop()
        monitor_task = asyncio.create_task(_monitor_size(process, master_fd, local_proc))

        # ########## Redirect SSH Streams to PTY ##########
        try:
            await process.redirect(
                stdin=stdin_file,
                stdout=stdout_file,
                stderr=stdout_file
            )
        except Exception as e:
            logger.error("Error redirecting streams: %s", e)
            pass

        # ########## Wait for Bash Process to Exit ##########
        await loop.run_in_executor(None, local_proc.wait)

        # ########## Cancel Monitoring Task ##########
        monitor_task.cancel()
        await asyncio.gather(monitor_task, return_exceptions=True)

    except Exception as e:
        logger.exception("Terminal error")
        try:
            process.stderr.write(f"Terminal error: {e}\n")
        except:
            pass
    finally:
        # ########## Restore Terminal Settings ##########
        try:
            channel.set_line_mode(old_line_mode)
        except:
            pass

        try:
            channel.set_echo(old_echo)
        except:
            pass

        # ########## Final Output ##########
        try:
            process.stdout.write("\nTerminal session ended. Returning to shell.\n")
        except (BrokenPipeError, OSError):
            pass


########## Helper Function for Monitoring Window Size Changes ##########
async def _monitor_size(process, master_fd, local_proc):
    """
    ########## Monitor Terminal Size Changes ##########
    
    This background task monitors changes in terminal size and sends SIGWINCH
    to the child process to ensure it adjusts properly.
    """

    current_size = process.get_terminal_size()
    while local_proc.poll() is None:
        await asyncio.sleep(0.5)
        new_size = process.get_terminal_size()
        if new_size and new_size != current_size:
            current_size = new_size
            rows, cols, xpix, ypix = new_size
            set_winsize(master_fd, cols, rows, xpix, ypix)
            try:
                os.kill(local_proc.pid, signal.SIGWINCH)
            except ProcessLookupError:
                break


########## Command Definition ##########
command = {
    "name": "terminal",
    "help": "Open VM serial terminal",
    "func": terminal
}
