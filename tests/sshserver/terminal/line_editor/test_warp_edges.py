import pytest
from tests.testutils.terminal_fakes import FakeTerminal


@pytest.mark.asyncio
async def test_exact_terminal_edge_wrap(LineEditorFixture):
    term = FakeTerminal(width=8, ps1=">>> ")
    ed = LineEditorFixture(term)

    await ed.feed_text("1234")
    layout = ed._build_layout()

    assert layout.pending_wrap is True


@pytest.mark.asyncio
async def test_wrap_after_one_more_char(LineEditorFixture):
    term = FakeTerminal(width=8, ps1=">>> ")
    ed = LineEditorFixture(term)

    await ed.feed_text("12345")
    layout = ed._build_layout()

    assert len(layout.rows) >= 2