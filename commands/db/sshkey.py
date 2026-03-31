# commands/db/sshkey.py
"""
Manage SSH keys and optionally set a Proxmox API token.

This command uses the new CommandAPI style with built-in parser.
Documentation: see `new_command_api.md` section 7.1 (built-in parser).

The API token consists of:
- token_id (api_key) — stored in plain text.
- token_secret (api_secret) — stored encrypted via `api.db_encrypt()`.

When adding an SSH key, the user is prompted for the token secret
(if already configured in the database). The token is validated
against the Proxmox API before storage.

When the last SSH key is deleted, the stored token secret is cleared.
"""

import json
from typing import Optional

from pveapi import is_proxmox_token_valid
from helpers.globals import GlobalStore
from sshserver.commandapi import (
    CommandAPI,
    CommandArgumentError,
    CommandPermissionError,
    CommandAbort,
)


HELP = """Usage: sshkey <subcommand> [OPTIONS] [ARGS]

Manage SSH keys and optionally set a Proxmox API token.

Subcommands:
  list [--user USER]                       List SSH keys and token status
  add KEY [--user USER]                    Add SSH key (prompts for token secret)
  delete INDEX [--user USER]               Delete key by index (starting from 0)

Options:
  --user USER        Target user (requires db_admin if not yourself)
  -h, --help         Show this help

Permissions:
  - For your own user: requires db_user
  - For other users: requires db_admin

Examples:
  sshkey list
  sshkey list --user alice
  sshkey add "ssh-ed25519 AAAA..."
  sshkey delete 0
"""


async def execute(api: CommandAPI) -> str | None:
    # 1. Create parser using the built‑in api.parser()
    parser = api.parser("sshkey")
    parser.add_flag("-h", "--help", help="Show this help")

    # Subcommand: list
    p_list = parser.add_subcommand("list", help="List SSH keys")
    p_list.add_option("--user", help="Target username")

    # Subcommand: add
    p_add = parser.add_subcommand("add", help="Add SSH key")
    p_add.add_positional("key", help="SSH public key")
    p_add.add_option("--user", help="Target username")

    # Subcommand: delete
    p_del = parser.add_subcommand("delete", help="Delete SSH key by index")
    p_del.add_positional("index", help="Key index (0-based)")
    p_del.add_option("--user", help="Target username")

    # Parse arguments
    try:
        ns = parser.parse(api.args)
    except CommandArgumentError as e:
        return f"Argument error: {e}\n"

    if hasattr(ns, "help") and ns.help:
        return HELP

    # 2. Determine target user
    target_user = getattr(ns, "user", None) or api.username

    # 3. Permission checks
    if target_user != api.username:
        if not api.has_permission("db_admin"):
            raise CommandPermissionError(
                "db_admin required to modify other users"
            )

    # 4. Fetch user data from DB
    row = await api.fetch_one(
        "SELECT ssh_keys, api_key, api_secret FROM users WHERE username = ?",
        (target_user,)
    )
    if not row:
        return f"User {target_user} not found.\n"

    ssh_keys_raw, api_key, api_secret_enc = row
    try:
        ssh_keys = json.loads(ssh_keys_raw or "[]")
    except json.JSONDecodeError:
        ssh_keys = []

    # 5. Process subcommands
    if ns.subcommand == "list":
        lines = []
        if ssh_keys:
            lines.append(f"SSH keys for {target_user}:")
            for i, key in enumerate(ssh_keys):
                short = key[:80] + "..." if len(key) > 80 else key
                lines.append(f"{i}: {short}")
        else:
            lines.append(f"No SSH keys for {target_user}.")

        if api_key:
            lines.append(f"\nProxmox API token ID: {api_key} (secret stored)")
        else:
            lines.append("\nNo API token configured.")

        return "\n".join(lines) + "\n"

    elif ns.subcommand == "add":
        # --- Добавление SSH ключа ---
        if ns.key in ssh_keys:
            return f"Key already exists for {target_user}.\n"

        ssh_keys.append(ns.key)

        # --- Обработка API токена ---
        new_api_secret_enc = api_secret_enc

        # Если в БД уже есть api_key, запрашиваем секрет
        if api_key:
            # Защищённый ввод (пароль не отображается)
            token_secret = await api.read_line_secret(
                "Proxmox API token secret: "
            )
            if token_secret:
                # Получаем конфигурацию PVE для валидации
                config = GlobalStore.get().require("config")
                if not config:
                    return "Server configuration not available.\n"
                pve_cfg = config.get("pve", {})
                host = pve_cfg.get("main_node_host")
                if not host:
                    return "Proxmox host not configured.\n"
                verify_ssl = pve_cfg.get("ssl_verify", False)
                timeout = pve_cfg.get("timeout", 5)

                # Валидируем токен
                try:
                    valid = await is_proxmox_token_valid(
                        host, api_key, token_secret, verify_ssl, timeout
                    )
                except Exception as e:
                    api.logger.exception("Token validation failed")
                    return f"Error validating token: {e}\n"

                if not valid:
                    return "Invalid Proxmox API token.\n"

                # Шифруем и сохраняем новый секрет
                new_api_secret_enc = api.db_encrypt(token_secret)
                api.logger.info("API token secret updated for %s", target_user)
        else:
            # Нет api_key — предупреждаем, но продолжаем (токен не меняется)
            await api.write_warning(
                "No API token ID is configured. Token secret cannot be updated.\n"
                "Use a separate command to set up the token first.\n"
            )

        # Сохраняем изменения в БД (всегда обновляем ssh_keys, api_secret обновляем только если изменился)
        try:
            async with api.db.transaction():
                await api.execute(
                    "UPDATE users SET ssh_keys = ?, api_secret = ? WHERE username = ?",
                    (
                        json.dumps(ssh_keys, ensure_ascii=False),
                        new_api_secret_enc,
                        target_user,
                    ),
                )
        except Exception as e:
            api.logger.exception("Failed to add SSH key for %s", target_user)
            return f"Database error: {e}\n"

        api.logger.info("User %s added SSH key for %s", api.username, target_user)
        return f"SSH key added for {target_user}.\n"

    elif ns.subcommand == "delete":
        # --- Удаление SSH ключа ---
        try:
            idx = int(ns.index)
        except ValueError:
            return f"Invalid index: {ns.index} (must be a number)\n"

        if idx < 0 or idx >= len(ssh_keys):
            return f"Invalid index {idx}. Available indices: 0..{len(ssh_keys)-1}\n"

        removed = ssh_keys.pop(idx)

        # Если после удаления ключей не осталось, очищаем api_secret
        if not ssh_keys:
            new_api_secret_enc = None
            msg = " (last key removed, token secret cleared)"
        else:
            new_api_secret_enc = api_secret_enc
            msg = ""

        try:
            async with api.db.transaction():
                await api.execute(
                    "UPDATE users SET ssh_keys = ?, api_secret = ? WHERE username = ?",
                    (
                        json.dumps(ssh_keys, ensure_ascii=False),
                        new_api_secret_enc,
                        target_user,
                    ),
                )
        except Exception as e:
            api.logger.exception("Failed to delete SSH key for %s", target_user)
            return f"Database error: {e}\n"

        api.logger.info(
            "User %s deleted SSH key index %d for %s",
            api.username, idx, target_user
        )
        return f"SSH key #{idx} deleted for {target_user}.{msg}\n"

    else:
        return "Unknown subcommand.\n"


command = {
    "name": "sshkey",
    "help": "Manage SSH keys and optionally set a Proxmox API token",
    "func": execute,
    "permissions": [],   # Permissions are checked inside the command
}