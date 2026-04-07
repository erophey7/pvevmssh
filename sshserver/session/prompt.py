"""PS1 prompt expansion engine — полный bash-совместимый обработчик."""

import socket
import time
import re

from .types import PromptSegment

# Регулярки
_NONPRINT_RE = re.compile(r"\\\[ (.*?) \\\]", re.DOTALL | re.VERBOSE)
_CSI_RE = re.compile(r"\x1b\[.*?[A-Za-z~]", re.DOTALL)


def _expand_escapes(text: str, session, env) -> str:
    r"""Базовая замена \u \h \e и т.д. + $VAR."""
    if hasattr(env, "substitute"):
        try:
            text = env.substitute(text)
        except Exception:
            pass

    text = text.replace(r"\e", "\x1b").replace(r"\E", "\x1b").replace(r"\033", "\x1b")
    text = text.replace(r"\u", session.username or "user")
    text = text.replace(r"\h", env.get("HOSTNAME", "").partition(".")[0] or "host")
    text = text.replace(r"\H", env.get("HOSTNAME", "") or "host")

    # \$ → # / $
    text = text.replace(r"\$", "#" if getattr(session, "username", "") == "root" else "$")

    return text


def expand_ps1(raw_ps1: str, session, env) -> str:
    r"""Готовая строка ДЛЯ ВЫВОДА В ТЕРМИНАЛ (runtime.py)."""
    if not raw_ps1:
        return ">>> "

    ps1 = _expand_escapes(raw_ps1, session, env)

    # Убираем маркеры \[ \], оставляем содержимое
    def replace_nonprint(m):
        return m.group(1)

    ps1 = _NONPRINT_RE.sub(replace_nonprint, ps1)
    return ps1


def get_prompt_segments(terminal) -> list["PromptSegment"]:
    r"""Парсит промпт → видимые + невидимые части (для line editor)."""

    session = getattr(terminal, "session", None)
    if not session:
        return [PromptSegment(">>> ", True)]

    env = session.extra.get("env", {})
    raw = env.get("PS1", ">>> ") if hasattr(env, "get") else ">>> "

    parts: list[PromptSegment] = []
    pos = 0

    # 1. Обрабатываем официальные \[ \] (как в bash)
    for m in _NONPRINT_RE.finditer(raw):
        if m.start() > pos:
            visible = _expand_escapes(raw[pos:m.start()], session, env)
            parts.append(PromptSegment(visible, True))

        # невидимая часть
        nonprint = m.group(1)
        nonprint = nonprint.replace(r"\e", "\x1b").replace(r"\E", "\x1b").replace(r"\033", "\x1b")
        parts.append(PromptSegment(nonprint, False))

        pos = m.end()

    # 2. Оставшаяся часть + автоопределение CSI без \[ \]
    remaining = raw[pos:]
    if remaining:
        expanded = _expand_escapes(remaining, session, env)

        # Авто-детект CSI последовательностей как невидимых
        csi_pos = 0
        for csi_match in _CSI_RE.finditer(expanded):
            start = csi_match.start()
            if start > csi_pos:
                visible_part = expanded[csi_pos:start]
                parts.append(PromptSegment(visible_part, True))

            # CSI = невидимая
            parts.append(PromptSegment(csi_match.group(0), False))
            csi_pos = csi_match.end()

        # Остаток
        if csi_pos < len(expanded):
            parts.append(PromptSegment(expanded[csi_pos:], True))

    if not parts:
        parts.append(PromptSegment(_expand_escapes(raw, session, env), True))

    return parts