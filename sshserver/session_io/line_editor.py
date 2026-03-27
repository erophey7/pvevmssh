import asyncio
from sshserver.session_env.history import CommandHistory
import wcwidth

class LineEditor:
    """
    Полноценный line editor:
    - стрелки, ctrl+стрелки
    - backspace / ctrl+backspace
    - delete / ctrl+delete
    - история
    - UTF-8 корректно
    """

    def __init__(self, session_io):
        self.session_io = session_io
        self.chars = []  # список символов
        self.cursor = 0
        self.history = CommandHistory()
        self._encoding = 'utf-8'

    async def read_line(self) -> str | None:
        """
        Чтение строки с поддержкой истории и стрелок.
        Возвращает None при EOF / Ctrl+D на пустой строке.
        """
        self.chars.clear()
        self.cursor = 0
        self.history.reset_index()

        while True:
            chunk = await self.session_io.input_queue.get()
            if chunk is None:
                return None

            # декодируем байты безопасно
            try:
                text = chunk.decode(self._encoding)
            except UnicodeDecodeError:
                text = chunk.decode(self._encoding, errors='replace')

            i = 0
            while i < len(text):
                c = text[i]

                # Ctrl+C
                if c == '\x03':
                    await self.session_io.output.output_str('^C\r\n')
                    return ''

                # Ctrl+D
                if c == '\x04':
                    if not self.chars:
                        return None
                    i += 1
                    continue

                # Enter
                if c in ('\r', '\n'):
                    await self.session_io.output.output_str('\r\n')
                    line = ''.join(self.chars)
                    self.history.push(line)
                    return line

                # Backspace / DEL
                if c in ('\x08', '\x7f'):
                    await self._handle_backspace()
                    i += 1
                    continue

                # Ctrl+W / Ctrl+Backspace
                if c == '\x17':
                    await self._handle_ctrl_backspace()
                    i += 1
                    continue

                # Escape sequences (стрелки, ctrl+стрелки, del)
                if c == '\x1b':
                    seq = c
                    i += 1
                    while i < len(text) and len(seq) < 10:
                        seq += text[i]
                        i += 1
                        if seq.endswith('~') or seq.endswith(('A','B','C','D')):
                            break
                    await self._handle_escape(seq)
                    continue

                # обычные символы
                self.chars.insert(self.cursor, c)
                await self.session_io.output.output_str(c)
                self.cursor += 1
                i += 1

    async def _handle_backspace(self):
        if self.cursor == 0:
            return
        self.cursor -= 1
        ch = self.chars.pop(self.cursor)
        width = max(wcwidth.wcwidth(ch), 1)
        await self.session_io.output.output_str('\b' * width + ' ' * width + '\b' * width)

    async def _handle_ctrl_backspace(self):
        # удаляем до начала слова
        if self.cursor == 0:
            return
        while self.cursor > 0 and self.chars[self.cursor-1].isspace():
            self.cursor -= 1
            self.chars.pop(self.cursor)
            await self.session_io.output.output_str('\b \b')
        while self.cursor > 0 and not self.chars[self.cursor-1].isspace():
            self.cursor -= 1
            self.chars.pop(self.cursor)
            await self.session_io.output.output_str('\b \b')

    async def _handle_escape(self, seq: str):
        # стрелки
        if seq.endswith('D'):  # ←
            if self.cursor > 0:
                self.cursor -= 1
                await self.session_io.output.output_str('\x1b[D')
        elif seq.endswith('C'):  # →
            if self.cursor < len(self.chars):
                await self.session_io.output.output_str('\x1b[C')
                self.cursor += 1
        elif seq.endswith('A'):  # ↑
            prev = self.history.prev()
            if prev is not None:
                await self._replace_line(prev)
        elif seq.endswith('B'):  # ↓
            nxt = self.history.next()
            if nxt is not None:
                await self._replace_line(nxt)
            else:
                await self._replace_line('')
        elif seq.endswith('~'):
            # DEL или ctrl+DEL
            if seq.startswith('\x1b[3'):  # DEL
                if self.cursor < len(self.chars):
                    self.chars.pop(self.cursor)
                    await self.session_io.output.output_str(' ')
                    await self.session_io.output.output_str('\b')
            # ctrl+DEL может быть 3;5~
            # игнорируем пока, можно расширить по желанию

    async def _replace_line(self, new: str):
        # стираем текущую строку
        while self.cursor > 0:
            ch = self.chars.pop(0)
            width = max(wcwidth.wcwidth(ch), 1)
            await self.session_io.output.output_str('\b' * width + ' ' * width + '\b' * width)
            self.cursor -= 1
        # вставляем новую
        self.chars = list(new)
        self.cursor = len(self.chars)
        await self.session_io.output.output_str(new)