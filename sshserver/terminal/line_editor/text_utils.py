import typing as t
from wcwidth import wcswidth

from helpers.text_utils.lexer import lex

if t.TYPE_CHECKING:
    from sshserver.session.syntax_highlight import StyleContext
    from .types import SyntaxToken

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

def highlight_buffer(
    buffer: list[str],
    style_ctx: StyleContext,
    semantic_tokens: list[SyntaxToken] | None = None,
) -> list[tuple[str, str]]:          # list of (run_text, ansi_style)
    if not buffer:
        return []

    # ================================================
    # 1. БАЗОВАЯ ПОДСВЕТКА ЧЕРЕЗ LEXER (новое!)
    # ================================================
    

    def _kind_to_style(kind: str) -> str:
        mapping = {
            "command":          "SYNTAX_COMMAND",
            "flag":             "SYNTAX_FLAG",
            "key":              "SYNTAX_KEY",
            "operator":         "SYNTAX_OPERATOR",
            "string":           "SYNTAX_STRING",
            "string_unclosed":  "SYNTAX_WARNING",
            "comment":          "SYNTAX_COMMENT",
            "env":              "SYNTAX_ENV",
            "number":           "SYNTAX_NUMBER",
            "bool":             "SYNTAX_BOOL",
            "null":             "SYNTAX_NULL",
            "path":             "SYNTAX_PATH",
            "word":             "SYNTAX_DEFAULT",
            "ws":               "SYNTAX_WS",
        }
        return mapping.get(kind, "SYNTAX_DEFAULT")

    lex_tokens = lex("".join(buffer))

    styled: list[tuple[str, str, str]] = []  # (char, style_name, ansi)
    for token in lex_tokens:
        style_name = _kind_to_style(token.kind)
        ansi = style_ctx.get(style_name)
        for ch in token.text:                    # token.text уже joined graphemes
            styled.append((ch, style_name, ansi))

    # ================================================
    # 2. НАКЛАДЫВАЕМ СЕМАНТИКУ ИЗ SHELL_LSP
    # ================================================
    if not semantic_tokens:
        final = [(ch, ansi) for ch, _, ansi in styled]
    else:
        logger.debug(semantic_tokens)

        final: list[tuple[str, str]] = []
        sem_idx = 0
        num_sem = len(semantic_tokens)

        for pos in range(len(styled)):
            ch, base_name, base_ansi = styled[pos]

            # двигаем указатель семантики
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

                    if base_name != "SYNTAX_WS" and sem_prio >= base_prio:
                        final.append((ch, sem_ansi))
                        applied = True

            if not applied:
                final.append((ch, base_ansi))

        #logger.debug(final)

    # ================================================
    # 3. ГРУППИРУЕМ В RUNS
    # ================================================
    if not final:
        return []

    runs: list[tuple[str, str]] = []
    current_text: list[str] = [final[0][0]]
    current_ansi = final[0][1]

    for ch, ansi in final[1:]:
        if ansi == current_ansi:
            current_text.append(ch)
        else:
            runs.append(("".join(current_text), current_ansi))
            current_text = [ch]
            current_ansi = ansi

    runs.append(("".join(current_text), current_ansi))
    logger.debug(runs)
    return runs