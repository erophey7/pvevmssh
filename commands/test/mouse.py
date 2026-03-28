"""
Mouse control command.
Usage: mouse on | mouse off
"""

from sshserver.session.manager import get_current_session
from sshserver.terminal.mouse_handler import MouseEvent
import asyncio


async def on_mouse_event(event: MouseEvent):
    """Пример обработчика — выводит информацию о событии мыши прямо в терминал"""
    msg = f"\r\n[Mouse] {event.state} btn={event.button} at ({event.x},{event.y})"

    session = get_current_session()
    if session and "terminal" in session.extra:
        terminal = session.extra["terminal"]
        await terminal.output.output_str(msg)


async def execute(username: str, *args) -> str:
    session = get_current_session()
    if not session or "terminal" not in session.extra:
        return "Error: Cannot access terminal"

    terminal = session.extra["terminal"]
    mouse = terminal.input.mouse

    if not args or args[0].lower() == "on":
        await mouse.enable(1006)
        mouse.add_listener(on_mouse_event)
        return "Mouse tracking ENABLED (SGR 1006)\nTry clicking or moving the mouse in the terminal."
    else:
        await mouse.disable()
        # Опционально: удаляем слушателя
        mouse.remove_listener(on_mouse_event)
        return "Mouse tracking DISABLED"


command = {
    "name": "mouse",
    "help": "Enable or disable mouse tracking (mouse on | mouse off)",
    "func": execute,
    "permissions": []
}