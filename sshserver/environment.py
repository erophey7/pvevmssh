import re
from typing import Dict, Optional

class UserEnvironment:
    def __init__(self):
        self._vars: Dict[str, str] = {}

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        return self._vars.get(key, default)

    def set(self, key: str, value: str) -> None:
        self._vars[key] = value

    def unset(self, key: str) -> None:
        self._vars.pop(key, None)

    def export(self, line: str) -> str:
        line = line.strip()
        if not line:
            return ""

        # Простой парсинг: разделяем по первому '='
        if '=' not in line:
            key = line
            if key in self._vars:
                return f"{key}={self._vars[key]}\n"
            else:
                return f"export: {key}: not set\n"

        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip()

        # Удаляем кавычки, если они есть
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        elif value.startswith("'") and value.endswith("'"):
            value = value[1:-1]

        self._vars[key] = value
        return f"Environment variables set: {key}={value}\n"

    def substitute(self, text: str) -> str:
        def repl(match):
            var = match.group(1)
            return self._vars.get(var, '')
        return re.sub(r'\$([A-Za-z_][A-Za-z0-9_]*)', repl, text)