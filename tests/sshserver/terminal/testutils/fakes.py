import asyncio


class FakeOutput:
    def __init__(self):
        self.writes = []

    async def output_bytes(self, data: bytes):
        self.writes.append(data)

    def joined(self) -> bytes:
        return b"".join(self.writes)

    def clear(self):
        self.writes.clear()


class FakeSession:
    def __init__(self, width=80, height=24, ps1=">>> "):
        self.term_width = width
        self.term_height = height
        self.extra = {"env": {"PS1": ps1}}


class FakeTerminal:
    def __init__(self, width=80, height=24, ps1=">>> "):
        self.input_queue = asyncio.Queue()
        self.output = FakeOutput()
        self.session = FakeSession(width=width, height=height, ps1=ps1)


async def push_and_read(handler, chunks):
    task = asyncio.create_task(handler.read_str())
    await asyncio.sleep(0)

    for chunk in chunks:
        await handler.input_bytes(chunk)
        await asyncio.sleep(0)

    return await task