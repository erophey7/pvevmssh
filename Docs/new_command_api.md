# Документация API команд PVE SSH Server

**Версия документации:** 2.0 (март 2026)  
**Статус:** Актуально для ветки `dev`  
**Архитектурный статус:** команды должны использовать `CommandAPI`

---

## Оглавление

* [1. Общая идея](#1-общая-идея)
* [2. Структура команд](#2-структура-команд)
  * [2.1. Single-file команда](#21-single-file-команда)
  * [2.2. Command Module (команда-пакет)](#22-command-module-команда-пакет)
  * [2.3. Категория (Group)](#23-категория-group)
* [3. Новый стиль команд: `CommandAPI`](#3-новый-стиль-команд-commandapi)
* [4. Общие импорты](#4-общие-импорты)
* [5. Объект `CommandAPI`](#5-объект-commandapi)
  * [5.1. Что содержит `api`](#51-что-содержит-api)
  * [5.2. Доступ к сессии и служебным данным](#52-доступ-к-сессии-и-служебным-данным)
* [6. Система прав доступа](#6-система-прав-доступа)
  * [6.1. Наследование прав](#61-наследование-прав)
  * [6.2. Права пользователя внутри команды](#62-права-пользователя-внутри-команды)
  * [6.3. Изменение других пользователей и ручные проверки](#63-изменение-других-пользователей-и-ручные-проверки)
* [7. Работа с аргументами](#7-работа-с-аргументами)
  * [7.1. Встроенный парсер `api.parser()`](#71-встроенный-парсер-apiparser)
  * [7.2. Ручной парсинг (альтернатива)](#72-ручной-парсинг-альтернатива)
* [8. Работа с вводом и выводом (IO)](#8-работа-с-вводом-и-выводом-io)
  * [8.1. Возврат значения из команды](#81-возврат-значения-из-команды)
  * [8.2. Методы вывода `CommandAPI`](#82-методы-вывода-commandapi)
  * [8.3. Прямой доступ к `Terminal`](#83-прямой-доступ-к-terminal)
* [9. Интерактивный ввод](#9-интерактивный-ввод)
* [10. Работа с окружением (`UserEnvironment`)](#10-работа-с-окружением-userenvironment)
  * [10.1. Временные переменные сессии](#101-временные-переменные-сессии)
  * [10.2. Постоянное сохранение в БД (`saved_env`)](#102-постоянное-сохранение-в-бд-saved_env)
* [11. Работа с PTY и интерактивными процессами](#11-работа-с-pty-и-интерактивными-процессами)
  * [11.1. Быстрый способ: `api.run_interactive()`](#111-быстрый-способ-apirun_interactive)
  * [11.2. Низкоуровневая работа через `api.pty`](#112-низкоуровневая-работа-через-apipty)
  * [11.3. Важно: `attach_streams()` блокирует выполнение](#113-важно-attach_streams-блокирует-выполнение)
  * [11.4. Завершение PTY и cleanup](#114-завершение-pty-и-cleanup)
  * [11.5. Полноэкранные команды и альтернативный экран](#115-полноэкранные-команды-и-альтернативный-экран)
* [12. Работа с мышью](#12-работа-с-мышью)
* [13. Альтернативный экран](#13-альтернативный-экран)
* [14. Работа с базой данных](#14-работа-с-базой-данных)
  * [14.1. Доступ к БД](#141-доступ-к-бд)
  * [14.2. Shortcut-методы через `api`](#142-shortcut-методы-через-api)
  * [14.3. Что возвращают `fetch_one()` и `fetch_all()`](#143-что-возвращают-fetch_one-и-fetch_all)
  * [14.4. Практические примеры SQL](#144-практические-примеры-sql)
  * [14.5. Транзакции и обработка ошибок](#145-транзакции-и-обработка-ошибок)
* [15. Работа с JSON-полями в таблице `users`](#15-работа-с-json-полями-в-таблице-users)
  * [15.1. `ssh_keys`](#151-ssh_keys)
  * [15.2. `saved_env`](#152-saved_env)
  * [15.3. `history`](#153-history)
* [16. `api.user` и `UserContext`](#16-apiuser-и-usercontext)
* [17. Криптография](#17-криптография)
* [18. Глобальные сервисы и `GlobalStore`](#18-глобальные-сервисы-и-globalstore)
* [19. Исключения команд](#19-исключения-команд)
* [20. Логирование](#20-логирование)
* [21. Размеры терминала](#21-размеры-терминала)
* [22. Тестирование и локальная отладка](#22-тестирование-и-локальная-отладка)
* [23. Лучшие практики](#23-лучшие-практики)
* [24. Полные примеры команд](#24-полные-примеры-команд)
  * [24.1. Простая команда](#241-простая-команда)
  * [24.2. Команда с парсером](#242-команда-с-парсером)
  * [24.3. Команда с правами и БД](#243-команда-с-правами-и-бд)
  * [24.4. Интерактивная команда подтверждения](#244-интерактивная-команда-подтверждения)
  * [24.5. Интерактивный shell](#245-интерактивный-shell)

---

# 1. Общая идея

Начиная с текущей версии ветки `dev`, команды должны использовать **единый стабильный слой** — `CommandAPI`. Его задача: **скрыть внутреннюю архитектуру SSH-сервера** и дать команде один объект с доступом к:

* текущему пользователю,
* аргументам,
* терминалу,
* окружению,
* правам,
* БД,
* PTY,
* логгеру,
* парсеру аргументов,
* интерактивному вводу/выводу.

Это означает, что **новые команды не должны напрямую полагаться** на:

* `get_current_session()`
* `session.extra["terminal"]`
* `session.extra["permissions"]`
* `GlobalStore.get().require("db")`

Вместо этого команда должна работать через `api`. Реализация `CommandAPI` уже предоставляет эти возможности централизованно.

---

# 2. Структура команд

## 2.1. Single-file команда

```python
# commands/internal/about.py
from sshserver.commandapi import CommandAPI

async def execute(api: CommandAPI) -> str | None:
    return f"Hello, {api.username}!"

command = {
    "name": "about",
    "help": "Show information about current session",
    "func": execute,
}
```

---

## 2.2. Command Module (команда-пакет)

```python
# commands/edit/__init__.py
from sshserver.commandapi import CommandAPI

async def execute(api: CommandAPI):
    return "Edit command"

command = {
    "type": "command",
    "name": "edit",
    "help": "Edit configuration",
    "func": execute,
    "permissions": ["config_edit"]
}
```

---

## 2.3. Категория (Group)

```python
# commands/internal/__init__.py
command = {
    "type": "category",
    "name": "internal",
    "help": "Internal server management commands",
    "permissions": []
}
```

> Если `__init__.py` отсутствует или не содержит `command = {...}`, папка считается обычной категорией без дополнительных метаданных.

---

# 3. Новый стиль команд: `CommandAPI`

Новый рекомендуемый формат команды:

```python
from sshserver.commandapi import CommandAPI

async def execute(api: CommandAPI) -> str | None:
    return f"Hello, {api.username}!"
```

Это **новый рекомендуемый стандарт**.  
Команда получает **один объект** `api`, а не `username` и не набор разрозненных helper’ов.

---

# 4. Общие импорты

В большинстве команд тебе достаточно вот этого:

```python
from sshserver.commandapi import CommandAPI
```

Если нужны пользовательские ошибки:

```python
from sshserver.commandapi import (
    CommandAPI,
    CommandError,
    CommandPermissionError,
    CommandArgumentError,
    CommandAbort,
    CommandNotFoundError,
    CommandRuntimeError,
)
```

Все эти классы экспортируются через `sshserver.commandapi.__init__`.

---

# 5. Объект `CommandAPI`

## 5.1. Что содержит `api`

При создании `CommandAPI(username, args)` объект инициализирует и кэширует доступ к ключевым сервисам сессии и среды выполнения.

Доступные поля и свойства:

```python
api.username        # имя текущего пользователя
api.args            # tuple[str, ...] аргументов команды
api.session         # текущая SSH-сессия
api.terminal        # Terminal
api.env             # UserEnvironment
api.history         # History
api.permissions     # set[str]
api.logger          # logging.Logger

api.db              # Database (lazy)
api.pty             # PTYHandler
api.mouse           # mouse handler
api.rows            # высота терминала
api.cols            # ширина терминала
api.pixheight       # высота терминала (в пикселях)
api.pixwidth        # ширина терминала (в пикселях)
api.user            # UserContext (lazy)
api.config          # объект конфигурации (lazy)
```

---

## 5.2. Доступ к сессии и служебным данным

`CommandAPI` сам использует текущую SSH-сессию и вытаскивает оттуда нужные объекты, включая `terminal`, `env` и `permissions`.

Эквивалентно старому стилю:

```python
session = get_current_session()
terminal = session.extra["terminal"]
env = session.extra["env"]
permissions = session.extra.get("permissions", [])
```

Теперь всё это уже доступно через:

```python
api.terminal
api.env
api.permissions
```

### Что находится в `session.extra`

На текущий момент для команд особенно важны следующие ключи:

* `session.extra["terminal"]` → объект `Terminal`
* `session.extra["env"]` → объект `UserEnvironment`
* `session.extra["permissions"]` → список прав пользователя

Именно из этих данных `CommandAPI` собирает свой runtime-контекст.

---

# 6. Система прав доступа

## 6.1. Наследование прав

Система наследования прав **не изменилась**:

* права могут задаваться у категорий;
* команда наследует права родительских уровней;
* свои `permissions` у команды объединяются с унаследованными;
* если итоговый набор прав пуст — команда доступна всем.

Пример:

```python
# commands/internal/__init__.py
command = {
    "type": "category",
    "name": "internal",
    "permissions": ["internal_access"]
}
```

```python
# commands/internal/edit.py
command = {
    "name": "edit",
    "permissions": ["config_edit"]
}
```

Итог: для выполнения команды нужен любой из контекстов — логика диспетчера и проверка прав на уровне команды/категории.

---

## 6.2. Права пользователя внутри команды

В новой API права доступны напрямую:

```python
api.permissions
```

Это `set[str]`.

### Проверка права

```python
if not api.has_permission("db_viewer"):
    return "Permission denied.\n"
```

### Проверка нескольких прав

```python
if api.has_any_permission("user_manage", "admin_tools"):
    ...
```

### Рекомендуемый способ

```python
api.require_permission("db_viewer")
```

Если права нет — будет выброшено `CommandPermissionError`.

---

## 6.3. Изменение других пользователей и ручные проверки

Есть команды, где автоматической проверки прав на входе недостаточно, например:

* `chgroup`
* `sshkey add <user>`
* `userinfo <user>`
* `usermod`

В таких сценариях рекомендуется делать **ручную бизнес-проверку** внутри команды:

```python
api.require_permission("user_manage")

target_username = "alice"

if target_username != api.username and not api.has_permission("admin"):
    return "You can modify only your own account.\n"
```

То есть:

* **доступ к самой команде** может быть защищён через `command["permissions"]`,
* **доступ к конкретному действию** проверяется уже внутри логики команды.

---

# 7. Работа с аргументами

## 7.1. Встроенный парсер `api.parser()`

`CommandAPI` предоставляет встроенный argparse-подобный парсер аргументов:

```python
parser = api.parser()
# или
parser = api.parser("userinfo")
# или
parser = api.parser("userinfo", description="Информация о пользователе")
```

Метод `api.parser()` возвращает экземпляр `ArgumentParser`, который предназначен для разбора аргументов команды в стиле Python `argparse`.

---

### 7.1.1. Что поддерживает парсер

Встроенный `ArgumentParser` поддерживает:

* **Позиционные аргументы**
* **Флаги** (`store_true`)
* **Опции со значением**
* **Короткие и длинные формы** (`-v`, `--verbose`)
* **Группировку коротких флагов** (`-abc`)
* **Короткие опции со значением** (`-n5`)
* **Длинные опции со значением через `=`** (`--count=5`)
* **Подкоманды**
* **Автоматический `-h/--help`**
* **Типизацию значений** (`type=int`)
* **Проверку допустимых значений** (`choices=[...]`)
* **Обязательные аргументы** (`required=True`)
* **Множественные значения** через `nargs`

---

### 7.1.2. Базовый синтаксис

Аргументы добавляются через единый метод `add_argument(...)`.

#### Позиционный аргумент

```python
parser.add_argument("file", help="Имя файла")
```

#### Флаг без значения

```python
parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
```

#### Опция со значением

```python
parser.add_argument("-c", "--count", type=int, default=5, help="Количество записей")
```

#### Разбор аргументов

```python
ns = parser.parse_args(api.args)
```

После этого значения доступны через `Namespace`:

```python
ns.file
ns.verbose
ns.count
```

---

### 7.1.3. Простой пример

```python
async def execute(api: CommandAPI) -> str | None:
    parser = api.parser("example", description="Пример команды")
    parser.add_argument("file", help="Имя файла")
    parser.add_argument("-v", "--verbose", action="store_true", help="Подробный вывод")
    parser.add_argument("-c", "--count", type=int, default=5, help="Количество записей")

    try:
        ns = parser.parse_args(api.args)
    except CommandArgumentError as e:
        return f"Ошибка: {e}\n"

    if ns.verbose:
        await api.writeln(f"Парсер сработал: {ns}")

    return f"File={ns.file}, count={ns.count}\n"
```

#### Примеры запуска

```bash
example report.txt
example report.txt -v
example report.txt --count 10
example report.txt -v -c 3
```

---

### 7.1.4. Флаги

Флаги — это аргументы без значения, которые просто включают поведение.

```python
parser.add_argument("-a", "--all", action="store_true", help="Показать все поля")
```

#### Пример

```bash
userinfo --all
userinfo -a
```

Если флаг передан, значение будет `True`, иначе — `False`.

```python
if ns.all:
    ...
```

---

### 7.1.5. Опции со значением

Опции используются, когда аргумент должен принимать значение.

```python
parser.add_argument("--user", help="Целевой пользователь")
parser.add_argument("-n", "--count", type=int, default=10)
```

#### Примеры

```bash
userinfo --user alice
userinfo -n 5
userinfo -n5
userinfo --count=5
```

---

### 7.1.6. Позиционные аргументы

Позиционные аргументы задаются без `-` и `--`.

```python
parser.add_argument("target", help="Целевой объект")
parser.add_argument("action", help="Действие")
```

#### Пример

```bash
vm myvm start
```

Значения будут доступны так:

```python
ns.target
ns.action
```

---

### 7.1.7. Типизация аргументов

Парсер может автоматически преобразовывать значения.

```python
parser.add_argument("--cpus", type=int, default=1)
parser.add_argument("--memory", type=int, default=1024)
```

#### Пример

```bash
vm create --cpus 4 --memory 4096
```

Если передать неверное значение:

```bash
vm create --cpus abc
```

будет выброшено исключение `CommandArgumentError`.

---

### 7.1.8. Обязательные аргументы

Для опций можно указать обязательность:

```python
parser.add_argument("--user", required=True, help="Имя пользователя")
```

#### Пример

```bash
userinfo --user alice
```

Если аргумент не передан, парсер вернёт ошибку.

---

### 7.1.9. Ограничение значений через `choices`

Можно ограничить допустимые значения аргумента:

```python
parser.add_argument("--mode", choices=["fast", "safe"], default="fast")
```

#### Пример

```bash
backup --mode fast
backup --mode safe
```

Если передать значение вне списка, будет ошибка.

---

### 7.1.10. Несколько значений (`nargs`)

Парсер поддерживает несколько режимов количества значений.

#### Необязательное значение

```python
parser.add_argument("file", nargs="?")
```

#### Ноль или больше значений

```python
parser.add_argument("files", nargs="*")
```

#### Один или больше значений

```python
parser.add_argument("files", nargs="+")
```

#### Пример

```python
parser.add_argument("files", nargs="+", help="Список файлов")
```

```bash
merge a.txt b.txt c.txt
```

---

### 7.1.11. Повторяемые аргументы

Если аргумент можно указывать несколько раз, удобно использовать `action="append"`:

```python
parser.add_argument("--tag", action="append", help="Тег")
```

#### Пример

```bash
task create --tag urgent --tag work --tag backend
```

Результат:

```python
ns.tag == ["urgent", "work", "backend"]
```

---

### 7.1.12. Счётчик повторений

Для увеличения уровня подробности удобно использовать `action="count"`:

```python
parser.add_argument("-v", "--verbose", action="count", help="Уровень подробности")
```

#### Пример

```bash
cmd -v
cmd -vv
cmd -vvv
```

Результат:

```python
ns.verbose == 3
```

---

### 7.1.13. Автоматическая справка (`-h`, `--help`)

Каждый парсер автоматически поддерживает:

```bash
command -h
command --help
```

#### Пример

```python
parser = api.parser("userinfo", description="Показать информацию о пользователе")
parser.add_argument("--user", required=True, help="Имя пользователя")
```

Вызов:

```bash
userinfo --help
```

вернёт help-сообщение с usage, списком аргументов и описанием.

---

### 7.1.14. Подкоманды

Для сложных команд рекомендуется использовать **подкоманды**.

Примеры:

* `sshkey add`
* `sshkey remove`
* `sshkey list`
* `vm create`
* `vm delete`
* `vm start`

#### Создание подкоманд

```python
parser = api.parser("vm", description="Управление виртуальными машинами")
subparsers = parser.add_subparsers(dest="command", required=True)

create = subparsers.add_parser("create", help="Создать VM")
create.add_argument("--name", required=True, help="Имя виртуальной машины")
create.add_argument("--cpus", type=int, default=1)
create.add_argument("--memory", type=int, default=1024)

delete = subparsers.add_parser("delete", help="Удалить VM")
delete.add_argument("--name", required=True, help="Имя виртуальной машины")
```

#### Разбор

```python
ns = parser.parse_args(api.args)
```

#### Пример запуска

```bash
vm create --name testvm --cpus 2 --memory 2048
vm delete --name testvm
```

#### Результат

Для первой команды:

```python
ns.command == "create"
ns.name == "testvm"
ns.cpus == 2
ns.memory == 2048
```

---

### 7.1.15. Полный пример с подкомандами

```python
async def execute(api: CommandAPI) -> str | None:
    parser = api.parser("vm", description="Управление виртуальными машинами")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create", help="Создать VM")
    create.add_argument("--name", required=True, help="Имя виртуальной машины")
    create.add_argument("--cpus", type=int, default=1)
    create.add_argument("--memory", type=int, default=1024)

    delete = subparsers.add_parser("delete", help="Удалить VM")
    delete.add_argument("--name", required=True, help="Имя виртуальной машины")

    try:
        ns = parser.parse_args(api.args)
    except CommandArgumentError as e:
        return f"Ошибка: {e}\n"

    if ns.command == "create":
        return f"Создание VM {ns.name}: {ns.cpus} CPU, {ns.memory} MB RAM\n"

    if ns.command == "delete":
        return f"Удаление VM {ns.name}\n"

    return None
```

---

### 7.1.16. Ручной разбор подкоманд (без парсера)

Если команда очень простая, подкоманды можно обрабатывать вручную:

```python
async def execute(api: CommandAPI) -> str | None:
    if not api.args:
        return "Usage: sshkey <add|remove|list> ...\n"

    subcmd = api.args[0]

    if subcmd == "add":
        ...
    elif subcmd == "remove":
        ...
    elif subcmd == "list":
        ...
    else:
        return f"Unknown subcommand: {subcmd}\n"
```

Однако для большинства команд предпочтительнее использовать встроенный `ArgumentParser`, так как он:

* автоматически валидирует аргументы
* формирует help/usage
* поддерживает типы и обязательные поля
* упрощает расширение команды

---

## 7.2. Ручной парсинг (альтернатива)

Если команда простая или требует полного контроля, допустим и ручной парсинг:

```python
from dataclasses import dataclass
from sshserver.commandapi import CommandAPI, CommandArgumentError

HELP = """Usage: userinfo [OPTIONS]

Show information about current user.

Options:
  -a, --all     Show all fields
  -h, --help    Show this help
"""

@dataclass
class ParsedArgs:
    show_all: bool = False
    help: bool = False

def parse_args(args: tuple[str, ...]) -> ParsedArgs:
    parsed = ParsedArgs()

    for arg in args:
        if arg in ("-h", "--help"):
            parsed.help = True
        elif arg in ("-a", "--all"):
            parsed.show_all = True
        else:
            raise CommandArgumentError(f"Unknown argument: {arg}")

    return parsed

async def execute(api: CommandAPI) -> str | None:
    parsed = parse_args(api.args)

    if parsed.help:
        return HELP

    return "OK\n"
```

---

# 8. Работа с вводом и выводом (IO)

## 8.1. Возврат значения из команды

Функция `execute(...)` может:

* вернуть `str`
* вернуть `bytes`
* вернуть `None`

### Рекомендуемый стиль

* **простые команды** → `return "text\n"`
* **потоковый/интерактивный вывод** → `await api.write(...)`
* **PTY/полноэкранные команды** → через `api.run_interactive()` или `api.pty`

---

## 8.2. Методы вывода `CommandAPI`

В `CommandAPI` уже есть готовые методы вывода.

### Базовые

```python
await api.write("Hello")           # запись строки или байтов
await api.writeln("Hello")         # с переводом строки
await api.write_line("Hello")      # псевдоним writeln
await api.flush()                  # принудительный сброс буфера (если есть)
await api.clear()                  # очистка экрана (ANSI)
```

### Цветные helper’ы

```python
await api.write_success("Done")    # зелёный
await api.write_error("Failed")    # красный
await api.write_warning("Warning") # жёлтый
```

---

## 8.3. Прямой доступ к `Terminal`

Если нужен низкий уровень — терминал доступен напрямую:

```python
terminal = api.terminal
```

И дальше можно работать напрямую:

```python
await terminal.output.write("Привет\n")
line = await terminal.input.read_str()
```

Но **для новых команд** предпочтительно сначала смотреть, есть ли уже helper в `CommandAPI`.

---

# 9. Интерактивный ввод

`CommandAPI` предоставляет готовые методы интерактивного ввода.

### Ввод строки

```python
name = await api.read_line("Enter name: ")
```

### Ввод строки без echo

```python
secret = await api.read_line_secure("Enter secret: ")
```

### Простая обёртка

```python
name = await api.prompt("Enter name: ")
```

### Подтверждение

```python
if not await api.confirm("Delete VM? [y/N]: "):
    return "Cancelled.\n"
```

`confirm()` считает подтверждением только:

* `y`
* `yes`

в нижнем регистре после `strip()`. Если пользователь ввёл что-то другое — возвращает `False` (и **не** бросает исключение, как указано в некоторых ранних версиях документации).  
Исключение `CommandAbort` не выбрасывается; оно может быть поднято вручную, если нужно.

---

# 10. Работа с окружением (`UserEnvironment`)

## 10.1. Временные переменные сессии

Текущее окружение доступно через:

```python
env = api.env
```

Тип — `UserEnvironment`, который берётся из текущей сессии.

Обычные сценарии:

```python
env.set("PS1", "pve> ")
env.set("EDITOR", "nano")
value = env.get("USER")
env.unset("TEMP_VAR")

text = env.substitute("Hello $USER")
```

Для удобства есть методы-шорткаты прямо в `api`:

```python
api.env_set("EDITOR", "nano")
api.env_get("EDITOR")
api.env_unset("TEMP_VAR")
api.env_substitute("Hello $USER")
```

---

## 10.2. Постоянное сохранение в БД (`saved_env`)

Важно понимать:

> Изменения через `api.env` живут **только в текущей сессии**, если ты отдельно не сохранишь их в БД.

Если ты хочешь сделать изменение **постоянным**, нужно обновлять поле `saved_env` в таблице `users`.

Пример:

```python
import json

row = await api.fetch_one(
    "SELECT saved_env FROM users WHERE username = ?",
    (api.username,)
)

if not row:
    return "User not found.\n"

(saved_env_raw,) = row
saved_env = json.loads(saved_env_raw or "{}")
saved_env["EDITOR"] = "nano"

await api.execute(
    "UPDATE users SET saved_env = ? WHERE username = ?",
    (json.dumps(saved_env, ensure_ascii=False), api.username)
)
await api.db.commit()

api.env.set("EDITOR", "nano")
return "EDITOR saved.\n"
```

---

# 11. Работа с PTY и интерактивными процессами

## 11.1. Быстрый способ: `api.run_interactive()`

Для большинства интерактивных программ рекомендуется использовать:

```python
await api.run_interactive("/bin/bash")
```

или:

```python
await api.run_interactive(
    cmd="/bin/bash",
    args=["-i"],
    cwd="/root",
    env=api.env.as_dict(),
    alt_screen=True   # по умолчанию True
)
```

`run_interactive()` делает сразу несколько вещей автоматически:

* гарантирует наличие PTY,
* синхронизирует размер окна (`rows`, `cols`),
* переключает пользователя в альтернативный экран (если `alt_screen=True`),
* запускает процесс,
* подключает SSH ↔ PTY,
* после завершения возвращает экран обратно.

---

## 11.2. Низкоуровневая работа через `api.pty`

Если нужен полный контроль, PTY доступен напрямую:

```python
pty = api.pty
```

Дальше можно использовать методы `PTYHandler`, например:

```python
await pty.ensure()
await pty.resize(api.rows, api.cols)

proc = await pty.spawn(
    "/bin/bash",
    ["-i"],
    env=api.env.as_dict(),
    cwd="/root"
)

await pty.attach_streams()
await proc.wait()
```

---

## 11.3. Важно: `attach_streams()` блокирует выполнение

Это один из самых важных моментов в архитектуре интерактивных команд:

> После вызова `attach_streams()` выполнение команды **останавливается**, пока интерактивный процесс не завершится.

То есть вот такой код:

```python
await api.pty.attach_streams()
return "Done\n"
```

означает:

* пользователь получает управление PTY;
* только **после выхода из процесса** выполнение дойдёт до `return`.

Это критично для понимания потока управления.

---

## 11.4. Завершение PTY и cleanup

Если ты используешь `api.run_interactive()`, cleanup уже частично сделан внутри метода: альтернативный экран будет восстановлен в `finally`.

Если ты работаешь с `api.pty` вручную, рекомендуется:

* оборачивать интерактивный режим в `try/finally`;
* при необходимости вручную возвращать экран и отключать режимы ввода;
* следить, чтобы после аварийного завершения пользователь не остался в “сломленном” терминале.

---

## 11.5. Полноэкранные команды и альтернативный экран

`CommandAPI` уже даёт готовые helper’ы для альтернативного экрана (см. раздел 13).

---

# 12. Работа с мышью

Доступ к мыши есть через:

```python
mouse = api.mouse
```

Это shortcut к `api.terminal.input.mouse`.

`CommandAPI` предоставляет удобные методы для включения/отключения мыши:

```python
await api.mouse_enable(modes=1006)          # включить SGR режим
await api.mouse_enable([1000, 1006])        # несколько режимов
await api.mouse_disable()                   # выключить все
```

Пример использования:

```python
async def execute(api: CommandAPI) -> str | None:
    await api.mouse_enable([1002, 1006])
    try:
        await api.writeln("Mouse mode enabled. Press Enter to exit.")
        await api.read_line()
    finally:
        await api.mouse_disable()

    return "Done.\n"
```

### Рекомендация

Если включаешь мышь — **всегда отключай её в `finally`**.

---

# 13. Альтернативный экран

`CommandAPI` предоставляет методы для переключения между основным и альтернативным буфером терминала (xterm 1049):

```python
await api.enter_alt_screen()
await api.exit_alt_screen()
```

Пример:

```python
async def execute(api: CommandAPI) -> str | None:
    await api.enter_alt_screen()
    try:
        await api.clear()
        await api.writeln("Interactive mode")
        await api.read_line("Press Enter to exit...")
    finally:
        await api.exit_alt_screen()
```

Это правильный шаблон для полноэкранных команд и TUI-режима.

---

# 14. Работа с базой данных

## 14.1. Доступ к БД

База данных доступна через:

```python
db = api.db
```

Это lazy property: объект БД поднимается через `GlobalStore.get().require("db")` только при первом обращении.

---

## 14.2. Shortcut-методы через `api`

Для удобства `CommandAPI` предоставляет shortcut’ы:

```python
await api.fetch_one(query, params)      # одна строка (tuple) или None
await api.fetch_all(query, params)      # список строк (list of tuple)
await api.fetch_val(query, params)      # скалярное значение (первое поле первой строки)
await api.execute(query, params)        # для INSERT/UPDATE/DELETE
```

Они просто проксируют вызовы к `api.db`.

---

## 14.3. Что возвращают `fetch_one()` и `fetch_all()`

⚠️ **Важно:** в текущей реализации строки из БД **являются кортежами (tuple)**.

Поэтому **не полагайся** на такой код:

```python
row["username"]   # ошибка!
row.items()       # ошибка!
```

### Рекомендуемый безопасный способ

Использовать распаковку:

```python
row = await api.fetch_one(
    "SELECT username, group_id, created_at FROM users WHERE username = ?",
    (api.username,)
)

if not row:
    return "User not found.\n"

db_username, group_id, created_at = row
```

---

## 14.4. Практические примеры SQL

### SELECT одной строки

```python
row = await api.fetch_one(
    "SELECT group_id, created_at FROM users WHERE username = ?",
    (api.username,)
)
```

### SELECT нескольких строк

```python
rows = await api.fetch_all(
    "SELECT username, group_id FROM users ORDER BY username"
)

lines = []
for username, group_id in rows:
    lines.append(f"{username}: group={group_id}")

return "\n".join(lines) + "\n"
```

### UPDATE / INSERT

```python
await api.execute(
    "UPDATE users SET group_id = ? WHERE username = ?",
    (2, "alice")
)
await api.db.commit()
```

---

## 14.5. Транзакции и обработка ошибок

Если меняется несколько связанных сущностей — рекомендуется использовать транзакции:

```python
import logging

logger = logging.getLogger(__name__)

async def execute(api: CommandAPI) -> str | None:
    try:
        async with api.db.transaction():
            await api.execute(
                "UPDATE users SET group_id = ? WHERE username = ?",
                (2, "alice")
            )
            await api.execute(
                "UPDATE users SET group_id = ? WHERE username = ?",
                (2, "bob")
            )

        return "Updated.\n"

    except Exception as e:
        logger.exception("Failed to update groups")
        return f"Database error: {e}\n"
```

### Практические правила

* одна запись → можно `execute()` + `commit()`
* несколько связанных записей → `async with db.transaction():`
* любые ошибки → логировать
* не делать предположений о типе row без проверки

---

# 15. Работа с JSON-полями в таблице `users`

Актуальная структура:

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

Здесь несколько полей хранятся как JSON в `TEXT`.

---

## 15.1. `ssh_keys`

Поле `ssh_keys` хранит JSON-массив.

### Чтение

```python
import json

row = await api.fetch_one(
    "SELECT ssh_keys FROM users WHERE username = ?",
    (api.username,)
)

if not row:
    return "User not found.\n"

(ssh_keys_raw,) = row
ssh_keys = json.loads(ssh_keys_raw or "[]")
```

### Обновление

```python
ssh_keys.append("ssh-ed25519 AAAA... newkey")

await api.execute(
    "UPDATE users SET ssh_keys = ? WHERE username = ?",
    (json.dumps(ssh_keys, ensure_ascii=False), api.username)
)
await api.db.commit()
```

---

## 15.2. `saved_env`

Поле `saved_env` хранит JSON-объект.

```python
import json

row = await api.fetch_one(
    "SELECT saved_env FROM users WHERE username = ?",
    (api.username,)
)

if not row:
    return "User not found.\n"

(saved_env_raw,) = row
saved_env = json.loads(saved_env_raw or "{}")
saved_env["EDITOR"] = "nano"

await api.execute(
    "UPDATE users SET saved_env = ? WHERE username = ?",
    (json.dumps(saved_env, ensure_ascii=False), api.username)
)
await api.db.commit()
```

---

## 15.3. `history`

Поле `history` хранит JSON-массив.

### Пример чтения истории

```python
import json

row = await api.fetch_one(
    "SELECT history FROM users WHERE username = ?",
    (api.username,)
)

if not row:
    return "User not found.\n"

(history_raw,) = row
history = json.loads(history_raw or "[]")
```

### Пример обновления истории

```python
history.append("userinfo --all")

await api.execute(
    "UPDATE users SET history = ? WHERE username = ?",
    (json.dumps(history, ensure_ascii=False), api.username)
)
await api.db.commit()
```

### Что это поле означает

`history` предназначено для хранения истории команд/действий пользователя.  
Если команда хочет явно логировать своё действие в пользовательскую историю — она может обновлять это поле вручную.

---

# 16. `api.user` и `UserContext`

`CommandAPI` содержит свойство:

```python
user = api.user
```

Оно лениво создаёт `UserContext(self.username, self.db)` и кэширует его внутри `CommandAPI`.

**На текущий момент** `UserContext` находится в разработке. В нём определены базовые методы:

* `get_field(field, default)` — получить сырое значение поля
* `set_field(field, value)` — установить значение поля
* `get_json(field, default)` — получить JSON-данные
* `set_json(field, data)` — сохранить JSON
* Шорткаты: `get_ssh_keys()`, `set_ssh_keys(keys)`, `get_history()`, `set_history(history)`

Однако эти методы **пока не реализованы** (в коде стоят `pass`). Поэтому в текущей версии рекомендуется использовать прямые SQL-запросы через `api.fetch_one` / `api.execute`. Как только `UserContext` будет доработан, его использование станет предпочтительным.

---

# 17. Криптография

`CommandAPI` предоставляет методы для шифрования/расшифровки с использованием мастер-ключа из конфига (AES-GCM):

```python
encrypted = api.encrypt("secret")      # шифрование
decrypted = api.decrypt(encrypted)     # расшифровка
```

Для явного контекста работы с БД доступны алиасы:

```python
api.db_encrypt(value)
api.db_decrypt(value)
```

Они работают так же, как `encrypt`/`decrypt`.

### Пример использования в БД

```python
encrypted_secret = api.encrypt(api_secret)
await api.execute(
    "UPDATE users SET api_secret = ? WHERE username = ?",
    (encrypted_secret, api.username)
)
await api.db.commit()

# При чтении:
row = await api.fetch_one("SELECT api_secret FROM users WHERE username = ?", (api.username,))
if row:
    secret = api.decrypt(row[0])
```

---

# 18. Глобальные сервисы и `GlobalStore`

Сейчас `CommandAPI` уже использует `GlobalStore` внутри себя для доступа к БД и конфигурации.

Это важно по архитектуре:

> **Команды не должны напрямую использовать `GlobalStore`, если нужный сервис уже доступен через `api`.**

Сейчас через `api` уже доступны:

* `api.db`
* `api.user`
* `api.terminal`
* `api.env`
* `api.permissions`
* `api.config`

Если в будущем в `GlobalStore` появятся другие сервисы (PVE client, cache, auth manager), их также желательно пробрасывать в `CommandAPI`.

В случае крайней необходимости можно получить `GlobalStore` через `api.global_store()`:

```python
store = api.global_store()
pve = store.require("pve_client")
```

---

# 19. Исключения команд

В `sshserver.commandapi.exceptions` определён базовый набор исключений:

* `CommandError` — базовый класс для всех ошибок команд.
* `CommandPermissionError` — недостаточно прав.
* `CommandArgumentError` — ошибка разбора аргументов.
* `CommandAbort` — операция отменена пользователем (например, Ctrl+C).
* `CommandNotFoundError` — команда не найдена (внутреннее использование).
* `CommandRuntimeError` — ошибка во время выполнения (PTY, DB, сеть и т.д.).

### Когда использовать

#### `CommandPermissionError`

Когда пользователь не имеет права выполнить действие:

```python
api.require_permission("db_viewer")
```

или вручную:

```python
from sshserver.commandapi import CommandPermissionError

raise CommandPermissionError("Недостаточно прав")
```

#### `CommandArgumentError`

Когда аргументы команды неверны:

```python
from sshserver.commandapi import CommandArgumentError

raise CommandArgumentError("Unknown argument: --foo")
```

#### `CommandAbort`

Когда пользователь явно отменил действие:

```python
from sshserver.commandapi import CommandAbort

if not await api.confirm("Continue? [y/N]: "):
    raise CommandAbort("Cancelled by user")
```

### Практический стиль

* для “обычных пользовательских ошибок” можно просто `return "..."`;
* для систематических сценариев и parser/permission-ошибок лучше использовать typed exceptions.

---

# 20. Логирование

У `CommandAPI` уже есть логгер:

```python
api.logger
```

Он создаётся как:

```python
logging.getLogger(f"cmd.{username}")
```

и уже готов к использованию.

### Примеры

```python
api.logger.info("User opened shell")
api.logger.warning("Unknown option passed")
api.logger.exception("Database update failed")
```

### Что логировать

Рекомендуется логировать:

* изменение прав/групп;
* обновление SSH-ключей;
* интерактивные shell/PTY-сессии;
* ошибки SQL;
* любые административные действия.

---

# 21. Размеры терминала

Размеры терминала (строки и столбцы) доступны через свойства:

```python
api.rows    # высота
api.cols    # ширина
```

Они обновляются автоматически при изменении размера окна SSH-клиента.

---

# 22. Тестирование и локальная отладка

Пока команды переписываются под новую API, полезно придерживаться такого цикла:

### 1. Запусти сервер

Запусти SSH server в dev-режиме или обычным способом, которым ты уже тестируешь команды.

### 2. Подключись по SSH

Подключись локально или с тестового клиента:

```bash
ssh user@host -p <port>
```

### 3. Вызови команду

Проверь:

* корректный вывод;
* help;
* ошибки;
* права;
* интерактивный ввод.

### 4. Смотри логи сервера

Особенно полезно смотреть:

* stack trace ошибок;
* SQL-ошибки;
* ошибки PTY;
* ошибки парсинга.

### 5. Отладка команд

Для отладки удобно:

* временно писать в `api.logger`
* делать маленькие тестовые команды
* сначала писать неинтерактивную логику, потом добавлять PTY/мышь/экран

---

# 23. Лучшие практики

1. **Новые команды пишите через `CommandAPI`.**
   Не используйте старый стиль, если нет крайней необходимости.

2. **Не тяните `get_current_session()` и `GlobalStore` напрямую.**
   Всё основное уже есть в `api`.

3. **Не используйте обычный `argparse` как основной parser.**
   Он плохо подходит для SSH-команд.

4. **Не полагайтесь на `dict`-строки из БД.**
   Считайте, что SQL-строка — это `tuple`, пока не доказано обратное.

5. **Все JSON-поля явно сериализуйте/десериализуйте.**
   Используйте `json.loads(raw or "[]")` / `json.loads(raw or "{}")`.

6. **Интерактивные режимы всегда оборачивайте в `try/finally`.**
   Особенно если используете:

   * альтернативный экран
   * мышь
   * PTY

7. **Для проверки прав используйте `api.require_permission()`.**
   Это чище и единообразнее.

8. **Для простых команд возвращайте строку.**
   Для потокового вывода — `await api.write(...)`.

9. **Изменения `api.env` не постоянны сами по себе.**
   Если нужна персистентность — обновляйте `saved_env` в БД.

10. **Логируйте административные действия.**
    Особенно всё, что меняет состояние системы или пользователей.

---

# 24. Полные примеры команд

## 24.1. Простая команда

```python
from sshserver.commandapi import CommandAPI

async def execute(api: CommandAPI) -> str | None:
    return f"Hello, {api.username}!\n"

command = {
    "name": "hello",
    "help": "Say hello",
    "func": execute,
}
```

---

## 24.2. Команда с парсером

```python
from sshserver.commandapi import CommandAPI, CommandArgumentError

async def execute(api: CommandAPI) -> str | None:
    parser = api.parser("example")
    parser.add_flag("-v", "--verbose", help="Verbose output")
    parser.add_option("-n", "--name", default="world", help="Name to greet")
    parser.add_positional("target", help="Target (optional)", required=False)

    try:
        ns = parser.parse(api.args)
    except CommandArgumentError as e:
        return f"Error: {e}\n"

    if ns.verbose:
        await api.writeln(f"Parsed: {ns}")

    return f"Hello, {ns.name}!\n"

command = {
    "name": "greet",
    "help": "Greet someone",
    "func": execute,
}
```

---

## 24.3. Команда с правами и БД

```python
import json
from sshserver.commandapi import CommandAPI, CommandArgumentError

HELP = """Usage: userinfo [OPTIONS]

Show information about current user.

Options:
  -a, --all     Show all fields
  -h, --help    Show this help
"""

async def execute(api: CommandAPI) -> str | None:
    api.require_permission("db_viewer")

    parser = api.parser("userinfo")
    parser.add_flag("-a", "--all", help="Show all fields")
    parser.add_flag("-h", "--help", help="Show help")

    try:
        ns = parser.parse(api.args)
    except CommandArgumentError as e:
        return f"Error: {e}\n"

    if ns.help:
        return HELP

    row = await api.fetch_one(
        "SELECT username, group_id, created_at, ssh_keys, saved_env, history "
        "FROM users WHERE username = ?",
        (api.username,)
    )

    if not row:
        return f"User {api.username} not found in database.\n"

    db_username, group_id, created_at, ssh_keys_raw, saved_env_raw, history_raw = row

    if ns.all:
        ssh_keys = json.loads(ssh_keys_raw or "[]")
        saved_env = json.loads(saved_env_raw or "{}")
        history = json.loads(history_raw or "[]")

        return (
            f"Username: {db_username}\n"
            f"Group ID: {group_id}\n"
            f"Created at: {created_at}\n"
            f"SSH keys: {len(ssh_keys)} entries\n"
            f"Saved env vars: {len(saved_env)} entries\n"
            f"History entries: {len(history)}\n"
        )

    return (
        f"Username: {db_username}\n"
        f"Group ID: {group_id}\n"
        f"Created at: {created_at}\n"
    )

command = {
    "name": "userinfo",
    "help": "Show information about current user",
    "func": execute,
    "permissions": ["db_viewer"]
}
```

---

## 24.4. Интерактивная команда подтверждения

```python
from sshserver.commandapi import CommandAPI, CommandAbort

async def execute(api: CommandAPI) -> str | None:
    if not await api.confirm("Delete temp data? [y/N]: "):
        return "Cancelled by user.\n"

    await api.write_success("Deleted.")
    return None

command = {
    "name": "confirmtest",
    "help": "Test confirmation flow",
    "func": execute,
}
```

---

## 24.5. Интерактивный shell

```python
from sshserver.commandapi import CommandAPI

async def execute(api: CommandAPI) -> str | None:
    await api.run_interactive(
        cmd="/bin/bash",
        args=["-i"],
        cwd="/root",
        env=api.env.as_dict()
    )
    return "Shell session finished.\n"

command = {
    "name": "bash",
    "help": "Open interactive shell",
    "func": execute,
}
```