import pytest
from tests.testutils.terminal_fakes import FakeTerminal, push_and_read


@pytest.mark.asyncio
async def test_backspace(InputHandlerFixture):
    term = FakeTerminal()
    ih = InputHandlerFixture(term)

    result = await push_and_read(ih, [b"hellx", b"\x7f", b"o\r"])
    assert result == "hello"


@pytest.mark.asyncio
async def test_left_insert_middle(InputHandlerFixture):
    term = FakeTerminal()
    ih = InputHandlerFixture(term)

    result = await push_and_read(
        ih,
        [
            b"helo",
            b"\x1b[D",
            b"\x1b[D",
            b"l",
            b"\r",
        ],
    )
    assert result == "hello"


@pytest.mark.asyncio
async def test_home_insert_prefix(InputHandlerFixture):
    term = FakeTerminal()
    ih = InputHandlerFixture(term)

    result = await push_and_read(
        ih,
        [
            b"world",
            b"\x1b[H",
            b"hello ",
            b"\r",
        ],
    )
    assert result == "hello world"


@pytest.mark.asyncio
async def test_end_insert_suffix(InputHandlerFixture):
    term = FakeTerminal()
    ih = InputHandlerFixture(term)

    result = await push_and_read(
        ih,
        [
            b"hello",
            b"\x1b[H",
            b"\x1b[F",
            b" world",
            b"\r",
        ],
    )
    assert result == "hello world"


@pytest.mark.asyncio
async def test_delete_key(InputHandlerFixture):
    term = FakeTerminal()
    ih = InputHandlerFixture(term)

    result = await push_and_read(
        ih,
        [
            b"heXllo",
            b"\x1b[D",
            b"\x1b[D",
            b"\x1b[D",
            b"\x1b[D",
            b"\x1b[3~",
            b"\r",
        ],
    )
    assert result == "hello"


@pytest.mark.asyncio
async def test_delete_at_end_does_nothing(InputHandlerFixture):
    term = FakeTerminal()
    ih = InputHandlerFixture(term)

    result = await push_and_read(
        ih,
        [
            b"hello",
            b"\x1b[3~",
            b"\r",
        ],
    )
    assert result == "hello"


@pytest.mark.asyncio
async def test_backspace_at_start_does_nothing(InputHandlerFixture):
    term = FakeTerminal()
    ih = InputHandlerFixture(term)

    result = await push_and_read(
        ih,
        [
            b"\x7f",
            b"hello\r",
        ],
    )
    assert result == "hello"