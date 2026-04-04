import pytest

from tests.sshserver.terminal.testutils import FakeTerminal
from tests.sshserver.terminal.testutils.line_editor import get_editor_layout, layout_rows_text




@pytest.mark.asyncio
async def test_invisible_prompt_does_not_consume_width(LineEditorFixture):
    term = FakeTerminal(width=10, ps1="\\[\x1b[31m\\]RED\\[\x1b[0m\\]> ")
    ed = LineEditorFixture(term)

    await ed.feed_text("abc")
    layout = get_editor_layout(ed)

    # ANSI should still be present in rendered output
    assert "\x1b[31m" in layout.rendered_text
    assert "\x1b[0m" in layout.rendered_text

    # But visible prompt width should be only "RED> " = 5
    # so cursor after "abc" should be at col 9
    assert layout.cursor_pos.row == 0
    assert layout.cursor_pos.col == 9


@pytest.mark.asyncio
async def test_prompt_only_exact_edge(LineEditorFixture):
    term = FakeTerminal(width=4, ps1=">>> ")
    ed = LineEditorFixture(term)

    layout = get_editor_layout(ed)

    assert layout.rendered_text == ">>> "
    assert layout.pending_wrap is True
    assert layout.cursor_pos.row == 1
    assert layout.cursor_pos.col == 1