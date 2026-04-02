import pytest
from tests.testutils.terminal_fakes import FakeTerminal


@pytest.mark.asyncio
async def test_history_navigation_sets_draft(LineEditorFixture):
    term = FakeTerminal()
    ed = LineEditorFixture(term)

    ed.history.add("one")
    ed.history.add("two")

    await ed.feed_text("draft")
    await ed.history_up()

    assert ed._history_navigation_active is True
    assert "".join(ed._history_draft) == "draft"
    assert "".join(ed._buffer) == "two"


@pytest.mark.asyncio
async def test_history_down_restores_draft(LineEditorFixture):
    term = FakeTerminal()
    ed = LineEditorFixture(term)

    ed.history.add("one")
    ed.history.add("two")

    await ed.feed_text("draft")
    await ed.history_up()
    await ed.history_down()

    assert "".join(ed._buffer) == "draft"
    assert ed._history_navigation_active is False