import pytest
from tests.sshserver.terminal.testutils.fakes import FakeTerminal


@pytest.mark.asyncio
async def test_resize_invalidates_layout(LineEditorFixture):
    term = FakeTerminal()
    ed = LineEditorFixture(term)

    await ed.feed_text("hello")
    assert ed._last_layout is not None

    await ed.on_terminal_resize()
    assert ed._last_layout is not None