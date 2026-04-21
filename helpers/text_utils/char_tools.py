import regex

def split_graphemes(text: str) -> list[str]:
    return regex.findall(r"\X", text)
