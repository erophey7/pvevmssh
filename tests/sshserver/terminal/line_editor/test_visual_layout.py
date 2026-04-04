import pytest

from tests.sshserver.terminal.testutils import FakeTerminal
from tests.sshserver.terminal.testutils.line_editor import get_editor_layout, layout_rows_text



@pytest.mark.asyncio
async def test_long_prompt_affects_wrap(LineEditorFixture):
    term = FakeTerminal(width=12, ps1="user@host$ ")
    ed = LineEditorFixture(term)

    await ed.feed_text("ls")
    layout = get_editor_layout(ed)

    # Фактический рендер учитывает wrap
    rows = layout_rows_text(layout)

    # Проверяем текст по строкам
    assert rows == [
        "user@host$ l",  # 12 колонок (wrap)
        "s",             # остаток
    ]

    # Курсор после последнего символа
    assert layout.cursor_pos.row == 1
    assert layout.cursor_pos.col == 2

    # Проверяем общий рендерированный текст
    assert layout.rendered_text == "user@host$ l\ns"


@pytest.mark.asyncio
async def test_wrap_into_two_rows(LineEditorFixture):
    term = FakeTerminal(width=8, ps1=">>> ")
    ed = LineEditorFixture(term)

    await ed.feed_text("1234567890")
    layout = get_editor_layout(ed)

    rows = layout_rows_text(layout)
    assert rows == [
        ">>> 1234",
        "567890",
    ]
    assert layout.cursor_pos.row == 1
    assert layout.cursor_pos.col == 7


@pytest.mark.asyncio
async def test_wrap_after_one_extra_char(LineEditorFixture):
    term = FakeTerminal(width=8, ps1=">>> ")
    ed = LineEditorFixture(term)

    await ed.feed_text("12345")
    layout = get_editor_layout(ed)

    rows = layout_rows_text(layout)
    assert rows == [
        ">>> 1234",
        "5",
    ]
    assert layout.cursor_pos.row == 1
    assert layout.cursor_pos.col == 2


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