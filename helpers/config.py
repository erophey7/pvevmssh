import json
from pathlib import Path
from helpers.path import Paths


########## Configuration Loader/Writer Class ##########
class Config:
    """
    ########## JSON-Based Configuration Manager ##########
    
    Provides methods to load, save, and manipulate configuration data stored in a JSON file.
    Supports nested configuration structures using dot notation for key access.
    """

    def __init__(self, path: Path = None):
        """
        ########## Configuration Initializer ##########
        
        Initializes the configuration manager with a specified file path.
        If the file doesn't exist, creates it with default values.
        
        Parameters:
            path (Path): Optional custom path for the configuration file
        """
        self.path = path or Paths.CONFIG_FILE
        self.data = {}
        if not self.path.exists():
            self._create_default()
        self.load()

    def _create_default(self):
        """
        ########## Create Default Configuration Structure ##########
        
        Initializes the configuration with default values for SSH and logging settings.
        Saves this structure to the configuration file.
        """
        self.data = {
            "ssh": {
                "bind": "0.0.0.0:22222",
                "host_key": str(Paths.SSH_HOST_KEY),
                "max_user_sessions": 10
            },
            "logger": {
                "level": "DEBUG"
            }
        }
        self.save()

    def load(self):
        """
        ########## Load Configuration from File ##########
        
        Reads the configuration data from the JSON file and stores it in memory.
        """
        with self.path.open("r", encoding="utf-8") as f:
            self.data = json.load(f)

    def save(self):
        """
        ########## Save Configuration to File ##########
        
        Writes the current in-memory configuration data to the JSON file.
        Ensures proper formatting and character encoding.
        """
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=4, ensure_ascii=False)

    def get(self, key: str, default=None):
        """
        ########## Retrieve Configuration Value by Dot Notation ##########
        
        Gets a value from the configuration using nested dot notation (e.g., 'ssh.bind').
        Returns the default value if the specified key doesn't exist.
        
        Parameters:
            key (str): Dot-separated path to the desired configuration value
            default: Default value to return if the key is not found
            
        Returns:
            Any: The requested configuration value or the default value
        """
        value = self.data
        for part in key.split("."):
            if not isinstance(value, dict):
                return default
            value = value.get(part)
            if value is None:
                return default
        return value

    def set(self, key: str, value):
        """
        ########## Set Configuration Value by Dot Notation ##########
        
        Sets a value in the configuration using nested dot notation (e.g., 'ssh.bind').
        Automatically creates any missing dictionary entries along the path.
        
        Parameters:
            key (str): Dot-separated path to the configuration value to set
            value: The new value to assign to the specified configuration key
        """
        d = self.data
        parts = key.split(".")
        for part in parts[:-1]:
            d = d.setdefault(part, {})
        d[parts[-1]] = value