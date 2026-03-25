"""
########## Global Data Storage Singleton ##########
"""

class GlobalStore:
    """
    ########## Singleton Class for Global Data Management ##########
    
    Provides a centralized storage solution for global application data,
    including configuration settings, database connections, and other shared resources.
    """
    _instance = None

    def __init__(self) -> None:
        """
        ########## Singleton Initialization ##########
        
        Initializes the GlobalStore singleton. Ensures only one instance exists
        throughout the application lifecycle. Sets up an empty dictionary for storing global data.
        """
        if GlobalStore._instance is not None:
            raise RuntimeError("GlobalStore already initialized")
        self._storage: dict = {}
        GlobalStore._instance = self

    @classmethod
    def get(cls) -> "GlobalStore":
        """
        ########## Retrieve Singleton Instance ##########
        
        Returns the singleton instance of GlobalStore. Raises an error if the
        singleton hasn't been initialized yet.
        """
        if cls._instance is None:
            raise RuntimeError("GlobalStore is not initialized")
        return cls._instance

    def set(self, key: str, value: object) -> None:
        """
        ########## Store Value in Global Storage ##########
        
        Saves a value under the specified key in the global storage dictionary.
        This allows for easy access to shared data across different parts of the application.
        
        Parameters:
            key (str): The identifier used to retrieve this value later
            value (object): The data value to store globally
        """
        self._storage[key] = value

    def require(self, key: str) -> object:
        """
        ########## Retrieve Value from Global Storage ##########
        
        Gets a value from the global storage dictionary using the specified key.
        If the key doesn't exist, raises a KeyError to indicate that the requested
        data isn't available in the global store.
        
        Parameters:
            key (str): The identifier used to retrieve this value
        
        Returns:
            object: The stored data value
            
        Raises:
            KeyError: If the specified key does not exist in the storage
        """
        if key not in self._storage:
            raise KeyError(f"Global key not found: {key}")
        return self._storage[key]