import pytest

from tests.sshserver.terminal.testutils import FakeTerminal
from tests.sshserver.terminal.testutils.line_editor import get_editor_layout


@pytest.mark.asyncio
async def test_emoji_width_affects_cursor(LineEditorFixture):
    term = FakeTerminal(width=20, ps1=">>> ")
    ed = LineEditorFixture(term)

    await ed.feed_text("a🙂b")
    layout = get_editor_layout(ed)

    # >>>  = 4 cols
    # a    = 1
    # 🙂   = 2
    # b    = 1
    # total cursor col = 9
    assert layout.cursor_pos.row == 0
    assert layout.cursor_pos.col == 9


@pytest.mark.asyncio
async def test_combining_char_is_single_visual_cell(LineEditorFixture):
    term = FakeTerminal(width=20, ps1=">>> ")
    ed = LineEditorFixture(term)

    await ed.feed_text("e\u0301")  # é via combining
    layout = get_editor_layout(ed)

    assert len(ed._buffer) == 1
    assert layout.cursor_pos.row == 0
    assert layout.cursor_pos.col == 6  # >>> + 1 char


@pytest.mark.asyncio
async def test_cjk_wrap_exactly(LineEditorFixture):
    term = FakeTerminal(width=8, ps1=">>> ")
    ed = LineEditorFixture(term)

    await ed.feed_text("你好")  # each width=2
    layout = get_editor_layout(ed)

    # >>>  = 4
    # 你   = 2 -> 6
    # 好   = 2 -> 8 exact edge
    assert layout.pending_wrap is True
    assert layout.cursor_pos.row == 1
    assert layout.cursor_pos.col == 1


@pytest.mark.asyncio
async def test_mixed_unicode_wrap(LineEditorFixture):
    term = FakeTerminal(width=10, ps1=">>> ")
    ed = LineEditorFixture(term)

    await ed.feed_text("a🙂你b")
    layout = get_editor_layout(ed)

    # >>>  = 4
    # a    = 1 => 5
    # 🙂   = 2 => 7
    # 你   = 2 => 9
    # b    = 1 => 10 exact edge
    assert layout.pending_wrap is True
    assert layout.cursor_pos.row == 1
    assert layout.cursor_pos.col == 1