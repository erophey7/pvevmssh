import regex
from wcwidth import wcswidth


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