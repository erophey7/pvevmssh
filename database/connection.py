import abc
from typing import Any, Optional, Union

class DatabaseConnection(abc.ABC):
    """Асинхронный абстрактный базовый класс для соединения с БД."""

    @abc.abstractmethod
    async def connect(self) -> None:
        """Устанавливает соединение."""
        pass

    @abc.abstractmethod
    async def close(self) -> None:
        """Закрывает соединение."""
        pass

    @abc.abstractmethod
    async def get_connection(self) -> Any:
        """Возвращает объект соединения (например, aiosqlite.Connection или aiomysql.Connection)."""
        pass

    @abc.abstractmethod
    async def get_cursor(self) -> Any:
        """Возвращает курсор для выполнения запросов."""
        pass

    @abc.abstractmethod
    async def execute(self, query: str, params: Optional[Union[tuple, dict]] = None) -> Any:
        """Выполняет SQL-запрос и возвращает результат (курсор)."""
        pass

    @abc.abstractmethod
    async def commit(self) -> None:
        """Фиксирует транзакцию."""
        pass

    @abc.abstractmethod
    async def rollback(self) -> None:
        """Откатывает транзакцию."""
        pass