# commands/db/sshkey.py
"""
Manage SSH keys and optionally set a Proxmox API token.
"""

import json
from pveapi import is_proxmox_token_valid
from helpers.globals import GlobalStore
from sshserver.commandapi import CommandAPI, CommandArgumentError, CommandPermissionError


async def execute(api: CommandAPI) -> str | None:
    parser = api.parser("sshkey", description="Manage SSH keys and optionally set a Proxmox API token")

    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # list
    p_list = subparsers.add_parser("list", help="List SSH keys")
    p_list.add_argument("--user", help="Target username")

    # add
    p_add = subparsers.add_parser("add", help="Add SSH key")
    p_add.add_argument("key", help="SSH public key")
    p_add.add_argument("--user", help="Target username")

    # delete
    p_del = subparsers.add_parser("delete", help="Delete SSH key by index")
    p_del.add_argument("index", help="Key index (0-based)")
    p_del.add_argument("--user", help="Target username")

    try:
        ns = parser.parse_args(api.args)
    except CommandArgumentError as e:
        return f"Argument error: {e}\n"

    target_user = ns.user or api.username

    if target_user != api.username and not api.has_permission("db_admin"):
        raise CommandPermissionError("db_admin required to modify other users")

    row = await api.fetch_one(
        "SELECT ssh_keys, api_key, api_secret FROM users WHERE username = ?",
        (target_user,)
    )
    if not row:
        return f"User {target_user} not found.\n"

    ssh_keys_raw, api_key, api_secret_enc = row
    ssh_keys = json.loads(ssh_keys_raw or "[]")

    if ns.subcommand == "list":
        lines = [f"SSH keys for {target_user}:"] if ssh_keys else [f"No SSH keys for {target_user}."]
        for i, key in enumerate(ssh_keys):
            short = key[:80] + "..." if len(key) > 80 else key
            lines.append(f"{i}: {short}")
        lines.append(f"\nProxmox API token ID: {api_key} (secret stored)" if api_key else "\nNo API token configured.")
        return "\n".join(lines) + "\n"

    elif ns.subcommand == "add":
        if ns.key in ssh_keys:
            return f"Key already exists for {target_user}.\n"
        ssh_keys.append(ns.key)

        new_api_secret_enc = api_secret_enc
        if api_key:
            token_secret = await api.read_line_secret("Proxmox API token secret: ")
            if token_secret:
                config = GlobalStore.get().require("config")
                pve_cfg = config.get("pve", {})
                host = pve_cfg.get("main_node_host")
                if not host:
                    return "Proxmox host not configured.\n"
                valid = await is_proxmox_token_valid(
                    host, api_key, token_secret,
                    pve_cfg.get("ssl_verify", False),
                    pve_cfg.get("timeout", 5)
                )
                if not valid:
                    return "Invalid Proxmox API token.\n"
                new_api_secret_enc = api.db_encrypt(token_secret)

        async with api.db.transaction():
            await api.execute(
                "UPDATE users SET ssh_keys = ?, api_secret = ? WHERE username = ?",
                (json.dumps(ssh_keys, ensure_ascii=False), new_api_secret_enc, target_user)
            )
        return f"SSH key added for {target_user}.\n"

    elif ns.subcommand == "delete":
        try:
            idx = int(ns.index)
        except ValueError:
            return f"Invalid index: {ns.index}\n"
        if idx < 0 or idx >= len(ssh_keys):
            return f"Invalid index {idx}. Available: 0..{len(ssh_keys)-1}\n"

        ssh_keys.pop(idx)
        new_secret = None if not ssh_keys else api_secret_enc

        async with api.db.transaction():
            await api.execute(
                "UPDATE users SET ssh_keys = ?, api_secret = ? WHERE username = ?",
                (json.dumps(ssh_keys, ensure_ascii=False), new_secret, target_user)
            )
        msg = " (last key removed, token secret cleared)" if not ssh_keys else ""
        return f"SSH key #{idx} deleted for {target_user}.{msg}\n"

    return "Unknown subcommand.\n"


command = {
    "name": "sshkey",
    "help": "Manage SSH keys and optionally set a Proxmox API token",
    "func": execute,
    "permissions": [],
}