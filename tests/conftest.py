import sys
import types
import pathlib
import importlib.util
import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SSH_ROOT = ROOT / "sshserver"

# Чтобы imports вида "from tests...." работали стабильно
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _ensure_pkg(name: str, path: pathlib.Path):
    if name in sys.modules:
        return sys.modules[name]
    mod = types.ModuleType(name)
    mod.__path__ = [str(path)]
    sys.modules[name] = mod
    return mod


def _load_module(fullname: str, file_path: pathlib.Path):
    if fullname in sys.modules:
        return sys.modules[fullname]

    spec = importlib.util.spec_from_file_location(fullname, str(file_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[fullname] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


# -----------------------------
# Lightweight package tree
# -----------------------------
_ensure_pkg("sshserver", SSH_ROOT)
_ensure_pkg("sshserver.terminal", SSH_ROOT / "terminal")
_ensure_pkg("sshserver.session", SSH_ROOT / "session")

# -----------------------------
# Fake CommandHistory
# -----------------------------
session_mod = sys.modules["sshserver.session"]


class FakeCommandHistory:
    def __init__(self):
        self._items = []
        self._index = None

    def add(self, line: str):
        self._items.append(line)
        self._index = None

    def previous(self):
        if not self._items:
            return None
        if self._index is None:
            self._index = len(self._items) - 1
        elif self._index > 0:
            self._index -= 1
        return self._items[self._index]

    def next(self):
        if self._index is None:
            return None
        self._index += 1
        if self._index >= len(self._items):
            self._index = None
            return ""
        return self._items[self._index]

    def reset_index(self):
        self._index = None


session_mod.CommandHistory = FakeCommandHistory

# -----------------------------
# Load only terminal modules
# -----------------------------
_load_module("sshserver.terminal.types", SSH_ROOT / "terminal" / "types.py")
_load_module("sshserver.terminal.mouse_handler", SSH_ROOT / "terminal" / "mouse_handler.py")
_load_module("sshserver.terminal.line_editor", SSH_ROOT / "terminal" / "line_editor.py")
_load_module("sshserver.terminal.input_handler", SSH_ROOT / "terminal" / "input_handler.py")

from sshserver.terminal.input_handler import InputHandler
from sshserver.terminal.line_editor import LineEditor


@pytest.fixture
def InputHandlerFixture():
    return InputHandler


@pytest.fixture
def LineEditorFixture():
    return LineEditor