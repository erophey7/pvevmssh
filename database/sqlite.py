import aiosqlite
from typing import Any, Optional, Union
from .connection import DatabaseConnection

class SQLiteConnection(DatabaseConnection):
    """Асинхронная реализация для SQLite."""

    def __init__(self, database: str, **kwargs):
        self.database = database
        self.kwargs = kwargs
        self.connection: Optional[aiosqlite.Connection] = None

    async def connect(self) -> None:
        try:
            self.connection = await aiosqlite.connect(self.database, **self.kwargs)
        except aiosqlite.Error as e:
            raise RuntimeError(f"Ошибка подключения к SQLite: {e}")

    async def close(self) -> None:
        if self.connection:
            await self.connection.close()
            self.connection = None

    async def get_connection(self) -> aiosqlite.Connection:
        if not self.connection:
            await self.connect()
        return self.connection

    async def get_cursor(self) -> aiosqlite.Cursor:
        conn = await self.get_connection()
        return await conn.cursor()

    async def execute(self, query: str, params: Optional[Union[tuple, dict]] = None) -> aiosqlite.Cursor:
        conn = await self.get_connection()
        if params:
            cursor = await conn.execute(query, params)
        else:
            cursor = await conn.execute(query)
        return cursor

    async def commit(self) -> None:
        if self.connection:
            await self.connection.commit()

    async def rollback(self) -> None:
        if self.connection:
            await self.connection.rollback()