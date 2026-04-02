import pytest
from tests.testutils.terminal_fakes import FakeTerminal


@pytest.mark.asyncio
async def test_emoji_layout(LineEditorFixture):
    term = FakeTerminal(width=20)
    ed = LineEditorFixture(term)

    await ed.feed_text("a🙂b")
    layout = ed._build_layout()

    assert layout.cursor_pos.col >= 1
    assert "🙂" in layout.rendered_text


@pytest.mark.asyncio
async def test_combining_char_layout(LineEditorFixture):
    term = FakeTerminal(width=20)
    ed = LineEditorFixture(term)

    await ed.feed_text("e\u0301")
    layout = ed._build_layout()

    assert layout.cursor_pos.col >= 1
    assert "e" in layout.rendered_text


@pytest.mark.asyncio
async def test_cjk_wrap(LineEditorFixture):
    term = FakeTerminal(width=8, ps1=">>> ")
    ed = LineEditorFixture(term)

    await ed.feed_text("你好")
    layout = ed._build_layout()

    assert len(layout.rows) >= 1