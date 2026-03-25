"""
########## Special Characters Test ##########
"""

def chars_test(username: str, *args) -> str:
    """
    ########## Display Special Character Sets ##########
    
    Generates a formatted string containing various special character sets,
    including box drawing characters, block characters, shades, arrows, and Unicode symbols.
    This is used to test the terminal's ability to display special characters correctly.
    """

    lines = []
    lines.append("Special characters:")
    chars = [
        ("Box drawing", "┌─┐│└─┘├─┤┴┬┼"),
        ("Blocks", "█▇▆▅▄▃▂▁"),
        ("Shades", "░▒▓"),
        ("Arrows", "←↑→↓↔↕"),
        ("Misc", "☺☻♥♦♣♠•◘○◙♂♀♪♫☼"),
    ]
    for name, ch in chars:
        lines.append(f"{name}: {ch}")
    lines.append("\nUnicode symbols (if supported):")
    unicode_chars = ["∀", "∁", "∂", "∃", "∄", "∅", "∆", "∇", "∈", "∉", "∊", "∋", "∌", "∍", "∎", "∏", "∐", "∑", "−", "∓", "∔", "∕", "∖", "∗", "∘", "∙", "√", "∛", "∜", "∝", "∞", "∟", "∠", "∡", "∢", "∣", "∤", "∥", "∧", "∨", "∩", "∪", "∫", "∬", "∭", "∮", "∯", "∰", "∱", "∲", "∳"]
    lines.append(" ".join(unicode_chars))
    return "\n".join(lines)


########## Command Definition ##########
command = {
    "name": "chars",
    "help": "Test special characters",
    "func": chars_test
}
