"""
Глобальное хранилище для доступа к конфигурации и другим общим объектам.
"""

class GlobalStore:
    """
    Синглтон для хранения глобальных данных (конфиг, соединения с БД и т.п.).
    """
    _instance = None

    def __init__(self) -> None:
        if GlobalStore._instance is not None:
            raise RuntimeError("GlobalStore already initialized")
        self._storage: dict = {}
        GlobalStore._instance = self

    @classmethod
    def get(cls) -> "GlobalStore":
        """Возвращает экземпляр синглтона."""
        if cls._instance is None:
            raise RuntimeError("GlobalStore is not initialized")
        return cls._instance

    def set(self, key: str, value: object) -> None:
        """Сохраняет значение под ключом."""
        self._storage[key] = value

    def require(self, key: str) -> object:
        """Возвращает значение по ключу, выбрасывая ошибку, если его нет."""
        if key not in self._storage:
            raise KeyError(f"Global key not found: {key}")
        return self._storage[key]