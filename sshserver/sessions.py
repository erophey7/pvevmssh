import contextvars
import uuid
from dataclasses import dataclass, field
from typing import Optional, Dict
import time

########## Session Information Data Class ##########
@dataclass
class SessionInfo:
    """
    ########## Session Information Data Class ##########
    
    Stores information about an active SSH session.
    
    Attributes:
        uuid (str): Unique identifier for the session (auto-generated)
        username (str): Username of the connected client
        client_addr (str): IP address of the connecting client
        term_type (str): Terminal type used by the client
        term_width (int): Width of the terminal in characters
        term_height (int): Height of the terminal in lines
        start_time (float): Timestamp when the session was created
        extra (Dict): Dictionary for storing additional session metadata
    """
    uuid: str = field(default_factory=lambda: str(uuid.uuid4()))
    username: str = ""
    client_addr: str = ""
    term_type: str = ""
    term_width: int = 0
    term_height: int = 0
    start_time: float = field(default_factory=time.time)
    extra: Dict = field(default_factory=dict)

########## Context Variable for Current Session ##########
current_session: contextvars.ContextVar[Optional[SessionInfo]] = contextvars.ContextVar('current_session', default=None)

########## Utility to Get Current Session ##########
def get_current_session() -> Optional[SessionInfo]:
    """
    ########## Retrieve Current Session ##########
    
    Returns the current session object if one is active in the context.
    Returns None if no session exists.
    """
    return current_session.get()

########## Singleton Class for Managing Sessions ##########
class SessionStore:
    """
    ########## Session Store Singleton ##########
    
    Manages a collection of active SSH sessions. Provides methods
    to add, remove, and retrieve sessions by UUID.
    """
    _instance = None

    def __new__(cls):
        """
        ########## Singleton Pattern Implementation ##########
        
        Ensures only one instance of SessionStore exists throughout the application.
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._sessions = {}
        return cls._instance

    def add(self, session: SessionInfo) -> None:
        """
        ########## Add Session to Store ##########
        
        Adds a new session to the internal storage.
        
        Parameters:
            session (SessionInfo): The session object to store
        """
        self._sessions[session.uuid] = session

    def remove(self, uuid: str) -> None:
        """
        ########## Remove Session from Store ##########
        
        Removes a session from the internal storage by its UUID.
        
        Parameters:
            uuid (str): Unique identifier of the session to remove
        """
        self._sessions.pop(uuid, None)

    def get(self, uuid: str) -> Optional[SessionInfo]:
        """
        ########## Retrieve Session by UUID ##########
        
        Retrieves a session from the internal storage by its UUID.
        
        Parameters:
            uuid (str): Unique identifier of the session to retrieve
            
        Returns:
            Optional[SessionInfo]: The session object if found, None otherwise
        """
        return self._sessions.get(uuid)

    def list_all(self) -> list:
        """
        ########## List All Active Sessions ##########
        
        Returns a list containing all active sessions in the store.
        
        Returns:
            list: Collection of SessionInfo objects representing active sessions
        """
        return list(self._sessions.values())

    def count(self) -> int:
        """
        ########## Count Active Sessions ##########
        
        Returns the number of active sessions currently stored.
        
        Returns:
            int: Number of active sessions in the store
        """
        return len(self._sessions)