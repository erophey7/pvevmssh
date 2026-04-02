import pytest
from tests.testutils.terminal_fakes import FakeTerminal, push_and_read


@pytest.mark.asyncio
async def test_bulk_paste(InputHandlerFixture):
    term = FakeTerminal()
    ih = InputHandlerFixture(term)

    text = "this is a pasted line with spaces and symbols _-./123"
    result = await push_and_read(ih, [text.encode() + b"\r"])
    assert result == text


@pytest.mark.asyncio
async def test_fragmented_escape_sequence(InputHandlerFixture):
    term = FakeTerminal()
    ih = InputHandlerFixture(term)

    result = await push_and_read(
        ih,
        [
            b"abc",
            b"\x1b",
            b"[",
            b"D",
            b"X",
            b"\r",
        ],
    )
    assert result == "abXc"


@pytest.mark.asyncio
async def test_unknown_escape_ignored(InputHandlerFixture):
    term = FakeTerminal()
    ih = InputHandlerFixture(term)

    result = await push_and_read(
        ih,
        [
            b"abc",
            b"\x1bX",
            b"\r",
        ],
    )
    assert result == "abc"


@pytest.mark.asyncio
async def test_partial_utf8_waits(InputHandlerFixture):
    term = FakeTerminal()
    ih = InputHandlerFixture(term)

    euro = "€".encode("utf-8")
    result = await push_and_read(
        ih,
        [
            euro[:1],
            euro[1:],
            b"\r",
        ],
    )
    assert result == "€"