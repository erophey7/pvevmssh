import logging

logger = logging.getLogger(__name__)

async def authenticate(username: str, password: str = None, key: str = None):
    logger.debug(f"Authenticating user: {username}, password: {password}")
    # Временная реализация: разрешаем любые логин/пароль
    return True