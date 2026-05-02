import typing as t
from wcwidth import wcswidth

from helpers.text_utils.lexer import lex

if t.TYPE_CHECKING:
    from sshserver.session.syntax_highlight import StyleContext
    from helpers.lsp.json_rpc_proto import SemanticTokens

import logging
logger = logging.getLogger(__name__)

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

# Константа уровня модуля — не пересоздаётся каждый вызов
_KIND_TO_STYLE: dict[str, str] = {
    "command":         "SYNTAX_COMMAND",
    "flag":            "SYNTAX_FLAG",
    "key":             "SYNTAX_KEY",
    "operator":        "SYNTAX_OPERATOR",
    "string":          "SYNTAX_STRING",
    "string_unclosed": "SYNTAX_WARNING",
    "comment":         "SYNTAX_COMMENT",
    "env":             "SYNTAX_ENV",
    "number":          "SYNTAX_NUMBER",
    "bool":            "SYNTAX_BOOL",
    "null":            "SYNTAX_NULL",
    "path":            "SYNTAX_PATH",
    "word":            "SYNTAX_DEFAULT",
    "ws":              "SYNTAX_WS",
}


def highlight_buffer(
    buffer: list[str],
    style_ctx: StyleContext,
    semantic_tokens: SemanticTokens | None = None,
) -> list[tuple[str, str]]:
    if not buffer:
        return []

    lex_tokens = lex("".join(buffer))
    if not lex_tokens:
        return []

    # ── Шаг 1: резолвим ANSI для каждого токена лексера ──────────────────
    # (pos, length, base_style_name, base_ansi)
    # pos — символьная позиция в буфере
    resolved: list[tuple[int, int, str, str]] = []
    pos = 0
    for token in lex_tokens:
        style_name = _KIND_TO_STYLE.get(token.kind, "SYNTAX_DEFAULT")
        ansi = style_ctx.get(style_name)
        length = len(token.text)
        resolved.append((pos, length, style_name, ansi))
        pos += length

    if not semantic_tokens:
        # Нет семантики — сразу группируем в runs без промежуточных структур
        runs: list[tuple[str, str]] = []
        joined = "".join(buffer)
        _append = runs.append  # локальный биндинг ускоряет вызов
        for tok_pos, tok_len, _, ansi in resolved:
            chunk = joined[tok_pos : tok_pos + tok_len]
            if runs and runs[-1][1] == ansi:
                runs[-1] = (runs[-1][0] + chunk, ansi)
            else:
                _append((chunk, ansi))
        return runs

    # ── Шаг 2: merge семантики — по токенам, не по символам ──────────────

    joined = "".join(buffer)
    runs = []
    sem_idx = 0
    num_sem = len(semantic_tokens)

    for tok_pos, tok_len, base_name, base_ansi in resolved:
        tok_end = tok_pos + tok_len
        is_ws = base_name == "SYNTAX_WS"

        # Advance sem_idx до первого токена который может перекрываться
        while sem_idx < num_sem and semantic_tokens[sem_idx].start + semantic_tokens[sem_idx].length <= tok_pos:
            sem_idx += 1

        # Собираем все семантические токены пересекающиеся с текущим лексером
        # (их обычно 0–2, не нужен вложенный цикл на символы)
        cursor = tok_pos
        si = sem_idx  # локальная копия — не двигаем sem_idx внутри токена

        while cursor < tok_end:
            if not is_ws and si < num_sem:
                sem = semantic_tokens[si]
                sem_end = sem.start + sem.length

                if sem.start > cursor:
                    # Зазор до начала semantic — рисуем base
                    chunk_end = min(sem.start, tok_end)
                    _append_run(runs, joined[cursor:chunk_end], base_ansi)
                    cursor = chunk_end
                    continue

                if sem.start <= cursor < sem_end:
                    # Внутри semantic диапазона
                    sem_ansi = style_ctx.get(sem.style)
                    # Локальный биндинг для ускорения (dict.get в hot loop)
                    _get_prio = STYLE_PRIORITY.get
                    base_prio = _get_prio(base_name, 0)
                    sem_prio  = _get_prio(sem.style, 0)

                    if sem_prio >= base_prio:
                        chunk_end = min(sem_end, tok_end)
                        _append_run(runs, joined[cursor:chunk_end], sem_ansi)
                    else:
                        chunk_end = min(sem_end, tok_end)
                        _append_run(runs, joined[cursor:chunk_end], base_ansi)

                    cursor = chunk_end
                    if cursor >= sem_end:
                        si += 1
                    continue

            # Нет покрытия — остаток токена базовым стилем
            _append_run(runs, joined[cursor:tok_end], base_ansi)
            break

    return runs


def _append_run(runs: list[tuple[str, str]], text: str, ansi: str) -> None:
    """Добавляет chunk в runs, объединяя с предыдущим если стиль совпадает."""
    if not text:
        return
    if runs and runs[-1][1] == ansi:
        runs[-1] = (runs[-1][0] + text, ansi)
    else:
        runs.append((text, ansi))