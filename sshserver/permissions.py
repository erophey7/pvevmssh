"""Permission and group resolution system."""

from typing import Set, Dict, Any
import logging

from helpers.globals import GlobalStore

logger = logging.getLogger(__name__)


########## Group Resolution ##########
async def get_user_group(username: str) -> int:
    """
    Return group ID for the user.
    """
    # TODO: Replace with real database query
    db = GlobalStore.get().require("db")
    group_id = await db.fetch_one(
        "SELECT group_id FROM users WHERE username = ?",
        (username,)
    )
    logger.debug("User '%s' assigned to group %s", username, group_id[0])
    return group_id[0]


########## Permission Resolution with Inheritance ##########
def resolve_permissions(group_id: int) -> Set[str]:
    """Resolve all permissions for a group, following permset inheritance."""
    config = GlobalStore.get().require("config")
    groups: Dict[str, Any] = config.get("groups", {})
    limited_inheritance: bool = config.get("auth.limited_inheritance", True) 

    if not groups:
        logger.warning("No 'groups' section found in configuration")
        return set()

    resolved: Set[str] = set()
    visited: Set[int] = set()

    def _collect(gid: int, parent: bool = False):
        if gid in visited:
            return
        visited.add(gid)

        group = groups.get(str(gid))
        if not group:
            return
                
        resolved.update(group.get("permissions", []))

        for parent_id in group.get("permset", []):
            if not parent:
                _collect(parent_id, limited_inheritance)

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