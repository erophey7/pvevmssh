"""
Команда echo: вывод аргументов с поддержкой переменных окружения и опций.
По умолчанию интерпретирует escape-последовательности.
"""

import re
from sshserver.sessions import get_current_session


def echo(username: str, *args) -> str:
    """
    Выводит аргументы.
    Опции:
      -n   не добавлять перевод строки
      -E   отключить интерпретацию escape-последовательностей (по умолчанию включена)
    """
    if not args:
        return ""

    # Парсим опции
    no_newline = True
    interpret = True   # по умолчанию интерпретируем
    output_args = []
    for arg in args:
        if arg == "-n":
            no_newline = False
        elif arg == "-E":
            interpret = False
        else:
            output_args.append(arg)

    # Получаем окружение из текущей сессии
    session = get_current_session()
    env = session.extra.get('env') if session else None

    # Функция подстановки переменных
    def expand_vars(text: str) -> str:
        if not env:
            return text
        # Если env объект UserEnvironment, используем его метод substitute
        if hasattr(env, 'substitute'):
            return env.substitute(text)
        # Если env — словарь (старый формат), заменяем вручную
        for key, val in env.items():
            text = text.replace(f"${key}", val)
        return text

    # Убираем внешние кавычки, если аргумент полностью в кавычках
    def strip_quotes(s: str) -> str:
        if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
            return s[1:-1]
        return s

    # Обрабатываем каждый аргумент
    result_parts = []
    for arg in output_args:
        # Убираем кавычки
        arg = strip_quotes(arg)
        # Подстановка переменных
        arg = expand_vars(arg)
        # Интерпретация escape-последовательностей
        if interpret:
            arg = arg.replace('\\n', '\n')
            arg = arg.replace('\\t', '\t')
            arg = arg.replace('\\r', '\r')
            arg = arg.replace('\\\\', '\\')
        result_parts.append(arg)

    output = ' '.join(result_parts)
    if not no_newline:
        output += '\n'
    return output


command = {
    "name": "echo",
    "help": "Display arguments with variable expansion (default: interpret escapes)",
    "func": echo
}