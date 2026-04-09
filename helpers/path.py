"""Centralized path management."""

import os
from pathlib import Path
import asyncssh
import logging

logger = logging.getLogger(__name__)


class Paths:
    """
    Project paths, all relative to project root.
    """

    BASE_DIR = Path(__file__).resolve().parent.parent
    DATA_DIR = BASE_DIR / ".data"
    SSH_DIR = DATA_DIR / "ssh"
    LOG_DIR = DATA_DIR / "logs"

    LIBOQS_DEFAULT_PREFIX =  DATA_DIR / "liboqs"

    CONFIG_DIR = DATA_DIR
    SQLITE_DIR = DATA_DIR
    DB_MASTERKEY_DIR = DATA_DIR

    SSH_HOST_KEY = SSH_DIR / "ssh_host_key"
    CONFIG_FILE = CONFIG_DIR / "config.json"
    SQLITE_FILE = SQLITE_DIR / "database.db"
    DB_MASTERKEY_FILE = DB_MASTERKEY_DIR / "master.key"

    @staticmethod
    def init() -> None:
        """Create required directories."""
        try:
            Paths.DATA_DIR.mkdir(parents=True, exist_ok=True)
            Paths.SSH_DIR.mkdir(parents=True, exist_ok=True)
            Paths.SQLITE_DIR.mkdir(parents=True, exist_ok=True)
            Paths.DB_MASTERKEY_DIR.mkdir(parents=True, exist_ok=True)
            Paths.LOG_DIR.mkdir(parents=True, exist_ok=True)

            logger.debug("Directories initialized: %s, %s, %s",
                        Paths.DATA_DIR, Paths.SSH_DIR, Paths.LOG_DIR)
        except Exception as e:
            logger.error("Failed to create directories: %s", e)
            raise

    @staticmethod
    def ensure_ssh_host_key() -> None:
        """Generate an SSH host key if missing."""
        if Paths.SSH_HOST_KEY.exists():
            logger.debug("SSH host key already exists: %s", Paths.SSH_HOST_KEY)
            return

        try:
            logger.info("Generating new SSH host key: %s", Paths.SSH_HOST_KEY)

            key = asyncssh.generate_private_key("ssh-ed25519")
            key.write_private_key(str(Paths.SSH_HOST_KEY))

            Paths.SSH_HOST_KEY.chmod(0o600)

            logger.info("SSH host key successfully generated")
        except Exception as e:
            logger.error("Failed to generate SSH host key: %s", e)
            raise