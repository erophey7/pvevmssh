import sys
import pathlib
import pytest

from tests.testutils.module_loader import load_module, load_package

ROOT = pathlib.Path(__file__).resolve().parents[3]
SSH_ROOT = ROOT / "sshserver"

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
# Load terminal modules
# -----------------------------
load_module("sshserver.terminal.types", SSH_ROOT / "terminal" / "types.py")
load_module("sshserver.terminal.mouse_handler", SSH_ROOT / "terminal" / "mouse_handler.py")
load_package("sshserver.terminal.line_editor", SSH_ROOT / "terminal" / "line_editor")
load_module("sshserver.terminal.input_handler", SSH_ROOT / "terminal" / "input_handler.py")

from sshserver.terminal.DELETING_input_handler import InputHandler
from sshserver.terminal.line_editor import LineEditor

from tests.sshserver.terminal.testutils.fakes import (
    FakeTerminal,
    FakeSession,
    FakeOutput,
)


@pytest.fixture
def InputHandlerFixture():
    return InputHandler


@pytest.fixture
def LineEditorFixture():
    return LineEditor


@pytest.fixture
def fake_output():
    return FakeOutput()


@pytest.fixture
def fake_session():
    return FakeSession()


@pytest.fixture
def fake_terminal(fake_session, fake_output):
    return FakeTerminal(session=fake_session, output=fake_output)