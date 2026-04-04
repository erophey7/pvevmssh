import pytest
from tests.sshserver.terminal.testutils.fakes import FakeTerminal
from tests.sshserver.terminal.testutils.line_editor import get_editor_layout


@pytest.mark.asyncio
async def test_exact_terminal_edge_wrap(LineEditorFixture):
    term = FakeTerminal(width=8, ps1=">>> ")
    ed = LineEditorFixture(term)

    await ed.feed_text("1234")
    layout = get_editor_layout(ed)

    assert layout.pending_wrap is True


@pytest.mark.asyncio
async def test_wrap_after_one_more_char(LineEditorFixture):
    term = FakeTerminal(width=8, ps1=">>> ")
    ed = LineEditorFixture(term)

    await ed.feed_text("12345")
    layout = get_editor_layout(ed)

    assert len(layout.rows) >= 2