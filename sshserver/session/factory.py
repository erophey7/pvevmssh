"""Factory for creating and initializing user sessions."""

import logging

from .types import SessionInfo
from .environment import UserEnvironment
from .history import CommandHistory
from .manager import SessionStore, current_session
from .syntax_highlight import StyleContext
from sshserver.permissions import get_user_group, resolve_permissions
from sshserver.dispatcher import CommandDispatcher
from helpers.globals import GlobalStore

logger = logging.getLogger(__name__)


async def create_session(process) -> SessionInfo:
    """
    Build a fully initialized session object.
    """
    username = process.get_extra_info("username")
    client_addr = process.get_extra_info("peername")[0] if process.get_extra_info("peername") else "unknown"

    client_env: dict[str, str] = dict(process.env)

    term_type = getattr(process, "term_type", "unknown")
    colorterm = client_env.get("COLORTERM")
    term_modes  = getattr(process, "term_modes",  {})

    term_size = getattr(process, "term_size", (80, 24, 0, 0))
    width, height, pixwidth, pixheight = term_size

    dispatcher = CommandDispatcher(username)

    session = SessionInfo(
        username=username,
        dispatcher=dispatcher,
        client_addr=client_addr,
        term_type=term_type,
        colorterm=colorterm,
        term_width=width,
        term_height=height,
        term_pixwidth=pixwidth,
        term_pixheight=pixheight
    )

    config = GlobalStore.get().require("config")

    env = UserEnvironment(max_size=config.get("db.limits.env", 50), session=session)
    await env.load()
    history = CommandHistory(max_size=config.get("db.limits.history", 1000), session=session)
    await history.load()
    env.set("USER", username)
    env.set("TERM", term_type)
    env.set("COLORTERM", colorterm or "truecolor")
    env.set("PS1", env.get("PS1", config.get("env.default_prompt", ">>> ")))
    env.set("HOSTNAME", config.get("env.hostname", "pvevmssh"))

    session.extra["env"] = env
    session.extra["history"] = history
    session.extra["process"] = process

    style = StyleContext(session)
    session.extra["style"] = style


    if config.get(f"auth.force_group.{username}", None) is not None:
        user_group = int(config.get(f"auth.force_group.{username}"))
        logger.info("Session: user %s, group forced to %d", username, user_group)
    else:
        user_group = await get_user_group(username)
    user_permissions = resolve_permissions(user_group)

    groups = config.get("groups", {})
    group_info = groups.get(str(user_group), {})
    group_name = group_info.get("name", f"Group_{user_group}")

    session.extra["group"] = user_group
    session.extra["group_name"] = group_name
    session.extra["permissions"] = user_permissions
    session.extra["term_modes"] = term_modes
    session.extra["client_env"] = client_env
    session.extra["auth_method"] = process.get_extra_info("auth_method")

    SessionStore().add(session)
    current_session.set(session)

    logger.debug(
        "Session %s | client_env keys: %s | COLORTERM=%s",
        session.uuid[:8], list(client_env.keys()), colorterm
    )

    logger.info(
        "Session created: %s | user=%s | group=%s (%s) | permissions=%d",
        session.uuid[:8], username, user_group, group_name, len(user_permissions)
    )
    return session