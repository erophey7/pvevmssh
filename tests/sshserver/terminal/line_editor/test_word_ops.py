import pytest
from tests.testutils.terminal_fakes import FakeTerminal


@pytest.mark.asyncio
async def test_ctrl_backspace_deletes_word(LineEditorFixture):
    term = FakeTerminal()
    ed = LineEditorFixture(term)

    await ed.feed_text("hello world")
    await ed.ctrl_backspace()

    assert "".join(ed._buffer) == "hello "


@pytest.mark.asyncio
async def test_ctrl_delete_deletes_word_right(LineEditorFixture):
    term = FakeTerminal()
    ed = LineEditorFixture(term)

    await ed.feed_text("hello world")
    await ed.cursor_home()
    await ed.ctrl_delete()

    assert "".join(ed._buffer) == " world"


@pytest.mark.asyncio
async def test_cursor_word_left(LineEditorFixture):
    term = FakeTerminal()
    ed = LineEditorFixture(term)

    await ed.feed_text("abc def ghi")
    await ed.cursor_word_left()

    assert ed._cursor == 8


@pytest.mark.asyncio
async def test_cursor_word_right(LineEditorFixture):
    term = FakeTerminal()
    ed = LineEditorFixture(term)

    await ed.feed_text("abc def ghi")
    await ed.cursor_home()
    await ed.cursor_word_right()

    assert ed._cursor == 3