import regex
import typing as t
from wcwidth import wcswidth

if t.TYPE_CHECKING:
    from sshserver.session.syntax_highlight import StyleContext
    from .types import SyntaxToken

import logging
logger = logging.getLogger(__name__)


def split_graphemes(text: str) -> list[str]:
    return regex.findall(r"\X", text)


def char_width(g: str) -> int:
    width = wcswidth(g)
    return width if width > 0 else 1


def char_class(g: str) -> str:
    if g.isspace():
        return "ws"
    if g.isalnum() or g == "_":
        return "word"
    return "punct"

def get_style(style_ctx: StyleContext, key: str) -> str:
    return style_ctx.get(key.upper())

def highlight_buffer(
    buffer: list[str],
    style_ctx: StyleContext,
    semantic_tokens: list[SyntaxToken] | None = None,
) -> list[tuple[str, str]]:
    if not buffer:
        return []

    # --- приоритеты стилей ---
    STYLE_PRIORITY = {
        # --- абсолютный верх (диагностика) ---
        "SYNTAX_ERROR": 1000,
        "SYNTAX_WARNING": 900,

        # --- блокирующие семантики ---
        "SYNTAX_COMMENT": 800,
        "SYNTAX_STRING": 750,

        # --- команда и структура CLI ---
        "SYNTAX_COMMAND": 700,
        "SYNTAX_SUBCOMMAND": 680,

        # --- ключи/параметры ---
        "SYNTAX_KEY": 650,
        "SYNTAX_VALUE": 640,

        # --- флаги / опции ---
        "SYNTAX_FLAG": 620,
        "SYNTAX_OPTION": 610,

        # --- спец-типы значений ---
        "SYNTAX_ENV": 580,
        "SYNTAX_PATH": 570,
        "SYNTAX_NUMBER": 560,
        "SYNTAX_BOOL": 550,
        "SYNTAX_NULL": 540,

        # --- операторы ---
        "SYNTAX_OPERATOR": 500,

        # --- дефолт ---
        "SYNTAX_DEFAULT": 100,
        "SYNTAX_WS": 0,
    }

    # --- 1. базовая подсветка (имя + ansi) ---
    styled: list[tuple[str, str, str]] = []  # (char, style_name, ansi)
    i = 0
    n = len(buffer)
    expect_command = True
    in_comment = False

    while i < n:
        ch = buffer[i]

        if in_comment:
            name = "SYNTAX_COMMENT"
            styled.append((ch, name, style_ctx.get(name)))
            i += 1
            continue

        if ch in "\"'":
            quote = ch
            name = "SYNTAX_STRING"
            styled.append((ch, name, style_ctx.get(name)))
            i += 1
            while i < n:
                ch = buffer[i]
                styled.append((ch, name, style_ctx.get(name)))
                if ch == quote:
                    i += 1
                    break
                i += 1
            continue

        if ch.isspace():
            name = "SYNTAX_WS"
            styled.append((ch, name, style_ctx.get(name)))
            i += 1
            continue

        if ch in "|&><;":
            name = "SYNTAX_OPERATOR"
            styled.append((ch, name, style_ctx.get(name)))
            if ch in "|&;":
                expect_command = True
            i += 1
            continue

        token = ""
        start = i
        while i < n and not buffer[i].isspace() and buffer[i] not in "\"'|&><;":
            token += buffer[i]
            i += 1

        if token.startswith("#"):
            name = "SYNTAX_COMMENT"
            for chh in token:
                styled.append((chh, name, style_ctx.get(name)))
            in_comment = True
            continue

        # --- классификация токена ---
        def emit(text, name):
            ansi = style_ctx.get(name)
            for chh in text:
                styled.append((chh, name, ansi))

        if expect_command:
            emit(token, "SYNTAX_COMMAND")
            expect_command = False
            continue

        if token.startswith(("--", "-")):
            emit(token, "SYNTAX_FLAG")
            continue

        if "=" in token:
            key, sep, value = token.partition("=")
            emit(key, "SYNTAX_KEY")
            emit(sep, "SYNTAX_OPERATOR")

            if value.isdigit():
                val_name = "SYNTAX_NUMBER"
            elif value.lower() in ("true", "false"):
                val_name = "SYNTAX_BOOL"
            elif value.lower() in ("null", "none"):
                val_name = "SYNTAX_NULL"
            elif "/" in value or value.startswith("."):
                val_name = "SYNTAX_PATH"
            else:
                val_name = "SYNTAX_DEFAULT"

            emit(value, val_name)
            continue

        if "/" in token or token.startswith("."):
            emit(token, "SYNTAX_PATH")
        elif token.lower() in ("true", "false"):
            emit(token, "SYNTAX_BOOL")
        elif token.lower() in ("null", "none"):
            emit(token, "SYNTAX_NULL")
        elif token.isdigit():
            emit(token, "SYNTAX_NUMBER")
        elif token.startswith("$"):
            emit(token, "SYNTAX_ENV")
        else:
            emit(token, "SYNTAX_DEFAULT")

    # --- 2. накладываем семантику ---
    if not semantic_tokens:
        return [(ch, ansi) for ch, _, ansi in styled]
    
    logger.debug(semantic_tokens)

    final: list[tuple[str, str]] = []
    sem_idx = 0
    num_sem = len(semantic_tokens)

    for pos in range(len(styled)):
        ch, base_name, base_ansi = styled[pos]

        # двигаем указатель
        while (
            sem_idx < num_sem
            and semantic_tokens[sem_idx].start + semantic_tokens[sem_idx].length <= pos
        ):
            sem_idx += 1

        applied = False

        if sem_idx < num_sem:
            tok = semantic_tokens[sem_idx]
            if tok.start <= pos < tok.start + tok.length:
                sem_name = tok.style
                sem_ansi = style_ctx.get(sem_name)

                base_prio = STYLE_PRIORITY.get(base_name, 0)
                sem_prio = STYLE_PRIORITY.get(sem_name, 0)

                # не трогаем whitespace
                if base_name != "SYNTAX_WS" and sem_prio >= base_prio:
                    final.append((ch, sem_ansi))
                    applied = True

        if not applied:
            final.append((ch, base_ansi))
    logger.debug(final)
    return final