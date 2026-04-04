import pytest

from tests.sshserver.terminal.testutils import FakeTerminal
from tests.sshserver.terminal.testutils.line_editor import get_editor_layout, layout_rows_text




@pytest.mark.asyncio
async def test_cursor_middle_position_mapping(LineEditorFixture):
    term = FakeTerminal(width=20, ps1=">>> ")
    ed = LineEditorFixture(term)

    await ed.feed_text("abcdef")
    await ed.cursor_left()
    await ed.cursor_left()

    layout = get_editor_layout(ed)
    rows = layout_rows_text(layout)
    assert rows[0] == ">>> abcdef"
    assert layout.cursor_pos.row == 0
    assert layout.cursor_pos.col == 9