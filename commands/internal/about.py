"""
About command — displays information about the server and current session.
"""

from helpers.globals import GlobalStore
from sshserver.session.manager import get_current_session, SessionStore


async def execute(username: str, *args) -> str:
    """
    Показывает информацию о сервере и текущей сессии.
    """
    config = GlobalStore.get().require("config")
    session = get_current_session()

    lines = [
        "╔══════════════════════════════════════════════════════════════╗",
        "║                   PVE SSH Server v0.2                        ║",
        "╚══════════════════════════════════════════════════════════════╝",
        "",
        f"User          : {username}",
        f"Group         : {session.extra.get('group_name', 'Unknown')} (ID: {session.extra.get('group', 0)})",
        f"Listen        : {config.get('ssh.bind', 'unknown')}",
        f"Auth method   : password (temporary)",
    ]

    if session:
        lines.extend([
            "",
            "Session Information:",
            f"  UUID          : {session.uuid}",
            f"  Client IP     : {session.client_addr}",
            f"  Terminal      : {session.term_type} • {session.term_width}x{session.term_height}",
            f"  Started       : {session.start_time:.0f}",
        ])

    # Количество активных сессий
    active_sessions = SessionStore().count()
    lines.append(f"  Active sessions : {active_sessions}")

    # Права пользователя
    user_perms = session.extra.get("permissions", set()) if session else set()
    if user_perms:
        lines.extend([
            "",
            "Your permissions:",
            f"  {', '.join(sorted(user_perms))}"
        ])
    else:
        lines.append("\nYou have no specific permissions (all commands allowed).")

    return "\n".join(lines)


# ==================== Command Definition ====================
command = {
    "name": "about",
    "help": "Show detailed information about the server and current session",
    "func": execute,
    # permissions не указываем — будет наследоваться от категории (internal)
}