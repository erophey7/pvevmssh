# sshserver/session/syntax_highlight.py
import typing as t

class StyleConfig:
    """Все цвета и стили вынесены сюда (как ты просил)."""
    RESET = "\x1b[0m"
    COMPLETION = "\x1b[36m"           # cyan
    COMPLETION_SELECTED = "\x1b[7;36m"  # reverse + cyan
    # Можно добавить BUFFER_xxx позже для подсветки набираемого текста


def get_style(key: str) -> str:
    styles = {
        "completion": StyleConfig.COMPLETION,
        "completion_selected": StyleConfig.COMPLETION_SELECTED,
        "default": "",
    }
    return styles.get(key, StyleConfig.RESET)