import pytest
from tests.sshserver.terminal.testutils.fakes import FakeTerminal, push_and_read


@pytest.mark.asyncio
async def test_history_up_recalls_previous(InputHandlerFixture):
    term = FakeTerminal()
    ih = InputHandlerFixture(term)

    await push_and_read(ih, [b"first\r"])
    await push_and_read(ih, [b"second\r"])

    result = await push_and_read(ih, [b"\x1b[A", b"\r"])
    assert result == "second"


@pytest.mark.asyncio
async def test_history_up_twice_goes_older(InputHandlerFixture):
    term = FakeTerminal()
    ih = InputHandlerFixture(term)

    await push_and_read(ih, [b"one\r"])
    await push_and_read(ih, [b"two\r"])
    await push_and_read(ih, [b"three\r"])

    result = await push_and_read(ih, [b"\x1b[A", b"\x1b[A", b"\r"])
    assert result == "two"


@pytest.mark.asyncio
async def test_history_down_returns_to_newer(InputHandlerFixture):
    term = FakeTerminal()
    ih = InputHandlerFixture(term)

    await push_and_read(ih, [b"one\r"])
    await push_and_read(ih, [b"two\r"])
    await push_and_read(ih, [b"three\r"])

    result = await push_and_read(
        ih,
        [b"\x1b[A", b"\x1b[A", b"\x1b[B", b"\r"],
    )
    assert result == "three"


@pytest.mark.asyncio
async def test_history_draft_restored(InputHandlerFixture):
    term = FakeTerminal()
    ih = InputHandlerFixture(term)

    await push_and_read(ih, [b"alpha\r"])
    await push_and_read(ih, [b"beta\r"])

    result = await push_and_read(
        ih,
        [
            b"draft",
            b"\x1b[A",
            b"\x1b[B",
            b"\r",
        ],
    )
    assert result == "draft"


@pytest.mark.asyncio
async def test_history_empty_no_crash(InputHandlerFixture):
    term = FakeTerminal()
    ih = InputHandlerFixture(term)

    result = await push_and_read(
        ih,
        [b"\x1b[A", b"\r"],
    )
    assert result == ""