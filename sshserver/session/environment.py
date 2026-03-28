"""User environment variable management."""

import re
from typing import Dict, Optional


class UserEnvironment:
    """
    Manages environment variables for a user session.
    Supports setting, getting, unsetting, and variable substitution.
    """

    def __init__(self):
        self._vars: Dict[str, str] = {}

    ########## Basic Operations ##########
    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        return self._vars.get(key, default)

    def set(self, key: str, value: str) -> None:
        self._vars[key] = value

    def unset(self, key: str) -> None:
        self._vars.pop(key, None)

    ########## Export Parsing ##########
    def export(self, line: str) -> str:
        """Parse 'VAR=value' line and set variable. Return formatted output."""
        line = line.strip()
        if not line:
            return ""

        if '=' not in line:
            key = line
            if key in self._vars:
                return f"{key}={self._vars[key]}\n"
            else:
                return f"export: {key}: not set\n"

        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip()

        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        elif value.startswith("'") and value.endswith("'"):
            value = value[1:-1]

        self._vars[key] = value
        return f"Environment variables set: {key}={value}\n"

    ########## Variable Substitution ##########
    def substitute(self, text: str) -> str:
        """Replace $VAR with the corresponding value (or empty if not set)."""
        def repl(match):
            var = match.group(1)
            return self._vars.get(var, '')
        return re.sub(r'\$([A-Za-z_][A-Za-z0-9_]*)', repl, text)