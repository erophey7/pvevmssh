"""
Команда mouse: включает/выключает режим мыши в терминале.
Отправляет escape-последовательности для включения/выключения отслеживания мыши.
"""

from sshserver.sessions import get_current_session

def mouse(username: str, *args) -> str:
    """
    Использование: mouse [on|off]
    Включает или выключает режим мыши в терминале.
    """
    session = get_current_session()
    if not session:
        return "No session found.\n"
    process = session.extra.get('process')
    if not process:
        return "No process found in session.\n"

    # Определяем, нужно включить или выключить
    enable = False
    if args and args[0].lower() == 'on':
        enable = True
    elif args and args[0].lower() == 'off':
        enable = False
    else:
        # Если аргумент не указан, показываем текущее состояние (просто справка)
        return "Usage: mouse on|off\n"

    # Escape-последовательности для мыши
    # Для включения: CSI ? 1000 h (включить обычный режим мыши)
    # Для выключения: CSI ? 1000 l
    # Можно также добавить другие режимы: 1002 (кнопки и движение), 1003 (все движения)
    # Пока используем базовый режим.
    if enable:
        process.stdout.write("\033[?1000h")   # включить мышь
        return "Mouse reporting enabled.\n"
    else:
        process.stdout.write("\033[?1000l")   # выключить мышь
        return "Mouse reporting disabled.\n"


command = {
    "name": "mouse",
    "help": "Enable or disable mouse reporting",
    "func": mouse
}