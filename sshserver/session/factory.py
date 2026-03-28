"""Factory for creating and initializing user sessions."""

import logging

from .types import SessionInfo
from .environment import UserEnvironment
from .manager import SessionStore, current_session
from sshserver.permissions import get_user_group, resolve_permissions
from helpers.globals import GlobalStore

logger = logging.getLogger(__name__)


async def create_session(process) -> SessionInfo:
    """
    Build a fully initialized session object.
    """
    username = process.get_extra_info("username")
    client_addr = process.get_extra_info("peername")[0] if process.get_extra_info("peername") else "unknown"

    term_type = getattr(process, "term_type", "unknown")
    term_size = getattr(process, "term_size", (80, 24, 0, 0))
    width, height, _, _ = term_size

    session = SessionInfo(
        username=username,
        client_addr=client_addr,
        term_type=term_type,
        term_width=width,
        term_height=height,
    )

    env = UserEnvironment()
    env.set("USER", username)
    env.set("TERM", term_type)
    env.set("PS1", ">>> ")

    session.extra["env"] = env
    session.extra["process"] = process

    user_group = get_user_group(username)
    user_permissions = resolve_permissions(user_group)

    config = GlobalStore.get().require("config")
    groups = config.get("groups", {})
    group_info = groups.get(str(user_group), {})
    group_name = group_info.get("name", f"Group_{user_group}")

    session.extra["group"] = user_group
    session.extra["group_name"] = group_name
    session.extra["permissions"] = user_permissions

    SessionStore().add(session)
    current_session.set(session)

    logger.info(
        "Session created: %s | user=%s | group=%s (%s) | permissions=%d",
        session.uuid[:8], username, user_group, group_name, len(user_permissions)
    )
    return session