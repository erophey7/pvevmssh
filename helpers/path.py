import os
from pathlib import Path
import asyncssh


class Paths:
    """Централизованное управление путями к файлам и директориям."""

    BASE_DIR = Path(__file__).resolve().parent.parent

    DATA_DIR = BASE_DIR / ".data"
    SSH_DIR = DATA_DIR / "ssh"
    LOG_DIR = DATA_DIR / "logs"
    CONFIG_DIR = DATA_DIR

    SSH_HOST_KEY = SSH_DIR / "ssh_host_key"
    CONFIG_FILE = CONFIG_DIR / "config.json"

    @staticmethod
    def init() -> None:
        """Создаёт все необходимые директории."""
        Paths.SSH_DIR.mkdir(parents=True, exist_ok=True)
        Paths.DATA_DIR.mkdir(parents=True, exist_ok=True)
        Paths.LOG_DIR.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def ensure_ssh_host_key() -> None:
        """Генерирует host-ключ, если он отсутствует."""
        if Paths.SSH_HOST_KEY.exists():
            return
        print(f"[INIT] Generating SSH host key: {Paths.SSH_HOST_KEY}")
        key = asyncssh.generate_private_key("ssh-rsa")
        key.write_private_key(str(Paths.SSH_HOST_KEY))
        Paths.SSH_HOST_KEY.chmod(0o600)