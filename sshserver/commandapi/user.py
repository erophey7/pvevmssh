from __future__ import annotations
import json
from typing import Any

from database.client import Database


class UserContext:
    """Удобный контекст пользователя с кэшированием данных из таблицы users."""

    def __init__(self, username: str, db: Database):
        self.username = username
        self._db = db
        self._cache: dict[str, Any] = {}

    async def get_field(self, field: str, default: Any = None) -> Any:
        """Получить сырое значение поля из таблицы users."""
        # реализация через self._db.fetch_one(...)
        pass  # будет заполнена при необходимости

    async def set_field(self, field: str, value: Any) -> None:
        """Сохранить значение поля."""
        pass

    async def get_json(self, field: str, default: Any = None) -> Any:
        """Получить JSON-поле (ssh_keys, history, saved_env)."""
        raw = await self.get_field(field)
        return json.loads(raw) if raw else (default or {})

    async def set_json(self, field: str, data: Any) -> None:
        """Сохранить данные как JSON."""
        await self.set_field(field, json.dumps(data, ensure_ascii=False))

    # Удобные шорткаты
    async def get_ssh_keys(self) -> list[str]:
        return await self.get_json("ssh_keys", [])

    async def set_ssh_keys(self, keys: list[str]) -> None:
        await self.set_json("ssh_keys", keys)

    async def get_history(self) -> list[dict]:
        return await self.get_json("history", [])

    async def set_history(self, history: list[dict]) -> None:
        await self.set_json("history", history)