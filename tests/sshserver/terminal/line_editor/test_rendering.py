import pytest
from tests.sshserver.terminal.testutils.fakes import FakeTerminal
from tests.sshserver.terminal.testutils.line_editor import get_editor_layout


@pytest.mark.asyncio
async def test_render_simple_text(LineEditorFixture):
    term = FakeTerminal(width=80)
    ed = LineEditorFixture(term)

    await ed.feed_text("hello")
    layout = get_editor_layout(ed)

    assert "hello" in layout.rendered_text


@pytest.mark.asyncio
async def test_render_wrap(LineEditorFixture):
    term = FakeTerminal(width=8, ps1=">>> ")
    ed = LineEditorFixture(term)

    await ed.feed_text("1234567890")
    layout = get_editor_layout(ed)

    assert len(layout.rows) >= 2


@pytest.mark.asyncio
async def test_cursor_position_end(LineEditorFixture):
    term = FakeTerminal(width=80)
    ed = LineEditorFixture(term)

    await ed.feed_text("abc")
    layout = get_editor_layout(ed)

    assert layout.cursor_pos.col >= 1