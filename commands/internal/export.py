"""
Команда export: установка переменных окружения.
"""

from sshserver.sessions import get_current_session
from sshserver.environment import UserEnvironment

def export(username: str, *args) -> str:
    """Устанавливает переменные окружения."""
    if not args:
        # Без аргументов: показать все переменные
        session = get_current_session()
        env = session.extra.get('env') if session else None
        if not env:
            return "No environment set.\n"
        # Если env — словарь (старый формат), преобразуем
        if isinstance(env, dict):
            env = UserEnvironment()
            for k, v in env.items():
                env.set(k, v)
            session.extra['env'] = env
        # Получаем все переменные
        lines = [f"{k}={v}" for k, v in env._vars.items()]  # доступ к protected, но ок для простоты
        return "\n".join(lines) + "\n" if lines else "No variables set.\n"

    # Объединяем все аргументы в одну строку для поддержки пробелов
    line = ' '.join(args)
    session = get_current_session()
    env = session.extra.get('env') if session else None
    if not env:
        env = UserEnvironment()
        session.extra['env'] = env
    elif isinstance(env, dict):
        # Преобразуем словарь в объект UserEnvironment
        new_env = UserEnvironment()
        for k, v in env.items():
            new_env.set(k, v)
        env = new_env
        session.extra['env'] = env

    # Используем метод export из UserEnvironment
    result = env.export(line)
    if result:
        return result
    return "Environment variables set.\n"


command = {
    "name": "export",
    "help": "Set or display environment variables",
    "func": export
}