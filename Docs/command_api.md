# Документация API команд PVE SSH Server

**Версия документации:** 0.1 (после рефакторинга марта 2026)

## 1. Структура директории `commands/`

```text
commands/
├── internal/                  # Группа (категория) команд
│   ├── __init__.py            # Метаданные категории (опционально)
│   ├── about.py               # Single-file команда
│   └── edit/                  # Подкатегория
│       ├── __init__.py
│       └── config.py
├── pve/                       # Ещё одна категория
├── test/                      # Тестовые команды
└── __init__.py                # (опционально) корневая категория
```

**Правила:**
- Каждая папка = категория (group).
- Команда может быть:
  - **Single-file** (`*.py`)
  - **Command Module** (папка с `__init__.py` и `type: "command"`)

---

## 2. Типы команд

### 2.1. Single-file команда (`xxx.py`)

```python
# commands/internal/about.py
from sshserver.session.manager import get_current_session

async def execute(username: str, *args) -> str | None:
    session = get_current_session()
    return f"Hello, {username}! Your session UUID: {session.uuid}"

command = {
    "name": "about",                    # обязательно
    "help": "Show information about server and session",   # рекомендуется
    "func": execute,                    # обязательно
    # "permissions": [...]              # опционально (иначе наследуется от категории)
}
```

### 2.2. Command Module (команда-пакет)

```python
# commands/edit/__init__.py
async def execute(username: str, *args):
    ...

command = {
    "type": "command",                  # обязательно для модуля
    "name": "edit",
    "help": "Edit configuration",
    "func": execute,
    "permissions": ["config_edit"]
}
```

### 2.3. Категория (Group)

```python
# commands/internal/__init__.py
command = {
    "type": "category",
    "name": "internal",
    "help": "Internal server management commands",
    "permissions": ["internal_access"]   # будут наследоваться всем дочерним командам
}
```

> Если `__init__.py` в папке **отсутствует** или не содержит `command = {...}`, папка считается обычной категорией без дополнительных прав.

---

## 3. Система прав и наследование

Права наследуются **вниз** по дереву:

- `commands/` → `internal/` → `edit/` → `config.py`

**Правила наследования:**
- Команда наследует все права родительских категорий.
- Если в команде указаны свои `permissions` — они **объединяются** с наследованными.
- Если в итоге у команды **нет ни одного права** — она доступна **всем** пользователям.

Пример:

```python
# В internal/__init__.py
"permissions": ["internal_access"]

# В edit/__init__.py
"permissions": ["config_edit"]

# В edit/config.py
"permissions": ["config_write"]   # итоговые права: ["internal_access", "config_edit", "config_write"]
```

Проверка прав происходит автоматически в `CommandDispatcher`.

---

## 4. Как писать команды (рекомендуемый стиль)

```python
"""
Короткое описание команды.
"""

from sshserver.session.manager import get_current_session
from sshserver.terminal import Terminal   # если нужен прямой доступ


async def execute(username: str, *args) -> str | None:
    """
    Основная функция команды.
    """
    session = get_current_session()
    terminal: Terminal = session.extra["terminal"]

    # Пример работы с окружением
    env = session.extra["env"]
    env.set("CUSTOM_VAR", "value")

    return "Command executed successfully"


command = {
    "name": "mycommand",
    "help": "One-line description for help",
    "func": execute,
    # "permissions": ["some_perm"]   # опционально
}
```

---

## 5. Работа с окружением (`UserEnvironment`)

Доступно через `session.extra["env"]`:

```python
env = session.extra["env"]          # объект UserEnvironment

env.set("PS1", "pve> ")
env.set("EDITOR", "nano")
value = env.get("USER")
env.unset("TEMP_VAR")

# Поддержка подстановки $VAR в строках
text = env.substitute("Hello $USER, your TERM is $TERM")
```

Также доступны глобальные методы:
- `env.export("VAR=value")` — как в shell
- `env.substitute(text)` — замена `$VAR`

---

## 6. Поддержка мыши

```python
from sshserver.terminal.mouse_handler import MouseEvent

async def on_mouse_event(event: MouseEvent):
    msg = f"\r\n[Mouse] {event.state} btn={event.button} ({event.x},{event.y})"
    await terminal.output.output_str(msg)

# В команде:
mouse = terminal.input.mouse
await mouse.enable()                    # mode=1006 по умолчанию
mouse.add_listener(on_mouse_event)

# При отключении
await mouse.disable()
mouse.remove_listener(on_mouse_event)
```

**События:** `press`, `release`, `motion`

---

## 7. Работа с PTY

```python
# Получить PTY (для запуска subprocess, подключения к VM и т.д.)
pty = terminal.pty

await pty.ensure()                      # создать PTY, если ещё нет
slave_fd = pty.get_slave_fd()           # для subprocess.Popen(..., stdin=slave_fd, ...)

# Изменение размера
await pty.resize(rows=24, cols=80)

# Подключить потоки (bridge SSH ↔ PTY)
await pty.attach_streams()
await pty.detach_streams()
```

---

## 8. Полезные объекты, доступные в командах

| Объект                        | Как получить                              | Назначение                     |
|------------------------------|-------------------------------------------|--------------------------------|
| `session`                    | `get_current_session()`                   | Информация о текущей сессии   |
| `terminal`                   | `session.extra["terminal"]`               | Полный контроль над IO        |
| `env`                        | `session.extra["env"]`                    | Переменные окружения          |
| `dispatcher`                 | уже в `run_session`                       | Для вызова других команд      |
| `GlobalStore`                | `from helpers.globals import GlobalStore` | Доступ к config и глобальным данным |

---

## 9. Полный пример современной команды

```python
# commands/internal/whoami.py
from sshserver.session.manager import get_current_session
from sshserver.terminal.mouse_handler import MouseEvent

async def on_click(event: MouseEvent):
    await terminal.output.output_str(f"\r\nClicked at ({event.x}, {event.y})\r\n")

async def execute(username: str, *args):
    global terminal
    session = get_current_session()
    terminal = session.extra["terminal"]

    await terminal.output.output_str(f"\r\nYou are {username} (group: {session.extra['group_name']})\r\n")
    await terminal.output.output_str("Your permissions: " + ", ".join(session.extra["permissions"]) + "\r\n")

    # Пример включения мыши
    mouse = terminal.input.mouse
    await mouse.enable()
    mouse.add_listener(on_click)

    return "\nMouse enabled. Click anywhere!"
    

command = {
    "name": "whoami",
    "help": "Show current user, group and permissions",
    "func": execute
}
```

