"""ANSI escape sequences — чистые примитивы, без состояния."""

# Cursor movement -------------------------------------------------
def move_cursor(row_0based: int, col_1based: int) -> bytes:
    """0-based row, 1-based col → ANSI CUP."""
    return f"\x1b[{row_0based + 1};{col_1based}H".encode()


def move_up(n: int = 1) -> bytes:
    return f"\x1b[{n}A".encode() if n > 0 else b""


def move_down(n: int = 1) -> bytes:
    return f"\x1b[{n}B".encode() if n > 0 else b""


def move_right(n: int = 1) -> bytes:
    return f"\x1b[{n}C".encode() if n > 0 else b""


def move_left(n: int = 1) -> bytes:
    return f"\x1b[{n}D".encode() if n > 0 else b""


def move_to_column(col_1based: int) -> bytes:
    return f"\x1b[{col_1based}G".encode()


# Erasing ---------------------------------------------------------
CLEAR_TO_END_OF_LINE = b"\x1b[K"
CLEAR_TO_START_OF_LINE = b"\x1b[1K"
CLEAR_LINE = b"\x1b[2K"
CLEAR_TO_END_OF_SCREEN = b"\x1b[J"
CLEAR_TO_START_OF_SCREEN = b"\x1b[1J"
CLEAR_SCREEN = b"\x1b[2J"
CURSOR_HOME = b"\x1b[H"

# Styles ----------------------------------------------------------
RESET_STYLE = b"\x1b[0m"

# CPR -------------------------------------------------------------
REQUEST_CURSOR_POSITION = b"\x1b[6n"

# Raw -------------------------------------------------------------
CR = b"\r"
CRLF = b"\r\n"