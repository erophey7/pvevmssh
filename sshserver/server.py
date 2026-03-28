"""SSH server bootstrap and connection handling."""

import asyncssh
import logging
import typing as t

from helpers.globals import GlobalStore
from helpers.path import Paths
from sshserver.handlers import handle_client
from sshserver.auth import authenticate


logger = logging.getLogger(__name__)


########## SSH Server Callbacks ##########
class PVESSHServer(asyncssh.SSHServer):
    """
    Custom SSH server with password and public‑key authentication.
    """

    def __init__(self) -> None:
        self._conn: t.Optional[asyncssh.SSHServerConnection] = None

    def connection_made(self, conn: asyncssh.SSHServerConnection) -> None:
        self._conn = conn
        logger.debug("Connection made")

    def connection_lost(self, exc: t.Optional[Exception]) -> None:
        logger.debug("Connection lost: %s", exc)

    def begin_auth(self, username: str) -> bool:
        logger.debug("begin_auth called for %s", username)
        return True

    def password_auth_supported(self) -> bool:
        return True

    def public_key_auth_supported(self) -> bool:
        return True

    async def validate_password(self, username: str, password: None) -> bool:
        logger.debug("validate_password called for %s", username)
        try_authenticate = await authenticate(username=username, password=password)
        return try_authenticate['status']

    async def validate_public_key(self, username: str, pkey: None) -> bool:
        logger.debug("validate_public_key called for %s", username)
        try_authenticate = await authenticate(username=username, pkey=pkey)
        return try_authenticate['status']


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