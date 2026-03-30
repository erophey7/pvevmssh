from __future__ import annotations
import json
from typing import Any
from database.client import Database


class UserContext:
    """Удобный объект для работы с пользователем (api.user и api.get_user)."""

    def __init__(self, username: str, db: Database):
        self.username = username
        self._db = db

    async def get_field(self, field: str, default: Any = None):
        row = await self._db.fetch_one(
            f"SELECT {field} FROM users WHERE username = ?", (self.username,)
        )
        if not row or row[0] is None:
            return default
        return row[0]

    async def set_field(self, field: str, value: Any):
        await self._db.execute(
            f"UPDATE users SET {field} = ? WHERE username = ?",
            (value, self.username)
        )
        await self._db.commit()

    # === JSON-поля ===
    async def get_json(self, field: str, default: Any = None):
        raw = await self.get_field(field)
        return json.loads(raw) if raw else default or []

    async def set_json(self, field: str, data: Any):
        await self.set_field(field, json.dumps(data, ensure_ascii=False))

    # Удобные методы
    async def get_ssh_keys(self) -> list[str]:
        return await self.get_json("ssh_keys", [])

    async def set_ssh_keys(self, keys: list[str]):
        await self.set_json("ssh_keys", keys)

    async def get_history(self) -> list[dict]:
        return await self.get_json("history", [])

    async def set_history(self, history: list[dict]):
        await self.set_json("history", history)

    async def get_saved_env(self) -> dict:
        return await self.get_json("saved_env", {})

    async def set_saved_env(self, env: dict):
        await self.set_json("saved_env", env)