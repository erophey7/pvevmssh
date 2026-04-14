from sshserver.commandapi import CommandAPI
from sshserver.session.manager import SessionStore


async def execute(api: CommandAPI) -> str | None:
    config = api.config
    session = api.session
    username = api.username

    lines = [
        "╔══════════════════════════════════════════════════════════════╗",
        "║                   PVE SSH Server v0.2                        ║",
        "╚══════════════════════════════════════════════════════════════╝",
        "",
        f"User          : {username}",
        f"Group         : {session.extra.get('group_name', 'Unknown')} (ID: {session.extra.get('group', 0)})",
        f"Listen        : {config.get('ssh.bind', 'unknown')}",
        f"Auth method   : {session.extra.get('auth_method', None)}",
    ]

    if session:
        lines.extend([
            "",
            "Session Information:",
            f"  UUID          : {session.uuid}",
            f"  Client IP     : {session.client_addr}",
            f"  Terminal      : {session.term_type} • {session.term_width}x{session.term_height} ({session.term_pixwidth}x{session.term_pixheight})",
            f"  Started       : {session.start_time:.0f}",
        ])

    active_sessions = SessionStore().count()
    lines.append(f"  Active sessions : {active_sessions}")

    user_perms = api.permissions
    if user_perms:
        lines.extend([
            "",
            "Your permissions:",
            f"  {', '.join(sorted(user_perms))}"
        ])
    else:
        lines.append("\nYou have no specific permissions (all commands allowed).")

    return "\n".join(lines)


command = {
    "name": "about",
    "help": "Show detailed information about the server and current session",
    "func": execute,
}