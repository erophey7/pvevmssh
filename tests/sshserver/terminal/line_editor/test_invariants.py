import pytest
from tests.sshserver.terminal.testutils.fakes import FakeTerminal


@pytest.mark.asyncio
async def test_cursor_never_negative(LineEditorFixture):
    term = FakeTerminal()
    ed = LineEditorFixture(term)

    await ed.cursor_left()
    assert ed._cursor == 0


@pytest.mark.asyncio
async def test_cursor_never_past_buffer(LineEditorFixture):
    term = FakeTerminal()
    ed = LineEditorFixture(term)

    await ed.feed_text("abc")
    await ed.cursor_right()
    assert ed._cursor == 3


@pytest.mark.asyncio
async def test_backspace_empty_safe(LineEditorFixture):
    term = FakeTerminal()
    ed = LineEditorFixture(term)

    await ed.backspace()
    assert ed._cursor == 0
    assert ed._buffer == []


@pytest.mark.asyncio
async def test_delete_empty_safe(LineEditorFixture):
    term = FakeTerminal()
    ed = LineEditorFixture(term)

    await ed.delete()
    assert ed._cursor == 0
    assert ed._buffer == []


@pytest.mark.asyncio
async def test_enter_returns_line_and_editor_stays_valid(LineEditorFixture):
    term = FakeTerminal()
    ed = LineEditorFixture(term)

    await ed.feed_text("hello")
    line = await ed.enter()

    assert line == "hello"
    assert 0 <= ed._cursor <= len(ed._buffer)


@pytest.mark.asyncio
async def test_reset_clears_everything(LineEditorFixture):
    term = FakeTerminal()
    ed = LineEditorFixture(term)

    await ed.feed_text("hello")
    await ed.reset()

    assert ed._buffer == []
    assert ed._cursor == 0
    assert ed._last_layout is None