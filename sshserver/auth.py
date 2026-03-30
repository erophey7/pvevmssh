import logging
from typing import Dict, Any, Optional
import json
import asyncssh

from helpers.globals import GlobalStore
from helpers.path import Paths
from helpers.crypto import encrypt, decrypt

logger = logging.getLogger(__name__)


async def password_auth(username: str, password: str = None) -> Dict[str, Any]:
    """Аутентификация по паролю/API secret."""
    logger.debug(f"Password auth attempt for: {username}")

    db = GlobalStore.get().require("db")
    config = GlobalStore.get().require("config")

    if "@" not in username:
        return {
            "status": False,
            "reason": "username must contain '@'",
            "code": -1
        }

    striped_username = username.split("@", 1)[0].strip()
    api_key = username.strip()
    api_secret = password

    if not striped_username:
        return {
            "status": False,
            "reason": "invalid username"
        }

    if not api_secret:
        return {
            "status": False,
            "reason": "api secret not provided"
        }

    try:
        if not await _check_api_key(api_key=api_key, api_secret=api_secret):
            return {
                "status": False,
                "reason": "api_key don't correct"
            }
    except TypeError:
        return {
            "status": False,
            "reason": "api secret not provided"
        }
    except Exception as e:
        logger.exception(f"API validation failed for {api_key}: {e}")
        return {
            "status": False,
            "reason": "api validation failed"
        }

    # Проверяем, есть ли уже запись с таким api_key
    db_username_by_api = await db.fetch_val(
        "SELECT username FROM users WHERE api_key = ?",
        (api_key,)
    )

    if db_username_by_api == striped_username:
        return {
            "status": True,
            "actual_username": striped_username
        }

    # Проверяем, есть ли пользователь по username
    record = await db.fetch_one(
        "SELECT ssh_keys FROM users WHERE username = ?",
        (striped_username,)
    )

    if record:
        ssh_keys_raw = record[0]
        has_keys = _has_ssh_keys(ssh_keys_raw)

        await db.execute("""
            UPDATE users
            SET api_key = ?, api_secret = ?
            WHERE username = ?
        """, (
            api_key,
            encrypt(api_secret) if has_keys else None,
            striped_username
        ))
    else:
        default_group = int(config.get("auth.default_group", 0))

        await db.execute("""
            INSERT INTO users (username, api_key, group_id)
            VALUES (?, ?, ?)
        """, (striped_username, api_key, default_group))

    await db.commit()

    return {
        "status": True,
        "actual_username": striped_username
    }


async def key_auth(username: str, pkey) -> Dict[str, Any]:
    """SSH Public Key authentication with asyncssh comparison."""
    logger.debug(f"Public key auth attempt for user: {username}")

    db = GlobalStore.get().require("db")

    if "@" in username:
        return {"status": False, "reason": "only api_secret"}

    record = await db.fetch_one(
        "SELECT ssh_keys FROM users WHERE username = ?",
        (username,)
    )

    if not record:
        logger.warning(f"Key auth failed: user {username} not found")
        return {"status": False, "reason": "User not found"}

    ssh_keys_raw = record[0]
    saved_keys = _parse_ssh_keys(ssh_keys_raw)

    if not saved_keys:
        logger.warning(f"Key auth failed: user {username} has no keys")
        return {"status": False, "reason": "No public keys configured"}

    for saved_key_str in saved_keys:
        try:
            saved_key = asyncssh.import_public_key(saved_key_str.strip())
            if pkey == saved_key:
                logger.info(f"Public key authentication SUCCESS for {username}")
                return {"status": True, "actual_username": username}
        except Exception as e:
            logger.warning(f"Invalid stored SSH key for {username}: {e}")
            continue


    record = await db.fetch_one(
        "SELECT api_key, api_secret FROM users WHERE username = ?",
        (username,)
    )

    if record:
        stored_api_key = record[0]
        stored_api_secret = record[1]

        if stored_api_key and stored_api_secret:
            try:
                stored_api_secret = decrypt(stored_api_secret)

                if await _check_api_key(stored_api_key, stored_api_secret):
                    logger.info(f"Stored API credential check SUCCESS for {username}")
                    return {"status": True, "actual_username": username}
            except Exception as e:
                logger.warning(f"Stored API credential check failed for {username}: {e}")


    logger.warning(f"Public key auth FAILED for {username}")
    return {"status": False, "reason": "Public key not authorized"}


async def _check_api_key(api_key: str, api_secret: str) -> bool:
    """Временная заглушка проверки API-ключа."""
    if api_secret is None:
        raise TypeError("api_secret is None")
    return True


def _parse_ssh_keys(ssh_keys_raw: Optional[str]) -> list[str]:
    """
    Преобразует поле ssh_keys из БД в список ключей.

    Поддерживает:
    - None
    - ""
    - "[]"
    - JSON-массив строк
    - одиночную строку ключа
    """
    if ssh_keys_raw is None:
        return []

    if isinstance(ssh_keys_raw, list):
        return [k for k in ssh_keys_raw if isinstance(k, str) and k.strip()]

    if not isinstance(ssh_keys_raw, str):
        return []

    ssh_keys_raw = ssh_keys_raw.strip()

    if not ssh_keys_raw or ssh_keys_raw in ("[]", "null", "None"):
        return []

    try:
        parsed = json.loads(ssh_keys_raw)
        if isinstance(parsed, list):
            return [k for k in parsed if isinstance(k, str) and k.strip()]
        if isinstance(parsed, str) and parsed.strip():
            return [parsed.strip()]
    except Exception:
        pass

    # fallback: считаем, что в БД лежит один обычный ключ строкой
    return [ssh_keys_raw]


def _has_ssh_keys(ssh_keys_raw: Optional[str]) -> bool:
    """Есть ли у пользователя хотя бы один SSH-ключ."""
    return bool(_parse_ssh_keys(ssh_keys_raw))