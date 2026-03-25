"""
Тест специальных символов.
"""

def chars_test(username: str, *args) -> str:
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

command = {
    "name": "chars",
    "help": "Test special characters",
    "func": chars_test
}