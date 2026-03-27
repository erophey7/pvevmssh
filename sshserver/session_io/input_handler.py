import typing as t
import logging
import codecs

logger = logging.getLogger(__name__)


class InputHandler:
    """
    Обработка входящих данных.
    Поддержка:
    - raw bytes
    - строкового ввода (UTF-8)
    - локальной line discipline:
        * Enter
        * Backspace
        * Ctrl+C
        * Ctrl+D
        * echo
    """

    def __init__(self, session_io):
        self.session_io = session_io
        self._buffer = bytearray()
        self._utf8_decoder = codecs.getincrementaldecoder("utf-8")()

    async def input_bytes(self, data: bytes):
        """Вручную добавить байты во входную очередь."""
        await self.session_io.input_queue.put(data)

    async def input_str(self, data: str, encoding="utf-8"):
        """Вручную добавить строку во входную очередь."""
        await self.session_io.input_queue.put(data.encode(encoding))

    async def read_bytes(self) -> t.Optional[bytes]:
        """Получить следующий кусок raw bytes."""
        return await self.session_io.input_queue.get()

    async def read_str(self, encoding="utf-8") -> t.Optional[str]:
        """
        Полноценное чтение одной строки с поддержкой UTF-8.

        Возвращает:
        - str   -> строка команды
        - ""    -> Ctrl+C
        - None  -> EOF / Ctrl+D на пустой строке / disconnect
        """
        self._buffer.clear()
        self._utf8_decoder.reset()

        while True:
            chunk = await self.session_io.input_queue.get()

            if chunk is None:
                if self._buffer:
                    return self._utf8_decoder.decode(bytes(self._buffer), final=True)
                return None

            if not chunk:
                if self._buffer:
                    return self._utf8_decoder.decode(bytes(self._buffer), final=True)
                return None

            for b in chunk:
                # Ctrl+C
                if b == 0x03:
                    self._buffer.clear()
                    self._utf8_decoder.reset()
                    await self.session_io.output.output_bytes(b"^C\r\n")
                    return ""

                # Ctrl+D
                if b == 0x04:
                    if not self._buffer:
                        return None
                    continue

                # Backspace / DEL
                if b in (0x08, 0x7F):
                    if self._buffer:
                        self._buffer.pop()
                        await self.session_io.output.output_bytes(b"\b \b")
                    continue

                # Enter (\r или \n)
                if b in (0x0D, 0x0A):
                    line = self._utf8_decoder.decode(bytes(self._buffer), final=True)
                    self._buffer.clear()
                    self._utf8_decoder.reset()
                    await self.session_io.output.output_bytes(b"\r\n")
                    return line

                # Escape sequence start (стрелки и прочее пока игнорируем)
                if b == 0x1B:
                    continue

                # Печатные символы
                self._buffer.append(b)
                try:
                    # безопасное эхо символа
                    char = self._utf8_decoder.decode(bytes([b]))
                    if char:
                        await self.session_io.output.output_str(char)
                except UnicodeDecodeError:
                    # если байт часть многобайтовой последовательности, пропускаем пока не наберется полная последовательность
                    pass