"""
Test special characters (box drawing, blocks, Unicode).
"""

from sshserver.commandapi import CommandAPI


async def execute(api: CommandAPI) -> str | None:
    api.require_permission("tester_permission")

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
    "func": execute,
    "permissions": ["tester_permission"]
}