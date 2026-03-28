"""Environment management for user session."""
import re
from typing import Dict, Optional

########## User Environment Management Class ##########
class UserEnvironment:
    def __init__(self):
        """
        ########## Environment Variable Manager Initialization ##########
        
        Initializes a new instance of the UserEnvironment class,
        which manages environment variables for a user session.
        """
        self._vars: Dict[str, str] = {}

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        ########## Retrieve Environment Variable ##########
        
        Retrieves the value of an environment variable if it exists,
        otherwise returns the provided default value.
        
        Parameters:
            key (str): Name of the environment variable
            default (Optional[str]): Default value to return if variable is not found
            
        Returns:
            Optional[str]: The value of the variable or the default value
        """
        return self._vars.get(key, default)

    def set(self, key: str, value: str) -> None:
        """
        ########## Set Environment Variable ##########
        
        Sets or updates an environment variable with the provided value.
        
        Parameters:
            key (str): Name of the environment variable
            value (str): Value to assign to the variable
        """
        self._vars[key] = value

    def unset(self, key: str) -> None:
        """
        ########## Unset Environment Variable ##########
        
        Removes an environment variable from the internal storage.
        
        Parameters:
            key (str): Name of the environment variable to remove
        """
        self._vars.pop(key, None)

    def export(self, line: str) -> str:
        """
        ########## Export Environment Variables ##########
        
        Processes a single line of environment variable assignment,
        parses it, and updates the internal storage accordingly.
        Returns a formatted output string showing the result.
        
        Parameters:
            line (str): A single line containing an environment variable assignment
            
        Returns:
            str: Formatted output showing the result of processing
        """
        line = line.strip()
        if not line:
            return ""

        # ########## Simple Parsing: Split by First '=' ##########
        if '=' not in line:
            key = line
            if key in self._vars:
                return f"{key}={self._vars[key]}\n"
            else:
                return f"export: {key}: not set\n"

        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip()

        # ########## Remove Quotes if Present ##########
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        elif value.startswith("'") and value.endswith("'"):
            value = value[1:-1]

        self._vars[key] = value
        return f"Environment variables set: {key}={value}\n"

    def substitute(self, text: str) -> str:
        """
        ########## Variable Substitution in Text ##########
        
        Replaces occurrences of $var syntax with the corresponding
        environment variable values. If a variable is not found,
        it is left unchanged.
        
        Parameters:
            text (str): Input string containing potential variables to substitute
            
        Returns:
            str: Modified text with substituted variables
        """
        def repl(match):
            var = match.group(1)
            return self._vars.get(var, '')
        return re.sub(r'\$([A-Za-z_][A-Za-z0-9_]*)', repl, text)
