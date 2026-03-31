# commands/db/sshkey.py
"""
Manage SSH keys and optionally set a Proxmox API token.

This command uses the new CommandAPI style with built-in parser.
Documentation: see `new_command_api.md` section 7.2 (built-in parser).

The API token consists of:
- token_id (api_key) — stored in plain text.
- token_secret (api_secret) — stored encrypted via `api.db_encrypt()`.

The token can be provided via the `--api-token` argument or interactively
(like sudo). When provided, it is validated against the Proxmox API before
storage.

The token is stored independently of SSH keys: it is never automatically
deleted, even when all SSH keys are removed.
"""

import json
import asyncio
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
  add KEY [--user USER] [--api-token TOKEN]   Add SSH key, optionally with API token
  delete INDEX [--user USER]               Delete key by index (starting from 0)

Options:
  --user USER        Target user (requires db_admin if not yourself)
  --api-token TOKEN  Proxmox API token in format "token_id=token_secret"
                     If omitted, the token secret will be requested interactively.
  -h, --help         Show this help

Permissions:
  - For your own user: requires db_user
  - For other users: requires db_admin

Examples:
  sshkey list
  sshkey list --user alice
  sshkey add "ssh-ed25519 AAAA..." --api-token "pve!user@realm=secret"
  sshkey add "ssh-ed25519 AAAA..."  # token will be asked interactively
  sshkey delete 0
"""


async def execute(api: CommandAPI) -> str | None:
    # 1. Create parser using the built‑in api.parser()
    parser = api.parser("sshkey")

    # Subcommand: list
    p_list = parser.add_subcommand("list", help="List SSH keys")
    p_list.add_argument("--user", help="Target username")

    # Subcommand: add
    p_add = parser.add_subcommand("add", help="Add SSH key")
    p_add.add_argument("key", help="SSH public key")
    p_add.add_argument("--user", help="Target username")
    p_add.add_argument("--api-token", help="Proxmox API token (token_id=token_secret)")

    # Subcommand: delete
    p_del = parser.add_subcommand("delete", help="Delete SSH key by index")
    p_del.add_argument("index", type=int, help="Key index")
    p_del.add_argument("--user", help="Target username")

    # Parse arguments (safe, never calls sys.exit)
    try:
        ns = parser.parse(api.args)
    except CommandArgumentError as e:
        return f"Argument error: {e}\n"

    if hasattr(ns, "help") and ns.help:
        return HELP

    # 4. Determine target user
    target_user = getattr(ns, "user", None) or api.username

    # 5. Permission checks
    if target_user != api.username:
        if not api.has_permission("db_admin"):
            raise CommandPermissionError(
                "db_admin required to modify other users"
            )

    # 6. Fetch user data from DB
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

    # 7. Process subcommands
    if ns.subcommand == "list":
        # Build output
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
        # Add SSH key
        if ns.key in ssh_keys:
            return f"Key already exists for {target_user}.\n"
        ssh_keys.append(ns.key)

        # Handle API token if requested
        new_api_key = api_key
        new_api_secret_enc = api_secret_enc

        if hasattr(ns, "api_token") and ns.api_token is not None:
            # Token provided via argument
            token_str = ns.api_token
        else:
            # No token argument – ask interactively
            await api.write("Proxmox API token (leave empty to skip): ")
            token_str = (await api.read_line()).strip()
            if not token_str:
                # User skipped token entry
                token_str = None

        if token_str:
            # Parse token into id and secret
            if "=" not in token_str:
                return "Invalid token format. Use: token_id=token_secret\n"
            token_id, token_secret = token_str.split("=", 1)

            # Get PVE configuration
            # TODO: use api.config when available
            config = GlobalStore.get().get("config")
            if not config:
                return "Server configuration not available.\n"
            pve_cfg = config.get("pve", {})
            host = pve_cfg.get("main_node_host")
            if not host:
                return "Proxmox host not configured.\n"
            verify_ssl = pve_cfg.get("ssl_verify", False)
            timeout = pve_cfg.get("timeout", 5)

            # Validate token
            try:
                valid = await is_proxmox_token_valid(
                    host, token_id, token_secret, verify_ssl, timeout
                )
            except Exception as e:
                api.logger.exception("Token validation failed")
                return f"Error validating token: {e}\n"

            if not valid:
                return "Invalid Proxmox API token.\n"

            # Store token: id plain, secret encrypted
            new_api_key = token_id
            new_api_secret_enc = api.db_encrypt(token_secret)
            api.logger.info("API token updated for %s", target_user)

        # Save changes to DB (always save SSH keys, even if token unchanged)
        try:
            async with api.db.transaction():
                await api.execute(
                    "UPDATE users SET ssh_keys = ?, api_key = ?, api_secret = ? WHERE username = ?",
                    (
                        json.dumps(ssh_keys, ensure_ascii=False),
                        new_api_key,
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
        # Delete SSH key by index
        if ns.index < 0 or ns.index >= len(ssh_keys):
            return f"Invalid index {ns.index}. Available indices: 0..{len(ssh_keys)-1}\n"
        removed = ssh_keys.pop(ns.index)

        # Do NOT delete api_key / api_secret – they are independent
        try:
            async with api.db.transaction():
                await api.execute(
                    "UPDATE users SET ssh_keys = ? WHERE username = ?",
                    (json.dumps(ssh_keys, ensure_ascii=False), target_user),
                )
        except Exception as e:
            api.logger.exception("Failed to delete SSH key for %s", target_user)
            return f"Database error: {e}\n"

        api.logger.info(
            "User %s deleted SSH key index %d for %s",
            api.username, ns.index, target_user
        )
        return f"SSH key #{ns.index} deleted for {target_user}.\n"

    else:
        # Should never happen because subcommand is required
        return "Unknown subcommand.\n"


command = {
    "name": "sshkey",
    "help": "Manage SSH keys and optionally set a Proxmox API token",
    "func": execute,
    "permissions": [],   # Permissions are checked inside the command
}