import logging

logger = logging.getLogger(__name__)


class OutputHandler:
    """
    Обработка вывода.
    Всё отдаётся в raw bytes.
    Строковый вывод автоматически нормализует переводы строк в CRLF.
    """

    def __init__(self, session_io):
        self.session_io = session_io

    async def output_bytes(self, data: bytes):
        """Отправить сырые байты в stdout"""
        async with self.session_io.output_lock:
            self.session_io.process.stdout.write(data)

    async def output_str(self, data: str, encoding="utf-8"):
        """
        Отправить строку в stdout с нормализацией \n -> \r\n
        """
        normalized = self._normalize_newlines(data)
        await self.output_bytes(normalized.encode(encoding, errors="replace"))

    async def error_bytes(self, data: bytes):
        """Отправить сырые байты в stderr"""
        async with self.session_io.output_lock:
            self.session_io.process.stderr.write(data)

    async def error_str(self, data: str, encoding="utf-8"):
        """
        Отправить строку в stderr с нормализацией \n -> \r\n
        """
        normalized = self._normalize_newlines(data)
        await self.error_bytes(normalized.encode(encoding, errors="replace"))

    @staticmethod
    def _normalize_newlines(data: str) -> str:
        """
        Приводит любые переводы строк к tty-safe формату \r\n
        """
        data = data.replace("\r\n", "\n")
        data = data.replace("\r", "\n")
        return data.replace("\n", "\r\n")