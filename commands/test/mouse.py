from sshserver.commandapi import CommandAPI
from sshserver.session.manager import get_current_session
from sshserver.terminal.mouse_handler import MouseEvent


async def on_mouse_event(event: MouseEvent):
    msg = f"\r\n[Mouse] {event.state} btn={event.button} at ({event.x},{event.y})"
    if event.wheel:
        msg += f" wheel={event.wheel}"
    session = get_current_session()
    if session and "terminal" in session.extra:
        await session.extra["terminal"].output.output_str(msg)

def build_parser(parser):
    parser.description=command["help"]
    parser.add_argument("cmd", choices=["on", "off", "status"], help="on | off | status")
    parser.add_argument("mode", nargs="?", type=int, default=0, help="Mode for 'on' (0,2,3)")

async def execute(api: CommandAPI) -> str | None:
    parser = api.parser("mouse", description=command["help"])
    parsed_args = parser.parse_args(api.args)

    if parsed_args.cmd == "on":
        base = 1000 if parsed_args.mode == 0 else (1002 if parsed_args.mode == 2 else 1003)
        await api.mouse_enable([base, 1006])
        api.mouse.add_listener(on_mouse_event)
        return f"Mouse tracking ENABLED (mode {parsed_args.mode})"
    elif parsed_args.cmd == "off":
        await api.mouse_disable()
        api.mouse.remove_listener(on_mouse_event)
        return "Mouse tracking DISABLED"
    elif parsed_args.cmd == "status":
        return f"Active mouse modes: {sorted(api.mouse.active_modes)}" if api.mouse.active_modes else "Mouse tracking is OFF"
    return None


command = {
    "name": "mouse",
    "help": "Enable or disable mouse tracking",
    "func": execute,
    "permissions": ["tester_permission"],
    "build_parser": build_parser

}