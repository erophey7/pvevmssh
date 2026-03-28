# документация API команд PVE SSH Server

**Версия документации:** 0.2 (апрель 2026)

---

## 1. Структура директории `commands/`

```
commands/
├── internal/                  # Группа (категория) команд
│   ├── __init__.py            # Метаданные категории
│   ├── about.py               # Single-file команда
│   ├── echo.py
│   ├── export.py
│   ├── sessions.py
│   └── whoami.py
├── pve/                       # Категория для Proxmox VE
│   ├── __init__.py
│   └── bash.py                # Запуск интерактивного bash
├── test/                      # Тестовые команды
│   ├── __init__.py
│   ├── char.py
│   ├── color.py
│   └── mouse.py
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
    "permissions": []                   # права наследуются всем дочерним командам
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

### Включение и отключение

```python
mouse = terminal.input.mouse

# Включить один режим (1000, 1002, 1003)
await mouse.enable(1000)

# Включить несколько режимов одновременно (например, 1002 + 1006)
await mouse.enable([1002, 1006])

# Отключить все активные режимы
await mouse.disable()

# Отключить конкретный режим
await mouse.disable(1006)
```

### Обработка событий

```python
from sshserver.terminal.mouse_handler import MouseEvent

async def on_mouse_event(event: MouseEvent):
    if event.wheel:
        print(f"Wheel: {'up' if event.wheel > 0 else 'down'}")
    else:
        print(f"Button {event.button} {event.state} at ({event.x}, {event.y})")

mouse.add_listener(on_mouse_event)
```

**Свойства `MouseEvent`:**
- `button`: 0 = левая, 1 = средняя, 2 = правая (для колёсика не определено)
- `x`, `y`: координаты (1-based)
- `state`: `'press'`, `'release'`, `'motion'`
- `wheel`: 0 = нет, 1 = вверх, -1 = вниз
- `modifiers`: битовая маска модификаторов (пока не используется)

**Режимы мыши (xterm):**
- `1000`: обычный режим (нажатия и отпускания кнопок)
- `1002`: режим с отслеживанием движений (события при движении с нажатой кнопкой)
- `1003`: все движения (любое движение мыши)
- `1006`: расширенный SGR-формат координат (всегда рекомендуется включать вместе с основным режимом)

**Примечание:** для работы колёсика достаточно любого из основных режимов (1000, 1002, 1003). События колёсика приходят как `press` с `wheel` = ±1 и `button` = 0.

---

## 7. Работа с PTY

PTYHandler предоставляет низкоуровневые методы для работы с псевдотерминалом, а также удобный метод `spawn` для запуска интерактивных процессов.

### 7.1. Базовые операции

```python
pty = terminal.pty

await pty.ensure()                      # создать PTY, если ещё нет
slave_fd = pty.get_slave_fd()           # для subprocess.Popen(..., stdin=slave_fd, ...)

# Изменение размера
await pty.resize(rows=24, cols=80)

# Подключить потоки (bridge SSH ↔ PTY)
await pty.attach_streams()
await pty.detach_streams()
```

### 7.2. Запуск интерактивных программ (метод `spawn`)

Для запуска программ, которым требуется управляющий терминал (bash, vim, ssh и т.д.), рекомендуется использовать метод `spawn`. Он автоматически:
- создаёт PTY (если не создан),
- настраивает его как управляющий терминал (вызов `setsid` и `TIOCSCTTY`),
- запускает процесс с использованием slave-дескриптора для stdin/out/err,
- устанавливает owner PID для корректной передачи SIGWINCH,
- по желанию прикрепляет потоки SSH ↔ PTY.

**Сигнатура:**
```python
async def spawn(self, program: str, *args, env=None, cwd=None, attach_streams=True, **kwargs) -> asyncio.subprocess.Process
```

**Параметры:**
- `program` – путь к исполняемому файлу.
- `*args` – аргументы командной строки.
- `env` – словарь переменных окружения (по умолчанию копия `os.environ`).
- `cwd` – рабочая директория.
- `attach_streams` – если `True`, автоматически вызывает `attach_streams()` после запуска.
- `**kwargs` – дополнительные параметры для `asyncio.create_subprocess_exec` (например, `limit`, `start_new_session`).

**Пример использования:**
```python
proc = await terminal.pty.spawn(
    "bash",
    env={"TERM": "xterm-256color", "PS1": "\\u@\\h:\\w\\$ "},
    attach_streams=True
)
await proc.wait()
await terminal.pty.detach_streams()
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

## 9. Примеры команд

### 9.1. Простая команда с выводом информации (`whoami`)

```python
# commands/internal/whoami.py
from sshserver.session.manager import get_current_session

async def execute(username: str, *args):
    session = get_current_session()
    terminal = session.extra["terminal"]

    await terminal.output.output_str(f"\r\nYou are {username} (group: {session.extra['group_name']})\r\n")
    await terminal.output.output_str("Your permissions: " + ", ".join(session.extra["permissions"]) + "\r\n")

command = {
    "name": "whoami",
    "help": "Show current user, group and permissions",
    "func": execute
}
```

### 9.2. Запуск интерактивного bash (рекомендуемый способ)

Использует `pty.spawn` – простой и надёжный.

```python
# commands/pve/bash.py
from sshserver.session.manager import get_current_session

async def execute(username: str, *args) -> None:
    session = get_current_session()
    terminal = session.extra["terminal"]
    env = session.extra["env"]

    process_env = {
        "TERM": env.get("TERM", "xterm-256color"),
        "PS1": env.get("PS1", "\\u@\\h:\\w\\$ "),
    }

    proc = await terminal.pty.spawn(
        "bash",
        env=process_env,
        attach_streams=True,
    )

    await proc.wait()
    await terminal.pty.detach_streams()
    return None

command = {
    "name": "bash",
    "help": "Start an interactive Bash shell",
    "func": execute,
    "permissions": ["poweruser_permission"]   # пример ограничения прав
}
```

### 9.3. Запуск интерактивного bash (ручная настройка PTY)

Этот пример демонстрирует низкоуровневые операции, которые скрыты внутри `spawn`. Полезен для понимания или при необходимости тонкой настройки.

```python
# commands/pve/bash_manual.py
import asyncio
import os
import fcntl
import termios
from sshserver.session.manager import get_current_session

def _setup_pty(slave_fd: int):
    """В дочернем процессе: стать лидером сессии и назначить slave_fd управляющим терминалом."""
    os.setsid()
    fcntl.ioctl(slave_fd, termios.TIOCSCTTY, 0)

async def execute(username: str, *args) -> None:
    session = get_current_session()
    terminal = session.extra["terminal"]
    pty = terminal.pty
    env = session.extra["env"]

    await pty.ensure()
    slave_fd = pty.get_slave_fd()

    process_env = os.environ.copy()
    term = env.get("TERM")
    if term:
        process_env["TERM"] = term
    else:
        process_env.setdefault("TERM", "xterm-256color")

    await pty.attach_streams()

    proc = await asyncio.create_subprocess_exec(
        "bash",
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        env=process_env,
        pass_fds=(slave_fd,),
        preexec_fn=lambda: _setup_pty(slave_fd),
    )

    pty.set_owner_pid(proc.pid)

    await proc.wait()
    await pty.detach_streams()
    return None

command = {
    "name": "bash_manual",
    "help": "Start an interactive Bash shell (manual PTY setup)",
    "func": execute,
}
```

### 9.4. Команда для управления мышью (`mouse`)

```python
# commands/test/mouse.py
from sshserver.session.manager import get_current_session
from sshserver.terminal.mouse_handler import MouseEvent

async def on_mouse_event(event: MouseEvent):
    msg = f"\r\n[Mouse] {event.state} btn={event.button} at ({event.x},{event.y})"
    if event.wheel:
        msg += f" wheel={event.wheel}"
    session = get_current_session()
    if session and "terminal" in session.extra:
        terminal = session.extra["terminal"]
        await terminal.output.output_str(msg)

async def execute(username: str, *args) -> str:
    session = get_current_session()
    if not session or "terminal" not in session.extra:
        return "Error: Cannot access terminal"

    terminal = session.extra["terminal"]
    mouse = terminal.input.mouse

    if not args:
        return "Usage: mouse on [mode] | mouse off | mouse status"

    cmd = args[0].lower()

    if cmd == "on":
        mode = 0
        if len(args) > 1:
            try:
                mode = int(args[1])
                if mode not in (0, 2, 3):
                    return "Invalid mode. Use 0, 2, or 3."
            except ValueError:
                return "Mode must be a number (0, 2, 3)."

        base_mode = 1000 if mode == 0 else (1002 if mode == 2 else 1003)
        await mouse.enable([base_mode, 1006])
        mouse.add_listener(on_mouse_event)
        return f"Mouse tracking ENABLED (mode {mode}, base {base_mode})"

    elif cmd == "off":
        await mouse.disable()
        mouse.remove_listener(on_mouse_event)
        return "Mouse tracking DISABLED"

    elif cmd == "status":
        if mouse.active_modes:
            return f"Active mouse modes: {sorted(mouse.active_modes)}"
        else:
            return "Mouse tracking is OFF"
    else:
        return "Unknown command. Use on, off, or status."

command = {
    "name": "mouse",
    "help": "Enable or disable mouse tracking",
    "func": execute,
    "permissions": ["tester_permission"]
}
```

### 9.5. Команда с правами администратора (`sessions`)

```python
# commands/internal/sessions.py
from sshserver.session.manager import SessionStore
import time

def sessions(username: str, *args) -> str:
    store = SessionStore()
    active = store.list_all()
    if not active:
        return "No active sessions."

    lines = ["Active sessions:"]
    for s in active:
        uptime = int(time.time() - s.start_time)
        lines.append(f"  {s.uuid[:8]}... {s.username}@{s.client_addr} "
                     f"{s.term_type} {s.term_width}x{s.term_height} uptime: {uptime}s")
    return "\n".join(lines)

command = {
    "name": "sessions",
    "help": "List active SSH sessions",
    "func": sessions,
    "permissions": ["admin_permission"]
}
```

### 9.6. Категория с правами

```python
# commands/pve/__init__.py
command = {
    "type": "category",
    "name": "pve",
    "help": "Proxmox VE management commands",
    "permissions": ["poweruser_permission"]
}
```
