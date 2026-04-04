import pytest

from tests.sshserver.terminal.testutils import FakeTerminal


@pytest.mark.asyncio
async def test_redraw_outputs_clear_sequence(LineEditorFixture):
    term = FakeTerminal(width=20)
    ed = LineEditorFixture(term)

    await ed.feed_text("hello")

    output = term.output.joined()

    assert b"\x1b[J" in output  # clear to end
    assert b"hello" in output


@pytest.mark.asyncio
async def test_redraw_wrap_outputs_newline(LineEditorFixture):
    term = FakeTerminal(width=8, ps1=">>> ")
    ed = LineEditorFixture(term)

    await ed.feed_text("1234")  # exact edge -> pending wrap
    output = term.output.joined()

    assert b"\r\n" in output


@pytest.mark.asyncio
async def test_ctrl_l_clears_screen(LineEditorFixture):
    term = FakeTerminal(width=20)
    ed = LineEditorFixture(term)

    await ed.feed_text("abc")
    term.output.clear()

    await ed.ctrl_l()

    output = term.output.joined()

    assert b"\x1b[2J\x1b[H" in output


@pytest.mark.asyncio
async def test_multiline_redraw_moves_up(LineEditorFixture):
    term = FakeTerminal(width=8, ps1=">>> ")
    ed = LineEditorFixture(term)

    await ed.feed_text("1234567890")
    term.output.clear()

    await ed.backspace()

    output = term.output.joined()

    # when redrawing multiline block, editor should move cursor up at least once
    assert b"\x1b[" in output
    assert b"A" in output