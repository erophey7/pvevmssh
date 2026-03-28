"""
Centralized Path Management for the project.
Все пути считаются относительно корня проекта.
"""

import os
from pathlib import Path
import asyncssh
import logging

logger = logging.getLogger(__name__)


class Paths:
    """
    Централизованное управление путями в проекте.
    """

    # Определяем пути относительно helpers/path.py
    BASE_DIR = Path(__file__).resolve().parent.parent          # корень проекта (pvevmssh/)
    DATA_DIR = BASE_DIR / ".data"
    SSH_DIR = DATA_DIR / "ssh"
    LOG_DIR = DATA_DIR / "logs"
    CONFIG_DIR = DATA_DIR

    # Важные файлы
    SSH_HOST_KEY = SSH_DIR / "ssh_host_key"
    CONFIG_FILE = CONFIG_DIR / "config.json"

    @staticmethod
    def init() -> None:
        """
        Создаёт все необходимые директории при запуске приложения.
        """
        try:
            Paths.DATA_DIR.mkdir(parents=True, exist_ok=True)
            Paths.SSH_DIR.mkdir(parents=True, exist_ok=True)
            Paths.LOG_DIR.mkdir(parents=True, exist_ok=True)

            logger.debug("Directories initialized: %s, %s, %s", 
                        Paths.DATA_DIR, Paths.SSH_DIR, Paths.LOG_DIR)
        except Exception as e:
            logger.error("Failed to create directories: %s", e)
            raise

    @staticmethod
    def ensure_ssh_host_key() -> None:
        """
        Создаёт SSH host key, если его нет.
        """
        if Paths.SSH_HOST_KEY.exists():
            logger.debug("SSH host key already exists: %s", Paths.SSH_HOST_KEY)
            return

        try:
            logger.info("Generating new SSH host key: %s", Paths.SSH_HOST_KEY)

            # Генерируем ключ
            key = asyncssh.generate_private_key("ssh-ed25519")   # лучше ed25519, чем rsa
            key.write_private_key(str(Paths.SSH_HOST_KEY))

            # Устанавливаем правильные права
            Paths.SSH_HOST_KEY.chmod(0o600)

            logger.info("SSH host key successfully generated")
        except Exception as e:
            logger.error("Failed to generate SSH host key: %s", e)
            raise