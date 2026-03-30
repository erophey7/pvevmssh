class PVEAPIError(Exception):
    """Базовое исключение для ошибок API Proxmox."""
    pass

class AuthenticationError(PVEAPIError):
    """Ошибка аутентификации."""
    pass

class APIRequestError(PVEAPIError):
    """Ошибка при выполнении запроса к API."""
    pass