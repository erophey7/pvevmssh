import pytest
from tests.sshserver.terminal.testutils.fakes import FakeTerminal
from tests.sshserver.terminal.testutils.line_editor import get_editor_layout


@pytest.mark.asyncio
async def test_emoji_layout(LineEditorFixture):
    term = FakeTerminal(width=20)
    ed = LineEditorFixture(term)

    await ed.feed_text("a🙂b")
    layout = get_editor_layout(ed)

    assert layout.cursor_pos.col >= 1
    assert "🙂" in layout.rendered_text


@pytest.mark.asyncio
async def test_combining_char_layout(LineEditorFixture):
    term = FakeTerminal(width=20)
    ed = LineEditorFixture(term)

    await ed.feed_text("e\u0301")
    layout = get_editor_layout(ed)

    assert layout.cursor_pos.col >= 1
    assert "e" in layout.rendered_text


@pytest.mark.asyncio
async def test_cjk_wrap(LineEditorFixture):
    term = FakeTerminal(width=8, ps1=">>> ")
    ed = LineEditorFixture(term)

    await ed.feed_text("你好")
    layout = get_editor_layout(ed)

    assert len(layout.rows) >= 1