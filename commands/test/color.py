"""
ANSI color test (standard, bright, 256‑color palette).
"""

def color(username: str, *args) -> str:
    lines = []
    lines.append("ANSI Color Test:\n")

    for fg in range(30, 38):
        line = []
        for bg in range(40, 48):
            line.append(f"\033[{fg};{bg}m {fg}:{bg} \033[0m")
        lines.append(''.join(line))

    lines.append("\nBright colors:")
    for fg in range(90, 98):
        line = []
        for bg in range(100, 108):
            line.append(f"\033[{fg};{bg}m {fg}:{bg} \033[0m")
        lines.append(''.join(line))

    lines.append("\n256 colors:")
    for i in range(16, 232):
        if (i - 16) % 36 == 0:
            lines.append("\n")
        lines.append(f"\033[48;5;{i}m {i:3} \033[0m")

    lines.append("\n")
    return ''.join(lines)


command = {
    "name": "color",
    "help": "Display ANSI color test",
    "func": color,
    "permissions": ["tester_permission"]
}