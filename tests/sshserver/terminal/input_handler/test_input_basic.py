import pytest
from tests.testutils.terminal_fakes import FakeTerminal, push_and_read


@pytest.mark.asyncio
async def test_simple_ascii(InputHandlerFixture):
    term = FakeTerminal()
    ih = InputHandlerFixture(term)

    result = await push_and_read(ih, [b"hello\r"])
    assert result == "hello"


@pytest.mark.asyncio
async def test_empty_enter(InputHandlerFixture):
    term = FakeTerminal()
    ih = InputHandlerFixture(term)

    result = await push_and_read(ih, [b"\r"])
    assert result == ""


@pytest.mark.asyncio
async def test_ctrl_c_returns_empty_line(InputHandlerFixture):
    term = FakeTerminal()
    ih = InputHandlerFixture(term)

    result = await push_and_read(ih, [b"abc", b"\x03"])
    assert result == ""


@pytest.mark.asyncio
async def test_ctrl_d_on_empty_returns_eof(InputHandlerFixture):
    from sshserver.terminal.types import EOF

    term = FakeTerminal()
    ih = InputHandlerFixture(term)

    result = await push_and_read(ih, [b"\x04"])
    assert result is EOF


@pytest.mark.asyncio
async def test_ctrl_d_on_non_empty_does_not_finish(InputHandlerFixture):
    term = FakeTerminal()
    ih = InputHandlerFixture(term)

    result = await push_and_read(ih, [b"abc", b"\x04", b"\r"])
    assert result == "abc"


@pytest.mark.asyncio
async def test_crlf_handled_as_single_enter(InputHandlerFixture):
    term = FakeTerminal()
    ih = InputHandlerFixture(term)

    result = await push_and_read(ih, [b"hello\r\n"])
    assert result == "hello"


@pytest.mark.asyncio
async def test_lfcr_handled_as_single_enter(InputHandlerFixture):
    term = FakeTerminal()
    ih = InputHandlerFixture(term)

    result = await push_and_read(ih, [b"hello\n\r"])
    assert result == "hello"