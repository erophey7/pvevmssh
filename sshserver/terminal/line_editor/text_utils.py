import regex
import typing as t
from wcwidth import wcswidth

if t.TYPE_CHECKING:
    from sshserver.session.syntax_highlight import StyleContext


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

def highlight_buffer(buffer: list[str], style_ctx: StyleContext) -> list[tuple[str, str]]:
    if not buffer:
        return []

    styled = []
    token = ""
    state = "normal"
    is_first = True

    def classify(tok: str) -> str:
        # ===== STRING =====
        if state == "string":
            return style_ctx.get("SYNTAX_STRING")

        # ===== COMMENT =====
        if tok.startswith("#"):
            return style_ctx.get("SYNTAX_COMMENT")

        # ===== FLAGS =====
        if tok.startswith("--") or tok.startswith("-"):
            return style_ctx.get("SYNTAX_FLAG")

        # ===== ENV =====
        if tok.startswith("$"):
            return style_ctx.get("SYNTAX_ENV")

        # ===== PATH =====
        if "/" in tok or tok.startswith("."):
            return style_ctx.get("SYNTAX_PATH")

        # ===== KEY=VALUE =====
        if "=" in tok:
            key, _, value = tok.partition("=")
            # отдельно обработаем позже
            return "KEYVALUE"

        # ===== BOOL =====
        if tok.lower() in ("true", "false"):
            return style_ctx.get("SYNTAX_BOOL")

        # ===== NULL =====
        if tok.lower() in ("null", "none"):
            return style_ctx.get("SYNTAX_NULL")

        # ===== NUMBER =====
        if tok.isdigit():
            return style_ctx.get("SYNTAX_NUMBER")

        # ===== COMMAND =====
        nonlocal is_first
        if is_first:
            is_first = False
            return style_ctx.get("SYNTAX_COMMAND")

        return style_ctx.get("SYNTAX_DEFAULT")

    def flush(tok):
        if not tok:
            return

        style = classify(tok)

        # ===== KEY=VALUE спец логика =====
        if style == "KEYVALUE":
            key, sep, value = tok.partition("=")

            for ch in key:
                styled.append((ch, style_ctx.get("SYNTAX_KEY")))

            styled.append((sep, style_ctx.get("SYNTAX_OPERATOR")))

            val_style = classify(value)
            for ch in value:
                styled.append((ch, val_style))

            return

        for ch in tok:
            styled.append((ch, style))

    i = 0
    n = len(buffer)

    while i < n:
        ch = buffer[i]

        # ===== STRING MODE =====
        if ch in "\"'":
            flush(token)
            token = ""

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

        # ===== WHITESPACE =====
        if ch.isspace():
            flush(token)
            token = ""
            styled.append((ch, style_ctx.get("SYNTAX_WS")))
            i += 1
            continue

        # ===== OPERATORS =====
        if ch in "|&><":
            flush(token)
            token = ""
            styled.append((ch, style_ctx.get("SYNTAX_OPERATOR")))
            i += 1
            continue

        token += ch
        i += 1

    flush(token)
    return styled