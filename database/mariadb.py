import aiomysql
from typing import Any, Optional, Union
from .connection import DatabaseConnection

class MariaDBConnection(DatabaseConnection):
    """Асинхронная реализация для MariaDB/MySQL с использованием aiomysql."""

    def __init__(self, host: str, user: str, password: str, database: str, port: int = 3306, **kwargs):
        self.host = host
        self.user = user
        self.password = password
        self.database = database
        self.port = port
        self.kwargs = kwargs
        self.pool: Optional[aiomysql.Pool] = None
        self.connection: Optional[aiomysql.Connection] = None  # необязательно, если используем пул

    async def connect(self) -> None:
        try:
            self.pool = await aiomysql.create_pool(
                host=self.host,
                user=self.user,
                password=self.password,
                db=self.database,
                port=self.port,
                **self.kwargs
            )
            # Получаем одно соединение из пула (опционально)
            self.connection = await self.pool.acquire()
        except aiomysql.Error as e:
            raise RuntimeError(f"Ошибка подключения к MariaDB/MySQL: {e}")

    async def close(self) -> None:
        if self.connection:
            await self.pool.release(self.connection)
            self.connection = None
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()
            self.pool = None

    async def get_connection(self) -> aiomysql.Connection:
        if not self.connection:
            # Если соединения нет, берём из пула
            if not self.pool:
                await self.connect()
            self.connection = await self.pool.acquire()
        return self.connection

    async def get_cursor(self) -> aiomysql.Cursor:
        conn = await self.get_connection()
        return await conn.cursor()

    async def execute(self, query: str, params: Optional[Union[tuple, dict]] = None) -> aiomysql.Cursor:
        conn = await self.get_connection()
        cursor = await conn.cursor()
        if params:
            await cursor.execute(query, params)
        else:
            await cursor.execute(query)
        return cursor

    async def commit(self) -> None:
        if self.connection:
            await self.connection.commit()

    async def rollback(self) -> None:
        if self.connection:
            await self.connection.rollback()