import json
from pathlib import Path
from helpers.path import Paths


class Config:
    """
    JSON configuration loader with dot‑notation access.
    """

    def __init__(self, path: Path = None):
        self.path = path or Paths.CONFIG_FILE
        self.data = {}
        if not self.path.exists():
            self._create_default()
        self.load()

    def _create_default(self):
        self.data = {
            "ssh": {
                "bind": "0.0.0.0:22222",
                "host_key": str(Paths.SSH_HOST_KEY),
                "max_user_sessions": 10
            },
            "logger": {
                "level": "DEBUG"
            },
            "db": {
                "type": "sqlite",
                "file": str(Paths.SQLITE_FILE),
                "masterkey_file": str(Paths.DB_MASTERKEY_FILE)
            },
            "auth": {
                "ssh_key_enabled": True,
                "password_enabled": True,
                "default_group": "2"
            },
            "pve": {
                "main_node_host": "https://example.com:8006",
                "ssl_verity": False,
                "timeout": 3
            },
            "groups": {
		        "0": {
		        	"name": "Administrator",
		        	"permissions": ["admin_permission"],   
		        	"permset": [1,2,3]         
		        },
		        "1": {
		        	"name": "Poweruser",
		        	"permissions": ["poweruser_permission"],
		        	"permset": [2]
		        },
		        "2": {
		        	"name": "User",
		        	"permissions": ["user_permission"],
		        	"permset": []
		        },
		        "3": {
		        	"name": "Tester",
		        	"permissions": ["tester_permission"],
		        	"permset": [1,2]
		        }

	        }
        }
        self.save()

    def load(self):
        with self.path.open("r", encoding="utf-8") as f:
            self.data = json.load(f)

    def save(self):
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=4, ensure_ascii=False)

    def get(self, key: str, default=None):
        """Retrieve value using dot notation, e.g. 'ssh.bind'."""
        value = self.data
        for part in key.split("."):
            if not isinstance(value, dict):
                return default
            value = value.get(part)
            if value is None:
                return default
        return value

    def set(self, key: str, value):
        """Set value using dot notation, creating intermediate dictionaries."""
        d = self.data
        parts = key.split(".")
        for part in parts[:-1]:
            d = d.setdefault(part, {})
        d[parts[-1]] = value