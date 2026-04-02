import pytest
from tests.testutils.terminal_fakes import FakeTerminal


@pytest.mark.asyncio
async def test_render_simple_text(LineEditorFixture):
    term = FakeTerminal(width=80)
    ed = LineEditorFixture(term)

    await ed.feed_text("hello")
    layout = ed._build_layout()

    assert "hello" in layout.rendered_text


@pytest.mark.asyncio
async def test_render_wrap(LineEditorFixture):
    term = FakeTerminal(width=8, ps1=">>> ")
    ed = LineEditorFixture(term)

    await ed.feed_text("1234567890")
    layout = ed._build_layout()

    assert len(layout.rows) >= 2


@pytest.mark.asyncio
async def test_cursor_position_end(LineEditorFixture):
    term = FakeTerminal(width=80)
    ed = LineEditorFixture(term)

    await ed.feed_text("abc")
    layout = ed._build_layout()

    assert layout.cursor_pos.col >= 1