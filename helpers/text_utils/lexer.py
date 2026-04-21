# helpers/lexer.py

from dataclasses import dataclass
from typing import List

from .char_tools import split_graphemes


# ==========================================
# TOKEN MODEL
# ==========================================
@dataclass(slots=True, frozen=True)
class LexToken:
    text: str
    start: int     # в grapheme-индексах
    length: int
    kind: str      # "command", "flag", "string", ...


# ==========================================
# TOKEN TYPES
# ==========================================
TK_WS               = "ws"
TK_WORD             = "word"
TK_STRING           = "string"
TK_STRING_UNCLOSED  = "string_unclosed"
TK_OPERATOR         = "operator"
TK_FLAG             = "flag"
TK_KEY              = "key"
TK_VALUE            = "value"
TK_COMMENT          = "comment"
TK_ENV              = "env"
TK_NUMBER           = "number"
TK_BOOL             = "bool"
TK_NULL             = "null"
TK_PATH             = "path"
TK_COMMAND          = "command"


OPERATORS = set("|&><;")


# ==========================================
# MAIN LEXER
# ==========================================
def lex(text: str) -> List[LexToken]:
    g = split_graphemes(text)
    n = len(g)

    tokens: list[LexToken] = []
    i = 0
    expect_command = True

    def emit(start: int, end: int, kind: str):
        if end <= start:
            return
        tokens.append(
            LexToken(
                text="".join(g[start:end]),
                start=start,
                length=end - start,
                kind=kind,
            )
        )

    while i < n:
        ch = g[i]

        # =========================
        # WHITESPACE
        # =========================
        if ch.isspace():
            start = i
            while i < n and g[i].isspace():
                i += 1
            emit(start, i, TK_WS)
            continue

        # =========================
        # COMMENT (# ...)
        # =========================
        if ch == "#":
            emit(i, n, TK_COMMENT)
            break

        # =========================
        # STRING ("..." / '...')
        # =========================
        if ch in ("'", '"'):
            quote = ch
            start = i
            i += 1
        
            closed = False
        
            while i < n:
                # TODO: можно добавить escape поддержку позже
                if g[i] == quote:
                    i += 1
                    closed = True
                    break
                i += 1
        
            kind = TK_STRING if closed else TK_STRING_UNCLOSED
            emit(start, i, kind)
            continue

        # =========================
        # OPERATORS
        # =========================
        if ch in OPERATORS:
            emit(i, i + 1, TK_OPERATOR)
            if ch in "|&;":
                expect_command = True
            i += 1
            continue

        # =========================
        # WORD TOKEN
        # =========================
        start = i
        while (
            i < n
            and not g[i].isspace()
            and g[i] not in OPERATORS
            and g[i] not in "\"'"
        ):
            i += 1

        token = "".join(g[start:i])

        # =========================
        # CLASSIFICATION
        # =========================

        # command
        if expect_command:
            emit(start, i, TK_COMMAND)
            expect_command = False
            continue

        # flag
        if token.startswith("--") or (token.startswith("-") and len(token) > 1):
            emit(start, i, TK_FLAG)
            continue

        # key=value
        if "=" in token:
            key, _, value = token.partition("=")

            # key
            emit(start, start + len(key), TK_KEY)

            # '='
            emit(start + len(key), start + len(key) + 1, TK_OPERATOR)

            val_start = start + len(key) + 1
            val_end = start + len(token)

            _emit_value(tokens, g, val_start, val_end)
            continue

        # value / word classification
        _emit_value(tokens, g, start, i)

    return tokens


# ==========================================
# VALUE CLASSIFIER
# ==========================================
def _emit_value(tokens, g, start, end):
    text = "".join(g[start:end])
    low = text.lower()

    if text.startswith("$"):
        kind = TK_ENV
    elif text.isdigit():
        kind = TK_NUMBER
    elif low in ("true", "false"):
        kind = TK_BOOL
    elif low in ("null", "none"):
        kind = TK_NULL
    elif "/" in text or text.startswith("."):
        kind = TK_PATH
    else:
        kind = TK_WORD

    tokens.append(
        LexToken(
            text=text,
            start=start,
            length=end - start,
            kind=kind,
        )
    )