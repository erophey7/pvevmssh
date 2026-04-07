"""User environment variable management."""

import json
import re
from typing import Dict, Optional, Literal

from helpers.globals import GlobalStore
from .manager import get_current_session
from .types import SessionInfo

import logging
logger = logging.getLogger(__name__)

LoadMode = Literal["replace", "merge"]
ClearStore = Literal["runtime", "db", "all"]


class UserEnvironment:
    """
    Manages environment variables for a user session.
    Supports setting, getting, unsetting, variable substitution,
    and database persistence.
    """

    def __init__(self, max_size: Optional[int] = None, session: SessionInfo = None):
        self._vars: Dict[str, str] = {}

        self._max_size = max_size
        self._session = session

    ########## Basic Operations ##########

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        return self._vars.get(key, default)

    def set(self, key: str, value: str) -> None:
        self._vars[key] = value

    def unset(self, key: str) -> None:
        self._vars.pop(key, None)

    def all(self) -> Dict[str, str]:
        return dict(self._vars)

    ########## Export Parsing ##########

    def export(self, line: str) -> str:
        """Parse 'VAR=value' line and set variable. Return formatted output."""

        if not line:
            return ""

        if '=' not in line:
            key = line
            if key in self._vars:
                return f"{key}={self._vars[key]}\n"
            else:
                return f"export: {key}: not set\n"

        key, value = line.split('=', 1)

        key = key.strip()

        if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
            value = value[1:-1]
            value = self._decode_escapes(value)

        elif len(value) >= 2 and value[0] == "'" and value[-1] == "'":
            # одинарные кавычки: сохранить буквально
            value = value[1:-1]

        else:
            value = self._decode_escapes(value)

        self._vars[key] = value
        return f"Environment variables set: {key}={value}\n"

    ########## Variable Substitution ##########

    def substitute(self, text: str) -> str:
        r"""Replace $VAR with the corresponding value (or empty if not set).

        Supports escaping:
            \$VAR -> $VAR
            \$    -> $
        """
        placeholder = "__ESCAPED_DOLLAR__"

        text = text.replace(r'\$', placeholder)

        def repl(match):
            var = match.group(1)
            return self._vars.get(var, '')

        text = re.sub(r'\$([A-Za-z_][A-Za-z0-9_]*)', repl, text)
        text = text.replace(placeholder, '$')

        return text

    ########## DB ##########

    async def load(self, username: str = None, mode: LoadMode = "replace") -> None:
        """
        Load environment from DB.

        mode:
            - replace: полностью заменить runtime env
            - merge: дозагрузить из БД поверх runtime
                     (значения из БД перезапишут существующие ключи)
        """
        db = GlobalStore.get().require("db")

        if username is None:
            if self._session is None:
                self._session = get_current_session()
            username = self._session.username

        row = await db.fetch_one(
            """
            SELECT saved_env
            FROM users
            WHERE username = ?
            """,
            (username,)
        )

        raw = "{}"
        if row:
            if isinstance(row, dict):
                raw = row.get("env", "{}") or "{}"
            else:
                raw = row[0] or "{}"

        try:
            data = json.loads(raw)
            if not isinstance(data, dict):
                data = {}
        except (json.JSONDecodeError, TypeError):
            data = {}

        # только строковые ключи/значения
        data = {
            str(k): str(v)
            for k, v in data.items()
            if isinstance(k, str)
        }

        if self._max_size is not None:
            items = list(data.items())[-self._max_size:]
            data = dict(items)

        if mode == "replace":
            self._vars = data.copy()
        elif mode == "merge":
            self._vars.update(data)
        else:
            raise ValueError(f"Unsupported load mode: {mode}")

        logger.debug(f"Loaded env from db {data}")

        return 

    async def save(self, username: str = None) -> None:
        """
        Save full runtime env to DB.
        No diff logic: full dump.
        """
        db = GlobalStore.get().require("db")

        if username is None:
            if self._session is None:
                self._session = get_current_session()
            username = self._session.username

        data = self._vars.copy()

        if self._max_size is not None:
            items = list(data.items())[-self._max_size:]
            data = dict(items)

        payload = json.dumps(data, ensure_ascii=False)

        async with db.transaction():
            await db.execute(
                """
                UPDATE users
                SET saved_env = ?
                WHERE username = ?
                """,
                (payload, username)
            )

    async def clear(self, username: str = None, store: ClearStore = "all") -> None:
        """
        Clear environment.

        store:
            - runtime: clear only in-memory env
            - db: clear only database env
            - all: clear both
        """
        db = GlobalStore.get().require("db")

        if store in ("runtime", "all"):
            self._vars.clear()

        if store in ("db", "all"):
            async with db.transaction():
                await db.execute(
                    """
                    UPDATE users
                    SET saved_env = '{}'
                    WHERE username = ?
                    """,
                    (username,)
                )

    ############ Helpers ###############
    @staticmethod
    def _decode_escapes(value: str) -> str:
        r"""
        Decode common shell-style escape sequences.
        Example:
            \\n -> newline
            \\t -> tab
            \\$ -> $
            \\\\ -> backslash
            \\" -> "
            \\' -> '
        """
        escapes = {
            r'\n': '\n',
            r'\t': '\t',
            r'\r': '\r',
            r'\\': '\\',
            r'\"': '"',
            r"\'": "'",
            r'\$': '$',
        }

        for src, dst in escapes.items():
            value = value.replace(src, dst)

        return value