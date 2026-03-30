from typing import Any, Optional, Union, List, Tuple, Dict
from .factory import DatabaseFactory
from .connection import DatabaseConnection


class Database:
    """
    Единый асинхронный API для работы с базой данных.
    Использует фабрику для создания подключения и предоставляет удобные методы.
    """

    def __init__(self, db_type: str, **config):
        """
        :param db_type: тип БД ('sqlite', 'mariadb', 'mysql')
        :param config: параметры подключения, зависящие от типа БД
        """
        self._db_type = db_type
        self._config = config
        self._connection: Optional[DatabaseConnection] = None

    async def connect(self) -> None:
        """Устанавливает соединение с БД."""
        self._connection = DatabaseFactory.create(self._db_type, **self._config)
        await self._connection.connect()

    async def close(self) -> None:
        """Закрывает соединение."""
        if self._connection:
            await self._connection.close()

    async def _ensure_connected(self) -> None:
        """Гарантирует, что соединение установлено."""
        if not self._connection:
            await self.connect()

    async def execute(
        self, query: str, params: Optional[Union[tuple, dict]] = None
    ) -> Any:
        """
        Выполняет SQL-запрос и возвращает курсор.
        Полезно для INSERT/UPDATE/DELETE или когда нужно обрабатывать курсор самостоятельно.
        """
        await self._ensure_connected()
        return await self._connection.execute(query, params)

    async def fetch_one(
        self, query: str, params: Optional[Union[tuple, dict]] = None
    ) -> Optional[Union[tuple, dict]]:
        """
        Выполняет SELECT и возвращает одну запись.
        Возвращает кортеж (для обычного курсора) или словарь, если настроено.
        """
        cursor = await self.execute(query, params)
        row = await cursor.fetchone()
        await cursor.close()
        return row

    async def fetch_all(
        self, query: str, params: Optional[Union[tuple, dict]] = None
    ) -> List[Union[tuple, dict]]:
        """
        Выполняет SELECT и возвращает все записи в виде списка.
        """
        cursor = await self.execute(query, params)
        rows = await cursor.fetchall()
        await cursor.close()
        return rows

    async def fetch_val(
        self, query: str, params: Optional[Union[tuple, dict]] = None
    ) -> Any:
        """
        Выполняет SELECT и возвращает первое поле первой записи.
        Удобно для получения скалярных значений (COUNT, SUM и т.п.).
        """
        row = await self.fetch_one(query, params)
        if row:
            return row[0]
        return None

    async def commit(self) -> None:
        """Фиксирует текущую транзакцию."""
        if self._connection:
            await self._connection.commit()

    async def rollback(self) -> None:
        """Откатывает текущую транзакцию."""
        if self._connection:
            await self._connection.rollback()

    async def __aenter__(self):
        """Поддержка async with: автоматически подключается."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Закрывает соединение при выходе из контекста."""
        if exc_type is not None:
            await self.rollback()
        await self.close()

    def transaction(self):
        """
        Возвращает контекстный менеджер транзакции.
        Использование:
            async with db.transaction():
                await db.execute(...)
        """
        return Transaction(self)


class Transaction:
    """Вспомогательный класс для управления транзакциями."""

    def __init__(self, db: "Database"):
        self._db = db

    async def __aenter__(self):
        # Транзакция начинается автоматически (БД в auto-commit?).
        # Для MySQL/MariaDB нужно отключить autocommit.
        # Сделаем явное начало транзакции.
        await self._db.execute("START TRANSACTION")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            await self._db.commit()
        else:
            await self._db.rollback()