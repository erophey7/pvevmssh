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

    # 1. Базовая подсветка (логическими токенами, как было раньше)
    styled: list[tuple[str, str]] = []
    i = 0
    n = len(buffer)
    expect_command = True
    in_comment = False

    while i < n:
        ch = buffer[i]

        if in_comment:
            styled.append((ch, style_ctx.get("SYNTAX_COMMENT")))
            i += 1
            continue

        if ch in "\"'":
            quote = ch
            styled.append((ch, style_ctx.get("SYNTAX_STRING")))
            i += 1
            while i < n:
                ch = buffer[i]
                styled.append((ch, style_ctx.get("SYNTAX_STRING")))
                if ch == quote:
                    i += 1
                    break
                i += 1
            continue

        if ch.isspace():
            styled.append((ch, style_ctx.get("SYNTAX_WS")))
            i += 1
            continue

        if ch in "|&><;":
            styled.append((ch, style_ctx.get("SYNTAX_OPERATOR")))
            if ch in "|&;":
                expect_command = True
            i += 1
            continue

        token_start = i
        token = ""
        while i < n and not buffer[i].isspace() and buffer[i] not in "\"'|&><;":
            token += buffer[i]
            i += 1

        if token.startswith("#"):
            style = style_ctx.get("SYNTAX_COMMENT")
            for chh in token:
                styled.append((chh, style))
            in_comment = True
            continue

        style = "SYNTAX_DEFAULT"
        if expect_command:
            style = "SYNTAX_COMMAND"
            expect_command = False
        elif token.startswith(("--", "-")):
            style = "SYNTAX_FLAG"
        elif "=" in token:
            key, sep, value = token.partition("=")
            for chh in key:
                styled.append((chh, style_ctx.get("SYNTAX_KEY")))
            styled.append((sep, style_ctx.get("SYNTAX_OPERATOR")))
            val_style = style_ctx.get("SYNTAX_DEFAULT")
            if value.isdigit():
                val_style = style_ctx.get("SYNTAX_NUMBER")
            elif value.lower() in ("true", "false"):
                val_style = style_ctx.get("SYNTAX_BOOL")
            elif value.lower() in ("null", "none"):
                val_style = style_ctx.get("SYNTAX_NULL")
            elif "/" in value or value.startswith("."):
                val_style = style_ctx.get("SYNTAX_PATH")
            for chh in value:
                styled.append((chh, val_style))
            continue
        elif "/" in token or token.startswith("."):
            style = "SYNTAX_PATH"
        elif token.lower() in ("true", "false"):
            style = "SYNTAX_BOOL"
        elif token.lower() in ("null", "none"):
            style = "SYNTAX_NULL"
        elif token.isdigit():
            style = "SYNTAX_NUMBER"
        elif token.startswith("$"):
            style = "SYNTAX_ENV"

        for chh in token:
            styled.append((chh, style_ctx.get(style)))

    # 2. Накладываем семантику (span-based)
    if not semantic_tokens or not isinstance(semantic_tokens, list) or len(semantic_tokens) == 0:
        return styled

    final: list[tuple[str, str]] = []
    PROTECTED = {
        style_ctx.get("SYNTAX_STRING"),
        style_ctx.get("SYNTAX_COMMENT"),
    }

    sem_idx = 0
    num_sem = len(semantic_tokens)

    for pos in range(len(buffer)):
        ch, base_style = styled[pos]

        # продвигаем указатель на актуальный спан
        while sem_idx < num_sem and semantic_tokens[sem_idx].start + semantic_tokens[sem_idx].length <= pos:
            sem_idx += 1

        applied = False
        if sem_idx < num_sem:
            tok = semantic_tokens[sem_idx]
            if tok.start <= pos < tok.start + tok.length:
                sem_ansi = style_ctx.get(tok.style)
                if base_style not in PROTECTED and base_style not in (
                    style_ctx.get("SYNTAX_WS"),
                    style_ctx.get("SYNTAX_OPERATOR"),
                ):
                    final.append((ch, sem_ansi))
                    applied = True

        if not applied:
            final.append((ch, base_style))

    return final