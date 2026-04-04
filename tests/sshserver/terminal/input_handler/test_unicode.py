import pytest
from tests.sshserver.terminal.testutils.fakes import FakeTerminal, push_and_read


@pytest.mark.asyncio
async def test_cyrillic_input(InputHandlerFixture):
    term = FakeTerminal()
    ih = InputHandlerFixture(term)

    text = "привет"
    result = await push_and_read(ih, [text.encode("utf-8") + b"\r"])
    assert result == text


@pytest.mark.asyncio
async def test_emoji_input(InputHandlerFixture):
    term = FakeTerminal()
    ih = InputHandlerFixture(term)

    text = "hi🙂"
    result = await push_and_read(ih, [text.encode("utf-8") + b"\r"])
    assert result == text


@pytest.mark.asyncio
async def test_combining_mark_input(InputHandlerFixture):
    term = FakeTerminal()
    ih = InputHandlerFixture(term)

    text = "e\u0301"
    result = await push_and_read(ih, [text.encode("utf-8") + b"\r"])
    assert result == text


@pytest.mark.asyncio
async def test_wide_cjk_input(InputHandlerFixture):
    term = FakeTerminal()
    ih = InputHandlerFixture(term)

    text = "你好世界"
    result = await push_and_read(ih, [text.encode("utf-8") + b"\r"])
    assert result == text