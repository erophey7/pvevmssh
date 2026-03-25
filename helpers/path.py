import os
from pathlib import Path
import asyncssh


########## Centralized Path Management Class ##########
class Paths:
    """
    ########## Path Management System ##########
    
    Provides a centralized way to access important directories and files
    for the SSH server application. All paths are resolved relative to
    the project root directory.
    """

    BASE_DIR = Path(__file__).resolve().parent.parent

    DATA_DIR = BASE_DIR / ".data"
    SSH_DIR = DATA_DIR / "ssh"
    LOG_DIR = DATA_DIR / "logs"
    CONFIG_DIR = DATA_DIR

    SSH_HOST_KEY = SSH_DIR / "ssh_host_key"
    CONFIG_FILE = CONFIG_DIR / "config.json"

    @staticmethod
    def init() -> None:
        """
        ########## Initialize Required Directories ##########
        
        Creates all necessary directories for the application to function properly.
        This includes data storage, SSH keys, and log directories.
        """
        Paths.SSH_DIR.mkdir(parents=True, exist_ok=True)
        Paths.DATA_DIR.mkdir(parents=True, exist_ok=True)
        Paths.LOG_DIR.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def ensure_ssh_host_key() -> None:
        """
        ########## Ensure SSH Host Key Exists ##########
        
        Generates an SSH host key file if it doesn't already exist.
        This is necessary for establishing secure SSH connections.
        """
        if Paths.SSH_HOST_KEY.exists():
            return
        print(f"[INIT] Generating SSH host key: {Paths.SSH_HOST_KEY}")
        key = asyncssh.generate_private_key("ssh-rsa")
        key.write_private_key(str(Paths.SSH_HOST_MY))
        Paths.SSH_HOST_KEY.chmod(0o600)
