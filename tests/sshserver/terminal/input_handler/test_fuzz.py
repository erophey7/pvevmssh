import pytest
import random
import string
from tests.testutils.terminal_fakes import FakeTerminal, push_and_read


@pytest.mark.asyncio
async def test_random_ascii_inputs_do_not_crash(InputHandlerFixture):
    random.seed(1337)

    for _ in range(100):
        term = FakeTerminal()
        ih = InputHandlerFixture(term)

        s = "".join(random.choice(string.ascii_letters + string.digits + " _-./") for _ in range(50))
        result = await push_and_read(ih, [s.encode() + b"\r"])
        assert result == s


@pytest.mark.asyncio
async def test_random_backspaces_do_not_break_state(InputHandlerFixture):
    random.seed(42)

    term = FakeTerminal()
    ih = InputHandlerFixture(term)

    chunks = []
    text = []

    for _ in range(100):
        if random.random() < 0.25:
            chunks.append(b"\x7f")
            if text:
                text.pop()
        else:
            ch = random.choice(string.ascii_lowercase)
            chunks.append(ch.encode())
            text.append(ch)

    chunks.append(b"\r")
    result = await push_and_read(ih, chunks)

    assert result == "".join(text)