"""Global data storage singleton."""


class GlobalStore:
    """
    Singleton container for global objects (config, etc.).
    """

    _instance = None

    def __init__(self) -> None:
        if GlobalStore._instance is not None:
            raise RuntimeError("GlobalStore already initialized")
        self._storage: dict = {}
        GlobalStore._instance = self

    @classmethod
    def get(cls) -> "GlobalStore":
        if cls._instance is None:
            raise RuntimeError("GlobalStore is not initialized")
        return cls._instance

    def set(self, key: str, value: object) -> None:
        self._storage[key] = value

    def require(self, key: str) -> object:
        if key not in self._storage:
            raise KeyError(f"Global key not found: {key}")
        return self._storage[key]