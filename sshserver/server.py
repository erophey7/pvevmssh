"""
########## SSH Server Startup: Authentication and Session Creation ##########
"""

import asyncssh
import logging
import typing as t

from helpers.globals import GlobalStore
from helpers.path import Paths
from sshserver.handlers import handle_client
from sshserver.auth import authenticate


logger = logging.getLogger(__name__)


########## PVESSHServer Class for SSH Connection Handling ##########
class PVESSHServer(asyncssh.SSHServer):
    """
    ########## SSH Server Handler Class ##########
    
    Custom SSH server class that handles authentication and session creation.
    Extends the asyncssh.SSHServer base class to provide Proxmox-specific functionality.
    """

    def __init__(self) -> None:
        self._conn: t.Optional[asyncssh.SSHServerConnection] = None

    def connection_made(self, conn: asyncssh.SSHServerConnection) -> None:
        """
        ########## Connection Established ##########
        
        Called when an SSH connection is successfully established.
        Stores the connection object for later use.
        """
        self._conn = conn
        logger.debug("Connection made")

    def connection_lost(self, exc: t.Optional[Exception]) -> None:
        """
        ########## Connection Lost ##########
        
        Called when the SSH connection is unexpectedly closed.
        Logs any exceptions that occurred during the connection.
        """
        logger.debug("Connection lost: %s", exc)

    def begin_auth(self, username: str) -> bool:
        """
        ########## Authentication Start ##########
        
        Called at the beginning of the authentication process.
        Returns True to allow continuing with authentication steps.
        """
        logger.debug("begin_auth called for %s", username)
        return True

    def password_auth_supported(self) -> bool:
        """
        ########## Password Authentication Support ##########
        
        Indicates that password-based authentication is supported by this server.
        """
        return True
    
    def public_key_auth_supported(self) -> bool:
        """
        ########## Password Authentication Support ##########
        
        Indicates that pulic-key-based authentication is supported by this server.
        """
        return True

    async def validate_password(self, username: str, password: None) -> bool:
        """
        ########## Password Validation ##########
        """
        logger.debug("validate_password called for %s", username)
        try_authenticate = await authenticate(username=username, password=password)

        return try_authenticate['status']
    
    async def validate_public_key(self, username: str, pkey: None) -> bool:
        """
        ########## Public Key Validation ##########
        """
        logger.debug("validate_public_key called for %s", username)
        try_authenticate = await authenticate(username=username, pkey=pkey)

        return try_authenticate['status']


########## SSH Server Runner Class ##########
class SSHServerRunner:
    """
    ########## SSH Server Execution Manager ##########
    
    Manages the lifecycle of the SSH server, including binding to a network interface,
    loading host keys, and starting the server listening for incoming connections.
    """

    def __init__(self) -> None:
        # ########## Load Configuration ##########
        config = GlobalStore.get().require("config")
        self.bind = config.get("ssh.bind", "0.0.0.0:22222")
        self.host_key = config.get("ssh.host_key", str(Paths.SSH_HOST_KEY))

    async def start(self) -> None:
        """
        ########## Start SSH Server ##########
        
        Initializes and starts the SSH server, binding it to the specified network interface
        and port. The server listens for incoming connections until explicitly shut down.
        """
        host, port = self.bind.split(":")
        port = int(port)

        # ########## Create SSH Server Instance ##########
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
