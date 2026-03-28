"""Permission and group resolution system."""

from typing import Set, Dict, Any
import logging

from helpers.globals import GlobalStore

logger = logging.getLogger(__name__)


########## Group Resolution ##########
def get_user_group(username: str) -> int:
    """
    Return group ID for the user.
    Currently always 0 (Administrator) – to be replaced with DB lookup.
    """
    # TODO: Replace with real database query
    group_id = 0
    logger.debug("User '%s' assigned to group %s (Administrator) [temporary]", username, group_id)
    return group_id


########## Permission Resolution with Inheritance ##########
def resolve_permissions(group_id: int) -> Set[str]:
    """Resolve all permissions for a group, following permset inheritance."""
    config = GlobalStore.get().require("config")
    groups: Dict[str, Any] = config.get("groups", {})

    if not groups:
        logger.warning("No 'groups' section found in configuration")
        return set()

    resolved: Set[str] = set()
    visited: Set[int] = set()

    def _collect(gid: int):
        if gid in visited:
            return
        visited.add(gid)

        group = groups.get(str(gid))
        if not group:
            return

        resolved.update(group.get("permissions", []))

        for parent_id in group.get("permset", []):
            _collect(parent_id)

    _collect(group_id)
    return resolved


########## Permission Check ##########
def has_permission(session, required_perm: str | list[str] | None) -> bool:
    """Check if session's user has the required permission(s)."""
    if not required_perm:
        return True

    user_perms: Set[str] = session.extra.get("permissions", set())

    if isinstance(required_perm, str):
        return required_perm in user_perms

    return bool(user_perms & set(required_perm))