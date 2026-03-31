"""
Mouse tracking control and event display.
"""

from sshserver.commandapi import CommandAPI, CommandArgumentError
from sshserver.session.manager import get_current_session
from sshserver.terminal.mouse_handler import MouseEvent


async def on_mouse_event(event: MouseEvent):
    """Обработчик событий мыши. Использует старый способ получения сессии."""
    msg = f"\r\n[Mouse] {event.state} btn={event.button} at ({event.x},{event.y})"
    if event.wheel:
        msg += f" wheel={event.wheel}"
    session = get_current_session()
    if session and "terminal" in session.extra:
        terminal = session.extra["terminal"]
        await terminal.output.output_str(msg)


async def execute(api: CommandAPI) -> str | None:
    mouse = api.mouse
    args = api.args

    if not args:
        return "Usage: mouse on [mode] | mouse off | mouse status"

    cmd = args[0].lower()

    if cmd == "on":
        mode = 0
        if len(args) > 1:
            try:
                mode = int(args[1])
                if mode not in (0, 2, 3):
                    return "Invalid mode. Use 0, 2, or 3."
            except ValueError:
                return "Mode must be a number (0, 2, 3)."

        base_mode = 1000 if mode == 0 else (1002 if mode == 2 else 1003)
        await api.mouse_enable([base_mode, 1006])
        mouse.add_listener(on_mouse_event)
        return f"Mouse tracking ENABLED (mode {mode}, base {base_mode})"

    elif cmd == "off":
        await api.mouse_disable()
        mouse.remove_listener(on_mouse_event)
        return "Mouse tracking DISABLED"

    elif cmd == "status":
        if mouse.active_modes:
            return f"Active mouse modes: {sorted(mouse.active_modes)}"
        else:
            return "Mouse tracking is OFF"

    else:
        return "Unknown command. Use on, off, or status."


command = {
    "name": "mouse",
    "help": "Enable or disable mouse tracking",
    "func": execute,
    "permissions": ["tester_permission"]
}