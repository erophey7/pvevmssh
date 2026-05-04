# Документация API команд PVE SSH Server

**Версия документации:** 0.5 (март 2026)
**Статус:** DEPRECATED

---

## Оглавление

* [1. Назначение](#1-назначение)
* [2. Структура директории `commands/`](#2-структура-директории-commands)
* [3. Типы команд](#3-типы-команд)

  * [3.1. Single-file команда](#31-single-file-команда)
  * [3.2. Command Module (команда-пакет)](#32-command-module-команда-пакет)
  * [3.3. Категория (Group)](#33-категория-group)
* [4. Система прав и наследование](#4-система-прав-и-наследование)

  * [4.1. Откуда команда получает права пользователя](#41-откуда-команда-получает-права-пользователя)
  * [4.2. Проверка прав внутри команды](#42-проверка-прав-внутри-команды)
* [5. Общие импорты и доступ к глобальным объектам](#5-общие-импорты-и-доступ-к-глобальным-объектам)

  * [5.1. `session.extra`](#51-sessionextra)
  * [5.2. `GlobalStore`](#52-globalstore)
* [6. Как писать команды](#6-как-писать-команды)

  * [6.1. Рекомендуемый шаблон](#61-рекомендуемый-шаблон)
  * [6.2. Синхронные и асинхронные команды](#62-синхронные-и-асинхронные-команды)
  * [6.3. Возвращаемое значение и перевод строки](#63-возвращаемое-значение-и-перевод-строки)
* [7. Разбор аргументов командной строки](#7-разбор-аргументов-командной-строки)

  * [7.1. Безопасный `argparse`](#71-безопасный-argparse)
  * [7.2. Подкоманды (`subparsers`)](#72-подкоманды-subparsers)
* [8. Работа с окружением (`UserEnvironment`)](#8-работа-с-окружением-userenvironment)

  * [8.1. Временные и постоянные переменные окружения](#81-временные-и-постоянные-переменные-окружения)
* [9. Работа с вводом и выводом (IO)](#9-работа-с-вводом-и-выводом-io)

  * [9.1. Возврат результата из команды](#91-возврат-результата-из-команды)
  * [9.2. Работа со строками и байтами](#92-работа-со-строками-и-байтами)
  * [9.3. Прямая работа с `Terminal`](#93-прямая-работа-с-terminal)
  * [9.4. Интерактивный ввод без PTY](#94-интерактивный-ввод-без-pty)
* [10. Поддержка мыши](#10-поддержка-мыши)

  * [10.1. Включение и отключение режимов](#101-включение-и-отключение-режимов)
  * [10.2. Обработка событий](#102-обработка-событий)
  * [10.3. Пример команды с мышью](#103-пример-команды-с-мышью)
* [11. Работа с PTY](#11-работа-с-pty)

  * [11.1. Базовые операции](#111-базовые-операции)
  * [11.2. Размер терминала](#112-размер-терминала)
  * [11.3. Запуск интерактивных программ (`spawn`)](#113-запуск-интерактивных-программ-spawn)
  * [11.4. Блокирующее поведение `attach_streams()`](#114-блокирующее-поведение-attach_streams)
  * [11.5. Корректное завершение PTY и очистка ресурсов](#115-корректное-завершение-pty-и-очистка-ресурсов)
  * [11.6. Полноэкранные команды и альтернативный экран](#116-полноэкранные-команды-и-альтернативный-экран)
* [12. Работа с базой данных](#12-работа-с-базой-данных)

  * [12.1. Получение объекта БД](#121-получение-объекта-бд)
  * [12.2. Основные методы](#122-основные-методы)
  * [12.3. Транзакции и обработка ошибок](#123-транзакции-и-обработка-ошибок)
  * [12.4. Работа с JSON-полями](#124-работа-с-json-полями)
  * [12.5. Структура таблицы `users`](#125-структура-таблицы-users)
  * [12.6. Поле `history`](#126-поле-history)
* [13. Логирование](#13-логирование)
* [14. Тестирование и отладка команд](#14-тестирование-и-отладка-команд)
* [15. Anti-patterns (как делать не стоит)](#15-anti-patterns-как-делать-не-стоит)
* [16. FAQ](#16-faq)
* [17. Production-grade пример команды](#17-production-grade-пример-команды)
* [18. Рекомендации и лучшие практики](#18-рекомендации-и-лучшие-практики)

---

# 1. Назначение

Этот документ описывает API и практики разработки **пользовательских команд** для PVE SSH Server.

Команды позволяют:

* выполнять действия от имени пользователя через SSH;
* управлять окружением и терминалом;
* запускать интерактивные процессы;
* работать с базой данных;
* реализовывать собственную бизнес-логику и контроль доступа.

Документация ориентирована на разработчиков, которые добавляют новые команды в директорию `commands/`.

---

# 2. Структура директории `commands/`

```plaintext
commands/
├── internal/                  # Группа (категория) команд
│   ├── __init__.py            # Метаданные категории
│   ├── about.py
│   ├── echo.py
│   ├── export.py
│   ├── sessions.py
│   └── whoami.py
├── pve/                       # Категория для Proxmox VE
│   ├── __init__.py
│   └── bash.py
├── test/                      # Тестовые команды
│   ├── __init__.py
│   ├── char.py
│   ├── color.py
│   └── mouse.py
└── __init__.py                # (опционально) корневая категория
```

## Правила

* Каждая папка = **категория** (group).
* Команда может быть:

  * **Single-file** (`*.py`)
  * **Command Module** (папка с `__init__.py` и `"type": "command"`)

---

# 3. Типы команд

## 3.1. Single-file команда

```python
# commands/internal/about.py
from sshserver.session.manager import get_current_session

async def execute(username: str, *args) -> str | None:
    session = get_current_session()
    return f"Hello, {username}! Your session UUID: {session.uuid}\n"

command = {
    "name": "about",
    "help": "Show information about server and session",
    "func": execute,
}
```

---

## 3.2. Command Module (команда-пакет)

```python
# commands/edit/__init__.py
async def execute(username: str, *args):
    ...

command = {
    "type": "command",
    "name": "edit",
    "help": "Edit configuration",
    "func": execute,
    "permissions": ["config_edit"]
}
```

Используйте такой формат, если команда:

* большая;
* имеет несколько вспомогательных файлов;
* работает с API, шаблонами или сложной логикой.

---

## 3.3. Категория (Group)

```python
# commands/internal/__init__.py
command = {
    "type": "category",
    "name": "internal",
    "help": "Internal server management commands",
    "permissions": []
}
```

> Если `__init__.py` в папке отсутствует или не содержит `command = {...}`, папка считается обычной категорией без дополнительных прав.

---

# 4. Система прав и наследование

Права наследуются **вниз** по дереву:

```text
commands/ → internal/ → edit/ → config.py
```

## Правила наследования

* Команда наследует все права родительских категорий.
* Если в команде указаны свои `permissions`, они **объединяются** с наследованными.
* Если итоговый список прав пустой — команда доступна **всем** пользователям.

## Пример

```python
# internal/__init__.py
"permissions": ["internal_access"]

# edit/__init__.py
"permissions": ["config_edit"]

# edit/config.py
"permissions": ["config_write"]
```

Итоговые права:

```python
["internal_access", "config_edit", "config_write"]
```

Проверка доступа к самой команде выполняется автоматически в `CommandDispatcher`.

---

## 4.1. Откуда команда получает права пользователя

После авторизации сервер загружает права пользователя и помещает их в текущую сессию.

```python
from sshserver.session.manager import get_current_session

session = get_current_session()
permissions = session.extra["permissions"]
```

### Что это такое

`session.extra["permissions"]` — это **уже вычисленный список разрешений**, доступных текущему пользователю.

Обычно права определяются:

* по `group_id` пользователя;
* по конфигурации ролей/групп;
* администратором сервера.

Команда не обязана знать внутренний механизм расчёта — ей достаточно использовать уже готовый список.

---

## 4.2. Проверка прав внутри команды

Иногда доступа к самой команде недостаточно.
Нужна дополнительная проверка внутри логики.

Типичные примеры:

* пользователь может редактировать **только свои** SSH-ключи;
* менять группу другим пользователям может только администратор;
* удаление требует отдельного разрешения.

### Пример

```python
from sshserver.session.manager import get_current_session

async def execute(username: str, *args):
    session = get_current_session()
    perms = set(session.extra["permissions"])

    target_user = args[0] if args else username

    if target_user != username and "users_manage" not in perms:
        return "Access denied: you can modify only your own account.\n"

    return f"Allowed for target: {target_user}\n"
```

### Рекомендуемый подход

* **Доступ к команде как сущности** → через `command["permissions"]`
* **Тонкая бизнес-логика** → через `session.extra["permissions"]`

---

# 5. Общие импорты и доступ к глобальным объектам

Ниже — рекомендуемый набор импортов для большинства команд.

```python
import json
import logging
import argparse

from sshserver.session.manager import get_current_session
from sshserver.terminal import Terminal
from helpers.globals import GlobalStore
```

---

## 5.1. `session.extra`

`session.extra` — это словарь служебных объектов и данных, доступных команде.

### Типичный набор

```python
{
    "terminal": Terminal,
    "env": UserEnvironment,
    "permissions": list[str],
    ...
}
```

### Доступ к основным объектам

#### Сессия

```python
session = get_current_session()
```

#### Терминал

```python
terminal: Terminal = session.extra["terminal"]
```

#### Окружение пользователя

```python
env = session.extra["env"]
```

#### Права пользователя

```python
permissions = session.extra["permissions"]
```

---

## 5.2. `GlobalStore`

`GlobalStore` — контейнер глобальных сервисов приложения.

### Получение контейнера

```python
store = GlobalStore.get()
```

### Обязательный сервис

```python
db = store.require("db")
```

### Опциональный сервис

```python
config = store.get("config")
```

### Что может быть доступно

В зависимости от инициализации сервера:

* `db` — база данных
* `config` — конфигурация
* `cache` — кэш
* другие сервисы, зарегистрированные приложением

> Гарантированно используйте только те сервисы, которые действительно инициализируются в вашем runtime.

---

# 6. Как писать команды

## 6.1. Рекомендуемый шаблон

```python
"""
Короткое описание команды.
"""

import logging
from sshserver.session.manager import get_current_session
from sshserver.terminal import Terminal

logger = logging.getLogger(__name__)


async def execute(username: str, *args) -> str | None:
    """
    username — имя пользователя
    *args    — аргументы после имени команды
    """
    session = get_current_session()
    terminal: Terminal = session.extra["terminal"]
    env = session.extra["env"]

    logger.info("Command mycommand executed by %s", username)

    env.set("CUSTOM_VAR", "value")

    return "Command executed successfully.\n"


command = {
    "name": "mycommand",
    "help": "One-line description for help",
    "func": execute,
}
```

---

## 6.2. Синхронные и асинхронные команды

Команда может быть реализована как:

* `async def execute(...)`
* `def execute(...)`

### Используйте `async def`, если команда:

* работает с БД;
* пишет в терминал через async API;
* читает пользовательский ввод;
* использует PTY;
* делает сетевые вызовы;
* работает с асинхронными сервисами.

### Используйте `def`, если команда:

* очень простая;
* не использует async API;
* просто возвращает текст.

### Рекомендация

Для новых команд **предпочтительно использовать `async def`**.

> Если синхронные команды внутри текущего диспетчера выполняются через отдельную обёртку или поток, это зависит от реализации. Не полагайтесь на это без проверки.

---

## 6.3. Возвращаемое значение и перевод строки

Команда может возвращать:

* `str`
* `bytes`
* `None`
* `list[str | bytes]`

### Важно

**Не полагайтесь на автоматическое добавление `\n`.**

Если вывод должен завершаться новой строкой — добавляйте её вручную.

### Хорошо

```python
return "Done.\n"
```

### Плохо

```python
return "Done."
```

Во втором случае следующий shell prompt или вывод другой команды может “прилипнуть” к тексту.

---

# 7. Разбор аргументов командной строки

Для команд с флагами и подкомандами рекомендуется использовать `argparse`, **но безопасно**.

---

## 7.1. Безопасный `argparse`

Стандартный `ArgumentParser` при ошибке вызывает `sys.exit()`, что нежелательно внутри команды.

### Рекомендуемый шаблон

```python
import argparse

class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)

    def exit(self, status=0, message=None):
        raise ValueError(message or "Argument parsing failed")


def build_parser():
    parser = SafeArgumentParser(prog="mycmd", add_help=True)
    parser.add_argument("--force", action="store_true", help="Force operation")
    parser.add_argument("target", nargs="?")
    return parser
```

### Использование

```python
async def execute(username: str, *args):
    parser = build_parser()

    try:
        ns, unknown = parser.parse_known_args(args)
    except ValueError as e:
        return f"Argument error: {e}\n"

    if unknown:
        return f"Unknown arguments: {' '.join(unknown)}\n"

    return f"Target={ns.target}, force={ns.force}\n"
```

### Почему `parse_known_args()` полезен

* не убивает процесс;
* позволяет вручную обработать лишние аргументы;
* удобен для SSH CLI-команд.

---

## 7.2. Подкоманды (`subparsers`)

Это рекомендуемый паттерн для команд вида:

* `sshkey add`
* `sshkey list`
* `sshkey delete`
* `user create`
* `user delete`
* `vm start`
* `vm stop`

### Пример

```python
import argparse

class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)

    def exit(self, status=0, message=None):
        raise ValueError(message or "Argument parsing failed")


def build_parser():
    parser = SafeArgumentParser(prog="sshkey")
    sub = parser.add_subparsers(dest="action", required=True)

    sub.add_parser("list", help="List SSH keys")

    p_add = sub.add_parser("add", help="Add SSH key")
    p_add.add_argument("key", help="Public SSH key")

    p_delete = sub.add_parser("delete", help="Delete SSH key by index")
    p_delete.add_argument("index", type=int)

    return parser
```

### Использование

```python
async def execute(username: str, *args):
    parser = build_parser()

    try:
        ns, unknown = parser.parse_known_args(args)
    except ValueError as e:
        return f"Argument error: {e}\n"

    if unknown:
        return f"Unknown arguments: {' '.join(unknown)}\n"

    if ns.action == "list":
        return "Listing keys...\n"

    if ns.action == "add":
        return f"Adding key: {ns.key[:32]}...\n"

    if ns.action == "delete":
        return f"Deleting key #{ns.index}\n"

    return "Unknown action.\n"
```

---

# 8. Работа с окружением (`UserEnvironment`)

Доступ:

```python
session = get_current_session()
env = session.extra["env"]
```

## Базовые операции

```python
env.set("PS1", "pve> ")
env.set("EDITOR", "nano")

value = env.get("USER")
env.unset("TEMP_VAR")

text = env.substitute("Hello $USER, your TERM is $TERM")
```

## Полезные методы

* `env.export("VAR=value")`
* `env.substitute(text)`
* `env.as_dict()`

---

## 8.1. Временные и постоянные переменные окружения

Важно понимать:

* изменения через `env.set(...)` живут **только в текущей SSH-сессии**;
* они **не сохраняются автоматически** в БД.

### Временное изменение

```python
env.set("EDITOR", "vim")
```

### Если нужно сохранить навсегда

Нужно обновить поле `saved_env` в таблице `users`.

### Пример

```python
import json
from helpers.globals import GlobalStore
from sshserver.session.manager import get_current_session

async def execute(username: str, *args):
    session = get_current_session()
    env = session.extra["env"]
    db = GlobalStore.get().require("db")

    env.set("EDITOR", "vim")

    async with db.transaction():
        await db.execute(
            "UPDATE users SET saved_env = ? WHERE username = ?",
            (json.dumps(env.as_dict(), ensure_ascii=False), username)
        )

    return "EDITOR saved permanently.\n"
```

---

# 9. Работа с вводом и выводом (IO)

Вся работа с терминалом пользователя происходит через объект `Terminal`.

```python
from sshserver.session.manager import get_current_session

async def execute(username: str, *args):
    session = get_current_session()
    terminal = session.extra["terminal"]
```

---

## 9.1. Возврат результата из команды

Функция `execute` может возвращать:

* `str`
* `bytes`
* `None`
* `list[str | bytes]`

### Пример

```python
async def execute(username: str, *args) -> str | bytes | None:
    if not args:
        return "Usage: mycmd <argument>\n"

    return f"Received: {' '.join(args)}\n"
```

---

## 9.2. Работа со строками и байтами

### Рекомендации

* Для обычного текста используйте `str`
* Для ANSI/escape-последовательностей допустимы и `str`, и `bytes`
* Для сложного вывода — используйте прямую запись в терминал

### Примеры

```python
return "\x1b[31mКрасный текст\x1b[0m\n"
```

```python
await terminal.output.write("Привет, мир!\n")
await terminal.output.write(b"\x1b[2J\x1b[H")
await terminal.output.writelines(["Строка 1\n", "Строка 2\n"])
```

---

## 9.3. Прямая работа с `Terminal`

### Основные компоненты

* `terminal.input` — чтение ввода
* `terminal.output` — запись вывода
* `terminal.pty` — работа с псевдотерминалом
* `terminal.rows` / `terminal.cols` — текущий размер терминала

### Чтение ввода

```python
line = await terminal.input.read_str()
data = await terminal.input.read_bytes(max_bytes=1024, timeout=10.0)
```

### Вывод

* `write(data: str | bytes)`
* `writelines(lines: list[str | bytes])`
* `flush()`

---

## 9.4. Интерактивный ввод без PTY

Для простых подтверждений не нужен полноценный PTY.

### Пример: подтверждение удаления

```python
from sshserver.session.manager import get_current_session

async def execute(username: str, *args):
    session = get_current_session()
    terminal = session.extra["terminal"]

    await terminal.output.write("Delete resource? [y/N]: ")
    answer = (await terminal.input.read_str()).strip().lower()

    if answer not in ("y", "yes"):
        return "Cancelled.\n"

    return "Resource deleted.\n"
```

### Пример: чтение сырых байтов

```python
await terminal.output.write("Press any key...\n")
data = await terminal.input.read_bytes(max_bytes=1, timeout=10.0)

if not data:
    return "Timeout.\n"

return f"Received byte: {data!r}\n"
```

---

# 10. Поддержка мыши

## 10.1. Включение и отключение режимов

```python
mouse = terminal.input.mouse

await mouse.enable(1000)
await mouse.enable([1002, 1006])
await mouse.disable()
await mouse.disable(1006)
```

### Рекомендуемые режимы

* `1000` — базовые клики
* `1002` — drag / motion
* `1006` — SGR-формат (рекомендуется)

---

## 10.2. Обработка событий

```python
from sshserver.terminal.mouse_handler import MouseEvent

async def on_mouse_event(event: MouseEvent):
    if event.wheel:
        print(f"Wheel: {'up' if event.wheel > 0 else 'down'}")
    else:
        print(f"Button {event.button} {event.state} at ({event.x}, {event.y})")

mouse.add_listener(on_mouse_event)
```

### Свойства `MouseEvent`

* `button`
* `x`, `y`
* `state`
* `wheel`
* `modifiers`

---

## 10.3. Пример команды с мышью

```python
from sshserver.session.manager import get_current_session

async def execute(username: str, *args):
    session = get_current_session()
    terminal = session.extra["terminal"]
    mouse = terminal.input.mouse

    async def on_mouse_event(event):
        await terminal.output.write(
            f"\rMouse: button={event.button} state={event.state} x={event.x} y={event.y}   \n"
        )

    await mouse.enable([1000, 1006])
    mouse.add_listener(on_mouse_event)

    try:
        await terminal.output.write("Mouse test enabled. Press Enter to exit.\n")
        await terminal.input.read_str()
    finally:
        await mouse.disable()

    return "Mouse test finished.\n"
```

> Если команда включает мышь, **всегда отключайте её в `finally`**.

---

# 11. Работа с PTY

`terminal.pty` используется для интерактивных приложений: shell, `vim`, `htop`, консоль ВМ и т.д.

---

## 11.1. Базовые операции

```python
pty = terminal.pty

await pty.ensure()
slave_fd = pty.get_slave_fd()

await pty.resize(rows=24, cols=80)

await pty.attach_streams()
await pty.detach_streams()
```

---

## 11.2. Размер терминала

Объект `Terminal` предоставляет:

```python
terminal.rows
terminal.cols
```

Эти значения отражают текущий размер SSH-окна пользователя и обновляются при resize.

### Рекомендуемый паттерн

```python
await pty.resize(terminal.rows, terminal.cols)
```

---

## 11.3. Запуск интерактивных программ (`spawn`)

### Пример

```python
process = await pty.spawn(
    cmd="/bin/bash",
    args=["--login"],
    env=session.extra["env"].as_dict(),
    cwd="/root"
)
```

`spawn(...)` обычно:

* создаёт PTY;
* назначает управляющий терминал;
* запускает процесс;
* подготавливает окружение.

---

## 11.4. Блокирующее поведение `attach_streams()`

```python
await pty.attach_streams()
```

### Важно

Этот вызов **блокирует выполнение команды** до завершения процесса или разрыва bridge.

То есть:

```python
await pty.attach_streams()
return "Done.\n"
```

вернёт строку **только после выхода пользователя** из shell / `vim` / консоли ВМ.

---

## 11.5. Корректное завершение PTY и очистка ресурсов

Используйте `try/finally`.

### Пример

```python
from sshserver.session.manager import get_current_session

async def execute(username: str, *args):
    session = get_current_session()
    terminal = session.extra["terminal"]
    pty = terminal.pty

    await pty.ensure()
    await pty.resize(terminal.rows, terminal.cols)

    try:
        await pty.spawn("/bin/bash", ["-i"], env=session.extra["env"].as_dict())
        await pty.attach_streams()
    finally:
        try:
            await pty.detach_streams()
        except Exception:
            pass

    return "PTY session finished.\n"
```

### Нужно ли всегда вызывать `detach_streams()`?

Зависит от реализации `PTYHandler`.

Безопасный практический подход:

* если вы **вручную включили bridge**, постарайтесь **вручную его и завершить**;
* cleanup через `finally` — предпочтителен.

---

## 11.6. Полноэкранные команды и альтернативный экран

Для TUI и полноэкранных режимов удобно использовать альтернативный экран:

* `\x1b[?1049h` — включить
* `\x1b[?1049l` — выключить

### Пример

```python
from sshserver.session.manager import get_current_session

async def execute(username: str, *args):
    session = get_current_session()
    terminal = session.extra["terminal"]

    try:
        await terminal.output.write(b"\x1b[?1049h")
        await terminal.output.write(b"\x1b[2J\x1b[H")
        await terminal.output.write("Interactive tool started.\n")
        await terminal.output.write("Press Enter to exit.\n")

        await terminal.input.read_str()
    finally:
        await terminal.output.write(b"\x1b[?1049l")

    return None
```

---

# 12. Работа с базой данных

База данных доступна глобально через `GlobalStore`.

---

## 12.1. Получение объекта БД

```python
from helpers.globals import GlobalStore

async def execute(username: str, *args):
    db = GlobalStore.get().require("db")
```

---

## 12.2. Основные методы

Все методы асинхронные:

* `fetch_one(query, params=None)`
* `fetch_all(query, params=None)`
* `fetch_val(query, params=None)`
* `execute(query, params=None)`
* `commit()`
* `rollback()`
* `transaction()`

### Рекомендация

Используйте плейсхолдеры `?`.

---

## 12.3. Транзакции и обработка ошибок

Если выполняется несколько связанных изменений — используйте транзакцию.

### Пример

```python
import logging
from helpers.globals import GlobalStore

logger = logging.getLogger(__name__)

async def execute(username: str, *args):
    db = GlobalStore.get().require("db")

    try:
        async with db.transaction():
            await db.execute(
                "UPDATE users SET group_id = ? WHERE username = ?",
                (2, username)
            )
            await db.execute(
                "UPDATE users SET api_key = ? WHERE username = ?",
                ("new-api-key", username)
            )
    except Exception as e:
        logger.exception("Failed to update user %s", username)
        return f"Database error: {e}\n"

    return "User updated successfully.\n"
```

### Что делает `transaction()`

* при успехе → `commit`
* при ошибке → `rollback`

---

## 12.4. Работа с JSON-полями

Некоторые поля в таблице `users` хранят JSON внутри `TEXT`:

* `ssh_keys`
* `saved_env`
* `history`

Используйте:

* `json.loads(...)`
* `json.dumps(...)`

---

### Пример: чтение `ssh_keys`

```python
import json
from helpers.globals import GlobalStore

async def execute(username: str, *args):
    db = GlobalStore.get().require("db")

    raw = await db.fetch_val(
        "SELECT ssh_keys FROM users WHERE username = ?",
        (username,)
    )

    ssh_keys = json.loads(raw or "[]")

    return f"SSH keys count: {len(ssh_keys)}\n"
```

---

### Пример: запись `ssh_keys`

```python
import json
from helpers.globals import GlobalStore

async def execute(username: str, *args):
    db = GlobalStore.get().require("db")

    raw = await db.fetch_val(
        "SELECT ssh_keys FROM users WHERE username = ?",
        (username,)
    )

    ssh_keys = json.loads(raw or "[]")
    ssh_keys.append("ssh-ed25519 AAAAC3Nza... user@host")

    async with db.transaction():
        await db.execute(
            "UPDATE users SET ssh_keys = ? WHERE username = ?",
            (json.dumps(ssh_keys, ensure_ascii=False), username)
        )

    return "SSH key added.\n"
```

### Рекомендация

```python
json.dumps(data, ensure_ascii=False)
```

---

## 12.5. Структура таблицы `users`

```sql
CREATE TABLE users (
    username    TEXT PRIMARY KEY,
    api_key     TEXT,
    api_secret  TEXT,
    ssh_keys    TEXT DEFAULT '[]',
    group_id    INTEGER DEFAULT 0,
    saved_env   TEXT DEFAULT '{}',
    history     TEXT DEFAULT '[]',
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
)
```

### Назначение полей

* `username` — имя пользователя
* `api_key` / `api_secret` — API-учётные данные
* `ssh_keys` — JSON-массив публичных SSH-ключей
* `group_id` — группа / роль пользователя
* `saved_env` — JSON-объект постоянных переменных окружения
* `history` — JSON-массив истории команд
* `created_at` — дата создания

---

## 12.6. Поле `history`

Поле `history` хранит историю команд пользователя.

### Пример значения

```json
[
  "whoami",
  "pve bash 101",
  "sshkey list"
]
```

### Пример чтения

```python
import json
from helpers.globals import GlobalStore

async def execute(username: str, *args):
    db = GlobalStore.get().require("db")

    raw = await db.fetch_val(
        "SELECT history FROM users WHERE username = ?",
        (username,)
    )

    history = json.loads(raw or "[]")
    return "\n".join(history[-20:]) + "\n"
```

### Пример обновления

```python
import json
from helpers.globals import GlobalStore

async def append_history(username: str, command_line: str):
    db = GlobalStore.get().require("db")

    raw = await db.fetch_val(
        "SELECT history FROM users WHERE username = ?",
        (username,)
    )

    history = json.loads(raw or "[]")
    history.append(command_line)

    history = history[-100:]

    async with db.transaction():
        await db.execute(
            "UPDATE users SET history = ? WHERE username = ?",
            (json.dumps(history, ensure_ascii=False), username)
        )
```

> Рекомендуется ограничивать длину истории.

---

# 13. Логирование

Используйте стандартный модуль `logging`.

### Шаблон

```python
import logging

logger = logging.getLogger(__name__)
```

### Примеры

```python
logger.info("User %s executed command %s", username, "mycommand")
logger.warning("User %s tried forbidden action", username)
logger.exception("Unexpected error in command")
```

### Что логировать

* запуск команды;
* изменение состояния;
* ошибки БД;
* ошибки PTY;
* подозрительные действия.

### Что не логировать

* приватные SSH-ключи;
* API secrets;
* токены;
* пароли.

---

# 14. Тестирование и отладка команд

## Базовый цикл

1. Запустить сервер
2. Подключиться по SSH
3. Выполнить команду
4. Проверить вывод
5. Проверить логи
6. Повторить

## Что проверять

### Простые команды

* корректный вывод;
* наличие `\n`;
* обработка пустых аргументов.

### Команды с правами

* доступ разрешён / запрещён;
* сценарии “для себя / для других”.

### Команды с БД

* корректность транзакций;
* rollback при ошибке;
* JSON-поля;
* пустые значения.

### PTY / интерактивные команды

* resize окна;
* возврат управления shell;
* cleanup после выхода.

### Мышь / альтернативный экран

* мышь отключается;
* экран восстанавливается;
* shell не остаётся в “грязном” состоянии.

### Полезный отладочный код

```python
logger.debug("Args: %r", args)
logger.debug("Permissions: %r", session.extra["permissions"])
logger.debug("Env: %r", session.extra["env"].as_dict())
```

---

# 15. Anti-patterns (как делать не стоит)

## 15.1. Не использовать `sys.exit()` или “сырой” `argparse`

### Плохо

```python
parser = argparse.ArgumentParser()
args = parser.parse_args(...)
```

Это может аварийно завершить команду.

### Хорошо

Использовать `SafeArgumentParser`.

---

## 15.2. Не забывать `\n`

### Плохо

```python
return "Done."
```

### Хорошо

```python
return "Done.\n"
```

---

## 15.3. Не писать JSON вручную строками

### Плохо

```python
await db.execute("UPDATE users SET ssh_keys = '[\"key1\"]' WHERE username = ?", (username,))
```

### Хорошо

```python
await db.execute(
    "UPDATE users SET ssh_keys = ? WHERE username = ?",
    (json.dumps(ssh_keys, ensure_ascii=False), username)
)
```

---

## 15.4. Не забывать cleanup режимов терминала

Если команда включает:

* мышь;
* alt screen;
* PTY bridge;

то она должна корректно их выключать.

### Хорошо

```python
try:
    ...
finally:
    ...
```

---

## 15.5. Не хранить секреты в логах

### Плохо

```python
logger.info("User key: %s", ssh_key)
logger.info("API secret: %s", api_secret)
```

---

# 16. FAQ

## Почему команда “ничего не выводит”?

Проверь:

* возвращает ли `execute(...)` значение;
* есть ли `\n` в конце строки;
* не проглатывается ли ошибка в `try/except`.

---

## Почему `argparse` “роняет” команду?

Потому что обычный `ArgumentParser` вызывает `sys.exit()`.

Используй `SafeArgumentParser`.

---

## Почему после команды shell выглядит “сломанным”?

Обычно причина:

* не выключен `alt screen`;
* не отключена мышь;
* не завершён PTY bridge;
* отправлены escape-последовательности без cleanup.

---

## Где брать права пользователя?

```python
session.extra["permissions"]
```

---

## Где брать терминал?

```python
session.extra["terminal"]
```

---

## Где брать окружение пользователя?

```python
session.extra["env"]
```

---

## Как сохранить переменные окружения навсегда?

Нужно обновить поле `saved_env` в БД.
Изменение через `env.set(...)` само по себе **не сохраняется между сессиями**.

---

# 17. Production-grade пример команды

Ниже — пример команды, которая объединяет:

* `argparse`
* проверку прав
* интерактивное подтверждение
* работу с БД
* JSON
* логирование

## Пример: удаление SSH-ключа

```python
"""
Delete SSH key from user account.
"""

import json
import logging
import argparse

from helpers.globals import GlobalStore
from sshserver.session.manager import get_current_session

logger = logging.getLogger(__name__)


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)

    def exit(self, status=0, message=None):
        raise ValueError(message or "Argument parsing failed")


def build_parser():
    parser = SafeArgumentParser(prog="sshkey-rm")
    parser.add_argument("index", type=int, help="Index of SSH key to remove")
    parser.add_argument("--user", help="Target username (admin only)")
    parser.add_argument("--yes", action="store_true", help="Skip confirmation")
    return parser


async def execute(username: str, *args):
    session = get_current_session()
    terminal = session.extra["terminal"]
    permissions = set(session.extra["permissions"])

    parser = build_parser()

    try:
        ns, unknown = parser.parse_known_args(args)
    except ValueError as e:
        return f"Argument error: {e}\n"

    if unknown:
        return f"Unknown arguments: {' '.join(unknown)}\n"

    target_user = ns.user or username

    if target_user != username and "users_manage" not in permissions:
        return "Access denied: you can modify only your own SSH keys.\n"

    db = GlobalStore.get().require("db")

    raw = await db.fetch_val(
        "SELECT ssh_keys FROM users WHERE username = ?",
        (target_user,)
    )

    ssh_keys = json.loads(raw or "[]")

    if ns.index < 0 or ns.index >= len(ssh_keys):
        return f"Invalid key index: {ns.index}\n"

    key_preview = ssh_keys[ns.index][:60]

    if not ns.yes:
        await terminal.output.write(
            f"Delete SSH key #{ns.index} for user '{target_user}'?\n"
        )
        await terminal.output.write(f"{key_preview}...\n")
        await terminal.output.write("Confirm [y/N]: ")

        answer = (await terminal.input.read_str()).strip().lower()
        if answer not in ("y", "yes"):
            return "Cancelled.\n"

    removed = ssh_keys.pop(ns.index)

    try:
        async with db.transaction():
            await db.execute(
                "UPDATE users SET ssh_keys = ? WHERE username = ?",
                (json.dumps(ssh_keys, ensure_ascii=False), target_user)
            )
    except Exception as e:
        logger.exception("Failed to remove SSH key for %s", target_user)
        return f"Database error: {e}\n"

    logger.info(
        "User %s removed SSH key #%d from %s",
        username, ns.index, target_user
    )

    return (
        f"SSH key #{ns.index} removed from user '{target_user}'.\n"
        f"Removed key preview: {removed[:60]}...\n"
    )


command = {
    "name": "sshkey-rm",
    "help": "Remove SSH key by index",
    "func": execute,
    "permissions": ["sshkey_manage"]
}
```

---

# 18. Рекомендации и лучшие практики

1. Для простых команд возвращайте `str`.
2. Всегда добавляйте `\n`, если ожидается отдельная строка вывода.
3. Для сложного CLI используйте безопасный `argparse`.
4. Для команд с несколькими действиями используйте `subparsers`.
5. Для БД почти всегда используйте `async def`.
6. JSON-поля всегда обрабатывайте через `json.loads()` / `json.dumps()`.
7. Для связанных изменений используйте `async with db.transaction():`.
8. Права команды задавайте в `command["permissions"]`.
9. Тонкую проверку прав выполняйте через `session.extra["permissions"]`.
10. Интерактивные подтверждения можно делать без PTY.
11. PTY-команды всегда синхронизируйте с `terminal.rows` / `terminal.cols`.
12. После временных режимов терминала всегда делайте cleanup в `finally`.
13. Логируйте действия и ошибки, но не секреты.
14. Если команда меняет окружение навсегда — обновляйте `saved_env`.
15. Если команда работает с историей — ограничивайте размер `history`.

---