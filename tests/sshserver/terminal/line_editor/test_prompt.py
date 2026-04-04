import pytest
from tests.sshserver.terminal.testutils.fakes import FakeTerminal
from tests.sshserver.terminal.testutils.line_editor import get_editor_layout


@pytest.mark.asyncio
async def test_custom_prompt_used(LineEditorFixture):
    term = FakeTerminal(ps1="user@host$ ")
    ed = LineEditorFixture(term)

    await ed.feed_text("ls")
    layout = get_editor_layout(ed)

    assert "user@host$ " in layout.rendered_text


@pytest.mark.asyncio
async def test_default_prompt_fallback(LineEditorFixture):
    term = FakeTerminal()
    term.session.extra["env"] = {}
    ed = LineEditorFixture(term)

    await ed.feed_text("ls")
    layout = get_editor_layout(ed)

    assert ">>> " in layout.rendered_text