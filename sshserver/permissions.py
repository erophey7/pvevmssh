"""Permission and group resolution system."""

from typing import Set, Dict, Any
import logging

from helpers.globals import GlobalStore

logger = logging.getLogger(__name__)


def get_user_group(username: str) -> int:
    """
    Возвращает группу пользователя.
    
    Сейчас: всем выдаётся группа 0 (Administrator)
    В будущем: здесь будет запрос к базе данных.
    """
    # ==================== FUTURE DB LOOKUP ====================
    # TODO: Заменить на реальный запрос к БД
    # Пример:
    # async def get_group_from_db(username: str) -> int:
    #     return await db.fetchval("SELECT group_id FROM users WHERE username = $1", username)
    #
    # group_id = await get_group_from_db(username)
    # return group_id if group_id is not None else 2
    # ===========================================================

    # Временная заглушка — всем Administrator
    group_id = 0
    logger.debug("User '%s' assigned to group %s (Administrator) [temporary]", username, group_id)
    return group_id


def resolve_permissions(group_id: int) -> Set[str]:
    """Разрешает все права группы с учётом наследования через permset."""
    config = GlobalStore.get().require("config")
    groups: Dict[str, Any] = config.get("groups", {})   # ключи — строки

    if not groups:
        logger.warning("No 'groups' section found in configuration")
        return set()

    resolved: Set[str] = set()
    visited: Set[int] = set()

    def _collect(gid: int):
        if gid in visited:
            return
        visited.add(gid)

        # Ключи в конфиге — строки, поэтому конвертируем
        group = groups.get(str(gid))
        if not group:
            return

        resolved.update(group.get("permissions", []))

        for parent_id in group.get("permset", []):
            _collect(parent_id)

    _collect(group_id)
    return resolved


def has_permission(session, required_perm: str | list[str] | None) -> bool:
    """Проверяет, есть ли у пользователя требуемое право."""
    if not required_perm:
        return True

    user_perms: Set[str] = session.extra.get("permissions", set())

    if isinstance(required_perm, str):
        return required_perm in user_perms

    return bool(user_perms & set(required_perm))