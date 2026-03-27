import typing as t
import logging
from wcwidth import wcswidth

logger = logging.getLogger(__name__)

class InputHandler:
    def __init__(self, session_io):
        self.session_io = session_io
        self._char_buffer: t.List[str] = []  # буфер символов
        self._byte_buffer: bytearray = bytearray()  # буфер байтов для команд

    async def input_bytes(self, data: bytes):
        await self.session_io.input_queue.put(data)

    async def input_str(self, data: str, encoding="utf-8"):
        await self.session_io.input_queue.put(data.encode(encoding))

    async def read_str(self, encoding="utf-8") -> t.Optional[str]:
        self._char_buffer.clear()
        self._byte_buffer.clear()

        while True:
            chunk = await self.session_io.input_queue.get()
            if not chunk:
                return None if not self._byte_buffer else self._byte_buffer.decode(encoding, errors="replace")

            i = 0
            while i < len(chunk):
                b = chunk[i]

                # Ctrl+C
                if b == 0x03:
                    self._char_buffer.clear()
                    self._byte_buffer.clear()
                    await self.session_io.output.output_bytes(b"^C\r\n")
                    return ""

                # Ctrl+D
                elif b == 0x04:
                    if not self._byte_buffer:
                        return None
                    i += 1
                    continue

                # Backspace / DEL
                elif b in (0x08, 0x7F):
                    if self._char_buffer:
                        last_char = self._char_buffer.pop()
                        # корректная ширина символа
                        width = wcswidth(last_char)
                        if width <= 0:
                            width = 1
                        # обрезаем соответствующее количество байт
                        self._byte_buffer = bytearray(
                            self._byte_buffer.decode(encoding, errors="replace")[:-len(last_char)].encode(encoding)
                        )
                        await self.session_io.output.output_bytes(b"\b" * width + b" " * width + b"\b" * width)
                    i += 1
                    continue

                # Enter
                elif b in (0x0D, 0x0A):
                    await self.session_io.output.output_bytes(b"\r\n")
                    result = self._byte_buffer.decode(encoding, errors="replace")
                    return result

                # Escape sequences игнорируем
                elif b == 0x1B:
                    i += 1
                    continue

                # обычные символы
                else:
                    # добавляем символ в буфер
                    try:
                        c = bytes([b])
                        while True:
                            try:
                                char = c.decode(encoding)
                                break
                            except UnicodeDecodeError:
                                i += 1
                                if i < len(chunk):
                                    c += bytes([chunk[i]])
                                else:
                                    # недополненный символ, подождем следующей порции байт
                                    i += 1
                                    break
                        else:
                            i += 1
                            continue

                        self._char_buffer.append(char)
                        self._byte_buffer += char.encode(encoding)
                        await self.session_io.output.output_str(char)
                    except Exception as e:
                        logger.exception("Char decode error: %s", e)

                i += 1