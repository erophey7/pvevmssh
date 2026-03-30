"""SSH server bootstrap and connection handling."""

import asyncssh
import logging
import typing as t

from helpers.globals import GlobalStore
from helpers.path import Paths
from sshserver.handlers import handle_client
from sshserver.auth import password_auth, key_auth


logger = logging.getLogger(__name__)


########## SSH Server Callbacks ##########
class PVESSHServer(asyncssh.SSHServer):
    """
    Custom SSH server with password and public‑key authentication.
    """

    def __init__(self) -> None:
        self._conn: t.Optional[asyncssh.SSHServerConnection] = None
        self._auth_mode = None
        self._username = None

    def connection_made(self, conn: asyncssh.SSHServerConnection) -> None:
        self._conn = conn
        logger.debug("Connection made")

    def connection_lost(self, exc: t.Optional[Exception]) -> None:
        logger.debug("Connection lost: %s", exc)

    def begin_auth(self, username: str) -> bool:
        logger.debug(f"begin_auth called for {username}")
        self._username = username

        if "@" in username:
            self._auth_mode = "password_only"
            logger.info(f"Auth mode for {username}: password only")
        else:
            self._auth_mode = "publickey_only"
            logger.info(f"Auth mode for {username}: public key only")

        return True

    def password_auth_supported(self) -> bool:
        config = GlobalStore.get().require("config")
        enabled = config.get("auth.password_enabled", True)

        if not enabled:
            logger.info("Password auth disabled by config")
            return False

        allowed = self._auth_mode == "password_only"

        if allowed:
            logger.info(f"Password auth enabled for {self._username}")
        else:
            logger.info(f"Password auth denied for {self._username}: key-only account")

        return allowed

    def keyboard_interactive_auth_supported(self) -> bool:
        config = GlobalStore.get().require("config")
        enabled = config.get("auth.password_enabled", True)

        if not enabled:
            logger.info("Keyboard-interactive auth disabled by config")
            return False

        allowed = self._auth_mode == "password_only"

        if allowed:
            logger.info(f"Keyboard-interactive auth enabled for {self._username}")
        else:
            logger.info(f"Keyboard-interactive auth denied for {self._username}: key-only account")

        return allowed

    def public_key_auth_supported(self) -> bool:
        config = GlobalStore.get().require("config")
        enabled = config.get("auth.ssh_key_enabled", True)

        if not enabled:
            logger.info("Public key auth disabled by config")
            return False

        allowed = self._auth_mode == "publickey_only"

        if allowed:
            logger.info(f"Public key auth enabled for {self._username}")
        else:
            logger.info(f"Public key auth denied for {self._username}: password-only account")

        return allowed

    async def validate_public_key(self, username: str, key) -> bool:
        logger.debug(f"validate_public_key called for {username}")

        if self._auth_mode != "publickey_only":
            logger.warning(f"Public key auth forbidden for {username}")
            return False

        result = await key_auth(username, key)
        return result.get("status", False)

    async def validate_password(self, username: str, password: str) -> bool:
        logger.debug(f"validate_password called for {username}")

        if self._auth_mode != "password_only":
            logger.warning(f"Password auth forbidden for {username}")
            return False

        result = await password_auth(username, password)
        return result.get("status", False)


########## Server Runner ##########
class SSHServerRunner:
    """
    Start and stop the SSH server.
    """

    def __init__(self) -> None:
        config = GlobalStore.get().require("config")
        self.bind = config.get("ssh.bind", "0.0.0.0:22222")
        self.host_key = config.get("ssh.host_key", str(Paths.SSH_HOST_KEY))

    async def start(self) -> None:
        host, port = self.bind.split(":")
        port = int(port)

        server = await asyncssh.create_server(
            PVESSHServer,
            host,
            port,
            server_host_keys=[self.host_key],
            process_factory=handle_client,
            encoding=None
        )

        logger.info("SSH server listening on %s", self.bind)
        await server.wait_closed()