import pytest
from tests.testutils.terminal_fakes import FakeTerminal


@pytest.mark.asyncio
async def test_custom_prompt_used(LineEditorFixture):
    term = FakeTerminal(ps1="user@host$ ")
    ed = LineEditorFixture(term)

    await ed.feed_text("ls")
    layout = ed._build_layout()

    assert "user@host$ " in layout.rendered_text


@pytest.mark.asyncio
async def test_default_prompt_fallback(LineEditorFixture):
    term = FakeTerminal()
    term.session.extra["env"] = {}
    ed = LineEditorFixture(term)

    await ed.feed_text("ls")
    layout = ed._build_layout()

    assert ">>> " in layout.rendered_text