# commands/test/color.py
"""
########## ANSI Color Test ##########
"""

def color(username: str, *args) -> str:
    """
    ########## Display ANSI Color Table ##########
    
    Generates a visual representation of all standard ANSI colors,
    including foreground/background combinations, bright colors,
    and 256-color palette. Used to verify terminal color support.
    """

    lines = []
    lines.append("ANSI Color Test:\n")

    # ########## Standard Color Codes (30-37 for foreground, 40-47 for background) ##########
    for fg in range(30, 38):
        line = []
        for bg in range(40, 48):
            line.append(f"\033[{fg};{bg}m {fg}:{bg} \033[0m")
        lines.append(''.join(line))

    # ########## Bright Color Codes (90-97 for foreground, 100-107 for background) ##########
    lines.append("\nBright colors:")
    for fg in range(90, 98):
        line = []
        for bg in range(100, 108):
            line.append(f"\033[{fg};{bg}m {fg}:{bg} \033[0m")
        lines.append(''.join(line))

    # ########## 256-Color Palette (16-232) ##########
    lines.append("\n256 colors:")
    for i in range(16, 232):
        if (i - 16) % 36 == 0:
            lines.append("\n")
        lines.append(f"\033[48;5;{i}m {i:3} \033[0m")

    lines.append("\n")
    return ''.join(lines)


########## Command Definition ##########
command = {
    "name": "color",
    "help": "Display ANSI color test",
    "func": color,
    "permissions": ["tester_permission"]
}