# Документация API команд PVE SSH Server

**Версия документации:** 3.0 (май 2026)  
**Статус:** Актуально для ветки `dev`  

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
  * [6.4. Force Group и limited_inheritance](#64-force-group-и-limited_inheritance)
* [7. Работа с аргументами](#7-работа-с-аргументами)
  * [7.1. Декларативный парсер: `build_parser`](#71-декларативный-парсер-build_parser)
  * [7.2. Получение парсера в `execute`](#72-получение-парсера-в-execute)
  * [7.3. Позиционные аргументы](#73-позиционные-аргументы)
  * [7.4. Флаги (`store_true`)](#74-флаги-store_true)
  * [7.5. Опции со значением](#75-опции-со-значением)
  * [7.6. Короткие и длинные формы](#76-короткие-и-длинные-формы)
  * [7.7. Группировка коротких флагов](#77-группировка-коротких-флагов)
  * [7.8. Типизация (`type=int` и др.)](#78-типизация-typeint-и-др)
  * [7.9. Обязательные аргументы](#79-обязательные-аргументы)
  * [7.10. Ограничение значений (`choices`)](#710-ограничение-значений-choices)
  * [7.11. Несколько значений (`nargs`)](#711-несколько-значений-nargs)
  * [7.12. Повторяемые аргументы (`append`)](#712-повторяемые-аргументы-append)
  * [7.13. Счётчик (`count`)](#713-счётчик-count)
  * [7.14. Подкоманды (`add_subparsers`)](#714-подкоманды-add_subparsers)
  * [7.15. Автоматическая справка](#715-автоматическая-справка)
  * [7.16. Обработка ошибок парсера](#716-обработка-ошибок-парсера)
  * [7.17. Ручной парсинг (альтернатива)](#717-ручной-парсинг-альтернатива)
* [8. Подсистема LSP: автодополнение и подсветка](#8-подсистема-lsp-автодополнение-и-подсветка)
  * [8.1. Как LSP использует `build_parser`](#81-как-lsp-использует-build_parser)
  * [8.2. Lexer и токенизация](#82-lexer-и-токенизация)
  * [8.3. Autocomplete (меню автодополнения)](#83-autocomplete-меню-автодополнения)
  * [8.4. Inline hints](#84-inline-hints)
  * [8.5. Syntax highlighting](#85-syntax-highlighting)
  * [8.6. AST highlighting](#86-ast-highlighting)
* [9. Работа с вводом и выводом (IO)](#9-работа-с-вводом-и-выводом-io)
  * [9.1. Возврат значения из команды](#91-возврат-значения-из-команды)
  * [9.2. Методы вывода `CommandAPI`](#92-методы-вывода-commandapi)
  * [9.3. Прямой доступ к `Terminal`](#93-прямой-доступ-к-terminal)
* [10. Интерактивный ввод](#10-интерактивный-ввод)
  * [10.1. `read_line` — ввод строки](#101-read_line--ввод-строки)
  * [10.2. `read_line_secret` — скрытый ввод](#102-read_line_secret--скрытый-ввод)
  * [10.3. `prompt` — псевдоним `read_line`](#103-prompt--псевдоним-read_line)
  * [10.4. `confirm` — подтверждение (выбрасывает `CommandAbort`)](#104-confirm--подтверждение-выбрасывает-commandabort)
* [11. Работа с окружением (`UserEnvironment`)](#11-работа-с-окружением-userenvironment)
  * [11.1. Временные переменные сессии](#111-временные-переменные-сессии)
  * [11.2. Постоянное сохранение в БД (`saved_env`)](#112-постоянное-сохранение-в-бд-saved_env)
* [12. Работа с историей команд (`api.history`)](#12-работа-с-историей-команд-apihistory)
* [13. Работа с PTY и интерактивными процессами](#13-работа-с-pty-и-интерактивными-процессами)
  * [13.1. Быстрый способ: `api.run_interactive()`](#131-быстрый-способ-apirun_interactive)
  * [13.2. Низкоуровневая работа через `api.pty`](#132-низкоуровневая-работа-через-apipty)
  * [13.3. Важно: `attach_streams()` блокирует выполнение](#133-важно-attach_streams-блокирует-выполнение)
  * [13.4. Завершение PTY и cleanup](#134-завершение-pty-и-cleanup)
  * [13.5. Полноэкранные команды и альтернативный экран](#135-полноэкранные-команды-и-альтернативный-экран)
* [14. Работа с мышью](#14-работа-с-мышью)
* [15. Альтернативный экран](#15-альтернативный-экран)
* [16. Работа с базой данных](#16-работа-с-базой-данных)
  * [16.1. Доступ к БД](#161-доступ-к-бд)
  * [16.2. Shortcut-методы через `api`](#162-shortcut-методы-через-api)
  * [16.3. Что возвращают `fetch_one()` и `fetch_all()`](#163-что-возвращают-fetch_one-и-fetch_all)
  * [16.4. Практические примеры SQL](#164-практические-примеры-sql)
  * [16.5. Транзакции и обработка ошибок](#165-транзакции-и-обработка-ошибок)
* [17. Работа с JSON-полями в таблице `users`](#17-работа-с-json-полями-в-таблице-users)
  * [17.1. `ssh_keys`](#171-ssh_keys)
  * [17.2. `saved_env`](#172-saved_env)
  * [17.3. `history`](#173-history)
* [18. `api.user` и `UserContext`](#18-apiuser-и-usercontext)
* [19. Криптография](#19-криптография)
* [20. Глобальные сервисы и `GlobalStore`](#20-глобальные-сервисы-и-globalstore)
* [21. Исключения команд](#21-исключения-команд)
* [22. Логирование](#22-логирование)
* [23. Размеры терминала](#23-размеры-терминала)
* [24. Система ввода: Line Editor](#24-система-ввода-line-editor)
  * [24.1. Input scroll (прокрутка ввода)](#241-input-scroll-прокрутка-ввода)
  * [24.2. Управление курсором](#242-управление-курсором)
* [25. Keybind layer (слой горячих клавиш)](#25-keybind-layer-слой-горячих-клавиш)
* [26. Тестирование и локальная отладка](#26-тестирование-и-локальная-отладка)
* [27. Лучшие практики](#27-лучшие-практики)
* [28. Полные примеры команд](#28-полные-примеры-команд)
  * [28.1. Простая команда](#281-простая-команда)
  * [28.2. Команда с `build_parser` и подкомандами](#282-команда-с-build_parser-и-подкомандами)
  * [28.3. Команда с правами и БД](#283-команда-с-правами-и-бд)
  * [28.4. Интерактивная команда подтверждения](#284-интерактивная-команда-подтверждения)
  * [28.5. Интерактивный shell через `run_interactive()`](#285-интерактивный-shell-через-run_interactive)
  * [28.6. Интерактивный shell через низкоуровневый PTY](#286-интерактивный-shell-через-низкоуровневый-pty)

---

# 1. Общая идея

Начиная с текущей версии ветки `dev`, команды должны использовать **единый стабильный слой** — `CommandAPI` (версия 3.0). Его задача: **скрыть внутреннюю архитектуру SSH-сервера** и дать команде один объект с доступом ко всему необходимому:

* текущему пользователю,
* аргументам,
* терминалу,
* окружению,
* правам,
* БД,
* PTY,
* логгеру,
* парсеру аргументов,
* интерактивному вводу/выводу,
* истории команд,
* криптографии.

Это означает, что **новые команды не должны напрямую полагаться** на:

* `get_current_session()`
* `session.extra["terminal"]`
* `session.extra["permissions"]`
* `GlobalStore.get().require("db")`

Вместо этого команда работает через `api`. Реализация `CommandAPI` предоставляет эти возможности централизованно.

> **Ключевое изменение v3.0:** парсер теперь объявляется декларативно через `build_parser(parser)` в поле команды. Этот парсер используется как в `execute`, так и в подсистеме LSP (автодополнение, подсветка).

---

# 2. Структура команд

## 2.1. Single-file команда

```python
# commands/internal/about.py
from sshserver.commandapi import CommandAPI

def build_parser(parser):
    parser.description = command["help"]

async def execute(api: CommandAPI) -> str | None:
    return f"Hello, {api.username}!"

command = {
    "name": "about",
    "help": "Show information about current session",
    "func": execute,
    "build_parser": build_parser,
}
```

---

## 2.2. Command Module (команда-пакет)

```python
# commands/edit/__init__.py
from sshserver.commandapi import CommandAPI

def build_parser(parser):
    parser.description = command["help"]

async def execute(api: CommandAPI):
    return "Edit command"

command = {
    "type": "command",
    "name": "edit",
    "help": "Edit configuration",
    "func": execute,
    "permissions": ["config_edit"],
    "build_parser": build_parser,
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

def build_parser(parser):
    parser.description = command["help"]

async def execute(api: CommandAPI) -> str | None:
    return f"Hello, {api.username}!"
```

Это **новый рекомендуемый стандарт**.  
Команда получает **один объект** `api`, а не `username` и не набор разрозненных helper'ов.

> **Важно:** поле `build_parser` в `command` обязательно для всех новых команд. Оно нужно для LSP (автодополнение, подсветка синтаксиса).

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

При создании `CommandAPI(username, args, parser=None)` объект инициализирует и кэширует доступ к ключевым сервисам сессии и среды выполнения.

Доступные поля и свойства:

```python
api.username        # имя текущего пользователя
api.args            # tuple[str, ...] аргументов команды
api.session         # текущая SSH-сессия
api.terminal        # Terminal
api.env             # UserEnvironment
api.history         # History (объект истории команд)
api.permissions     # set[str]
api.logger          # logging.Logger

api.db              # Database (lazy)
api.pty             # PTYHandler
api.mouse           # MouseHandler
api.rows            # высота терминала (строки)
api.cols            # ширина терминала (символы)
api.pixheight       # высота терминала (в пикселях)
api.pixwidth        # ширина терминала (в пикселях)
api.user            # UserContext (lazy)
api.config          # объект конфигурации (lazy)
```

---

## 5.2. Доступ к сессии и служебным данным

`CommandAPI` сам использует текущую SSH-сессию и вытаскивает оттуда нужные объекты, включая `terminal`, `env`, `permissions` и `history`.

Эквивалентно старому стилю:

```python
session = get_current_session()
terminal = session.extra["terminal"]
env = session.extra["env"]
permissions = session.extra.get("permissions", [])
history = session.extra.get("history", None)
```

Теперь всё это уже доступно через:

```python
api.terminal
api.env
api.permissions
api.history
```

### Что находится в `session.extra`

На текущий момент для команд особенно важны следующие ключи:

* `session.extra["terminal"]` → объект `Terminal`
* `session.extra["env"]` → объект `UserEnvironment`
* `session.extra["permissions"]` → список прав пользователя
* `session.extra["history"]` → объект `History`

Именно из этих данных `CommandAPI` собирает свой runtime-контекст.

---

# 6. Система прав доступа

## 6.1. Наследование прав

Система наследования прав:

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

* **доступ к самой команде** может быть защищён через `command["permissions"]`
* **доступ к конкретному действию** проверяется уже внутри логики команды

---

## 6.4. Force Group и limited_inheritance

Добавлены расширенные опции управления правами:

* **Force Group** — принудительная привязка пользователя к группе
* **limited_inheritance** — ограниченное наследование прав (наследуются только явно указанные)

Эти опции задаются на уровне категории или пользователя. Команда `chgroup` позволяет изменять группу пользователей:

```bash
chgroup 2 user1 user2
```

```python
# Прямое API-взаимодействие
api.require_permission("db_admin")

async with api.db.transaction():
    for user in parsed_args.users:
        await api.execute(
            "UPDATE users SET group_id = ? WHERE username = ?",
            (group_id, user)
        )
```

```python
# Прямое взаимодействие с БД (низкоуровневый доступ)
db = api.db
async with db.transaction():
    cursor = await db.execute(
        "UPDATE users SET group_id = ? WHERE username = ?",
        (new_group_id, target_user)
    )
    await db.commit()
```

---

# 7. Работа с аргументами

## 7.1. Декларативный парсер: `build_parser`

**Новый подход в v3.0:** парсер объявляется отдельной функцией `build_parser(parser)`, которая регистрируется в `command`:

```python
def build_parser(parser):
    parser.description = command["help"]
    parser.add_argument("group_id", help="Group ID")
    parser.add_argument("users", nargs="+", help="One or more usernames")

command = {
    "name": "chgroup",
    "help": "Change group of one or more users",
    "func": execute,
    "build_parser": build_parser,  # <-- декларативная регистрация
}
```

Преимущества:

* парсер создаётся **один раз при загрузке команды**
* используется в `execute` и **LSP** (автодополнение, подсветка)
* чистое разделение: `build_parser` описывает CLI, `execute` — логику

---

## 7.2. Получение парсера в `execute`

Внутри `execute` используется:

```python
parser = api.parser("command_name", description=command["help"])
parsed_args = parser.parse_args(api.args)
```

Если команда зарегистрировала `build_parser`, `api.parser()` вернёт готовый сконфигурированный парсер.

---

## 7.3. Позиционные аргументы

```python
def build_parser(parser):
    parser.add_argument("group_id", help="Group ID")
    parser.add_argument("users", nargs="+", help="One or more usernames")
```

Пример: `chgroup 10 user1 user2`

Доступ:

```python
parsed_args.group_id   # "10"
parsed_args.users      # ["user1", "user2"]
```

---

## 7.4. Флаги (`store_true`)

```python
def build_parser(parser):
    parser.add_argument("-n", action="store_true", help="No trailing newline")
    parser.add_argument("-e", action="store_true", help="Enable escape sequences")
    parser.add_argument("-E", action="store_true", help="Disable escape sequences")
```

Пример: `echo -n hello`

```python
parsed_args.n == True
```

---

## 7.5. Опции со значением

```python
def build_parser(parser):
    parser.add_argument("--user", help="Target username")
```

Пример: `sshkey list --user admin`

```python
parsed_args.user  # "admin"
```

---

## 7.6. Короткие и длинные формы

```python
def build_parser(parser):
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
```

Поддерживается:

```bash
cmd -v
cmd --verbose
```

---

## 7.7. Группировка коротких флагов

```bash
cmd -abc
```

эквивалентно:

```bash
cmd -a -b -c
```

---

## 7.8. Типизация (`type=int` и др.)

```python
def build_parser(parser):
    parser.add_argument("--cpus", type=int, help="Number of CPUs")
```

Если значение некорректно:

```bash
cmd --cpus abc
```

→ будет `CommandArgumentError`

---

## 7.9. Обязательные аргументы

```python
def build_parser(parser):
    parser.add_argument("--user", required=True, help="Target username")
```

Если аргумент не передан — будет ошибка.

---

## 7.10. Ограничение значений (`choices`)

```python
def build_parser(parser):
    parser.add_argument("--mode", choices=["fast", "safe"], help="Operation mode")
```

```bash
cmd --mode fast
```

---

## 7.11. Несколько значений (`nargs`)

```python
def build_parser(parser):
    parser.add_argument("text", nargs="*", help="Text arguments")
    parser.add_argument("vars", nargs="+", help="Variables to unset")
    parser.add_argument("file", nargs="?", help="Optional file")
```

| nargs | описание |
|-------|----------|
| `?` | 0 или 1 значение |
| `*` | 0 или больше |
| `+` | 1 или больше |

---

## 7.12. Повторяемые аргументы (`append`)

```python
def build_parser(parser):
    parser.add_argument("--tag", action="append", help="Add tag")
```

```bash
cmd --tag a --tag b
```

```python
parsed_args.tag == ["a", "b"]
```

---

## 7.13. Счётчик (`count`)

```python
def build_parser(parser):
    parser.add_argument("-v", action="count", help="Verbosity level")
```

```bash
cmd -vvv
```

```python
parsed_args.v == 3
```

---

## 7.14. Подкоманды (`add_subparsers`)

Используются для сложных команд.

#### Пример (`sshkey`)

```python
def build_parser(parser):
    parser.description = command["help"]

    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    p_list = subparsers.add_parser("list", help="List SSH keys")
    p_list.add_argument("--user", help="Target username")

    p_add = subparsers.add_parser("add", help="Add SSH key")
    p_add.add_argument("key", help="SSH public key")
    p_add.add_argument("--user", help="Target username")

    p_del = subparsers.add_parser("delete", help="Delete SSH key")
    p_del.add_argument("index", help="Key index")
```

#### Использование

```bash
sshkey list
sshkey list --user admin
sshkey add AAAAB3...
sshkey delete 0
```

#### Обработка

```python
if parsed_args.subcommand == "list":
    ...
elif parsed_args.subcommand == "add":
    ...
elif parsed_args.subcommand == "delete":
    ...
```

---

## 7.15. Автоматическая справка

Каждый парсер поддерживает:

```bash
command -h
command --help
```

Вывод включает:

* usage
* описание
* список аргументов
* подкоманды

---

## 7.16. Обработка ошибок парсера

```python
try:
    parsed_args = parser.parse_args(api.args)
except CommandArgumentError as e:
    return f"Argument error: {e}\n"
```

При запросе справки (`-h` / `--help`) также выбрасывается `CommandArgumentError` с текстом help.

---

## 7.17. Ручной парсинг (альтернатива)

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

> **Примечание:** ручной парсинг не интегрируется с LSP (нет автодополнения для ручных аргументов).

---

# 8. Подсистема LSP: автодополнение и подсветка

В проект интегрирована подсистема LSP (Language Server Protocol), которая обеспечивает:

* автодополнение (autocomplete menu)
* inline hints (подсказки inline)
* syntax highlighting (подсветку синтаксиса)
* AST highlighting (семантическую подсветку)

## 8.1. Как LSP использует `build_parser`

LSP получает доступ к декларативному описанию CLI через `build_parser`:

```python
# Диспетчер передаёт парсер в CommandAPI при создании
parser = command.get("build_parser")
api = CommandAPI(username, args, parser=parser)
```

LSP использует этот парсер для:

* построения списка доступных опций
* автодополнения аргументов
* валидации введённого текста
* семантической подсветки

---

## 8.2. Lexer и токенизация

Встроенный lexer разбивает ввод пользователя на токены:

* команда
* опции (`-f`, `--flag`)
* значения
* строки

Токены передаются в LSP engine для анализа и подсветки.

---

## 8.3. Autocomplete (меню автодополнения)

При вводе команды пользователь видит меню автодополнения:

* список доступных команд
* опции для текущей команды
* подсказки по типам аргументов

Меню управляется стрелками (`↑` / `↓`) и подтверждается `Tab` или `Enter`.

---

## 8.4. Inline hints

В строке ввода отображаются подсказки:

* ожидаемые аргументы
* типы значений
* доступные опции

Hints обновляются динамически по мере ввода.

---

## 8.5. Syntax highlighting

Строка ввода подсвечивается синтаксически:

* команда — выделенный цвет
* опции — другой цвет
* значения — третий цвет
* ошибки — красный/подчёркивание

---

## 8.6. AST highlighting

Семантическая подсветка на уровне AST (Abstract Syntax Tree):

* распознаёт структуру команды
* подсвечивает согласно контексту
* оптимизировано: токены обрабатываются не по grapheme, а по syntax token

---

# 9. Работа с вводом и выводом (IO)

## 9.1. Возврат значения из команды

Функция `execute(...)` может:

* вернуть `str`
* вернуть `bytes`
* вернуть `None`

### Рекомендуемый стиль

* **простые команды** → `return "text\n"`
* **потоковый/интерактивный вывод** → `await api.write(...)`
* **PTY/полноэкранные команды** → через `api.run_interactive()` или `api.pty`

---

## 9.2. Методы вывода `CommandAPI`

### Базовые

| API вызов | Прямое взаимодействие |
|-----------|----------------------|
| `await api.write("Hello")` | `await api.terminal.output.output_str("Hello")` |
| `await api.writeln("Hello")` | `await api.write("Hello\n")` |
| `await api.write_line("Hello")` | псевдоним `writeln` |
| `await api.flush()` | `await api.terminal.output.flush()` (если есть) |
| `await api.clear()` | `await api.write(b"\x1b[2J\x1b[H")` |

### Цветные helper'ы

| API вызов | ANSI-коды |
|-----------|-----------|
| `await api.write_success("Done")` | `\x1b[32m` (зелёный) + сброс |
| `await api.write_error("Failed")` | `\x1b[31m` (красный) + сброс |
| `await api.write_warning("Warning")` | `\x1b[33m` (жёлтый) + сброс |

---

## 9.3. Прямой доступ к `Terminal`

Если нужен низкий уровень — терминал доступен напрямую:

```python
# Через API	erminal = api.terminal

# Прямое взаимодействие
await api.terminal.output.output_str("Привет\n")
line = await api.terminal.input.read_str()

# Через session (устаревший способ — не рекомендуется)
session = get_current_session()
terminal = session.extra["terminal"]
```

Но **для новых команд** предпочтительно сначала смотреть, есть ли уже helper в `CommandAPI`.

---

# 10. Интерактивный ввод

## 10.1. `read_line` — ввод строки

```python
# API
name = await api.read_line("Enter name: ")

# Прямое взаимодействие
await api.terminal.output.output_str("Enter name: ")
name = await api.terminal.input.read_str()
```

---

## 10.2. `read_line_secret` — скрытый ввод

```python
# API
secret = await api.read_line_secret("Enter token: ")

# Прямое взаимодействие
echo_was = api.terminal.input.editor.echo
api.terminal.input.editor.echo = False
try:
    secret = await api.terminal.input.read_str()
finally:
    api.terminal.input.editor.echo = echo_was
await api.terminal.output.output_str("\n")
```

---

## 10.3. `prompt` — псевдоним `read_line`

```python
# API
name = await api.prompt("Enter name: ")

# Эквивалентно
name = await api.read_line("Enter name: ")
```

---

## 10.4. `confirm` — подтверждение (выбрасывает `CommandAbort`)

```python
# API — выбрасывает CommandAbort при отказе
try:
    await api.confirm("Delete VM? [y/N]: ")
except CommandAbort:
    return "Cancelled.\n"

# Или с явной проверкой
try:
    if await api.confirm("Delete VM? [y/N]: "):
        await api.write_success("Deleted.")
except CommandAbort:
    return "Cancelled.\n"
```

> **Важное изменение:** `confirm()` теперь выбрасывает `CommandAbort` при отрицательном ответе, а не возвращает `False`. Это позволяет использовать `await api.confirm()` без явной проверки — отказ автоматически прервёт выполнение.

---

# 11. Работа с окружением (`UserEnvironment`)

## 11.1. Временные переменные сессии

Текущее окружение доступно через:

```python
# API
env = api.env

# Прямое взаимодействие
env = api.session.extra["env"]
```

Обычные сценарии:

| Операция | API | Прямое взаимодействие |
|----------|-----|----------------------|
| Установить | `api.env_set("PS1", "pve> ")` | `api.env.set("PS1", "pve> ")` |
| Получить | `api.env_get("USER")` | `api.env.get("USER")` |
| Удалить | `api.env_unset("TEMP_VAR")` | `api.env.unset("TEMP_VAR")` |
| Подстановка | `api.env_substitute("Hello $USER")` | `api.env.substitute("Hello $USER")` |

---

## 11.2. Постоянное сохранение в БД (`saved_env`)

Важно понимать:

> Изменения через `api.env` живут **только в текущей сессии**, если ты отдельно не сохранишь их в БД.

```python
# API
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

api.env_set("EDITOR", "nano")
return "EDITOR saved.\n"

# Прямое взаимодействие с БД
import json
db = api.db
row = await db.fetch_one("SELECT saved_env FROM users WHERE username = ?", (api.username,))
saved_env = json.loads(row[0] if row else "{}")
saved_env["EDITOR"] = "nano"
await db.execute("UPDATE users SET saved_env = ? WHERE username = ?",
                 (json.dumps(saved_env), api.username))
await db.commit()
```

---

# 12. Работа с историей команд (`api.history`)

История команд доступна через свойство `api.history`:

```python
# API — доступ к истории
history = api.history

# Все записи
for i, entry in enumerate(history.all()):
    await api.write(f"  {i+1:2}  {entry}\r\n")

# Сохранить в БД
await history.save()

# Очистить
await history.clear(store="all")    # all, runtime, db
```

Поле `history` в таблице `users` хранит JSON-массив строк:

```python
# Чтение истории
row = await api.fetch_one(
    "SELECT history FROM users WHERE username = ?",
    (api.username,)
)
(history_raw,) = row
history = json.loads(history_raw or "[]")

# Обновление истории
history.append("userinfo --all")
await api.execute(
    "UPDATE users SET history = ? WHERE username = ?",
    (json.dumps(history, ensure_ascii=False), api.username)
)
await api.db.commit()
```

---

# 13. Работа с PTY и интерактивными процессами

## 13.1. Быстрый способ: `api.run_interactive()`

```python
# API — полностью автоматизированный запуск
await api.run_interactive("/bin/bash")

# С параметрами
await api.run_interactive(
    cmd="/bin/bash",
    args=["-i"],
    cwd="/root",
    env=api.env.as_dict(),
    alt_screen=True   # по умолчанию True
)
```

`run_interactive()` делает автоматически:

* гарантирует наличие PTY (`pty.ensure()`)
* синхронизирует размер окна (`rows`, `cols`)
* собирает окружение процесса (`os.environ + api.env`)
* устанавливает `TERM`
* переключает в альтернативный экран (если `alt_screen=True`)
* запускает процесс
* подключает SSH ↔ PTY
* после завершения возвращает экран и очищает ресурсы в `finally`

---

## 13.2. Низкоуровневая работа через `api.pty`

```python
# API — низкоуровневый доступ
pty = api.pty

# Прямое взаимодействие через terminal
pty = api.terminal.pty

# Дальше — полный контроль
await pty.ensure()
await pty.resize(api.rows, api.cols)

proc = await pty.spawn(
    "/bin/bash",
    ["-i"],
    env=api.env.as_dict(),
    cwd="/root",
    attach_streams=False,
)

await pty.attach_streams()
await proc.wait()
```

---

## 13.3. Важно: `attach_streams()` блокирует выполнение

После вызова `attach_streams()` выполнение команды **останавливается**, пока интерактивный процесс не завершится:

```python
await api.pty.attach_streams()   # <-- блокируется здесь
return "Done\n"                   # <-- выполнится только после выхода
```

---

## 13.4. Завершение PTY и cleanup

```python
# API — run_interactive делает cleanup сам
await api.run_interactive("/bin/bash")  # cleanup в finally

# Ручной cleanup
try:
    await pty.attach_streams()
    await proc.wait()
finally:
    try:
        await pty.detach_streams()
    except Exception:
        pass
    await api.exit_alt_screen()
```

---

## 13.5. Полноэкранные команды и альтернативный экран

```python
# API
await api.enter_alt_screen()
try:
    await api.clear()
    await api.writeln("Interactive mode")
    await api.read_line("Press Enter to exit...")
finally:
    await api.exit_alt_screen()

# Прямое взаимодействие (ANSI-коды)
await api.write(b"\x1b[?1049h")   # enter alt screen
await api.write(b"\x1b[2J\x1b[H") # clear
try:
    ...
finally:
    await api.write(b"\x1b[?1049l") # exit alt screen
```

---

# 14. Работа с мышью

Доступ к мыши есть через:

```python
# API
mouse = api.mouse

# Прямое взаимодействие
mouse = api.terminal.input.mouse
```

| Операция | API | Прямое взаимодействие |
|----------|-----|----------------------|
| Включить | `await api.mouse_enable([1002, 1006])` | `await mouse.enable([1002, 1006])` |
| Выключить | `await api.mouse_disable()` | `await mouse.disable()` |

Режимы мыши:

* `1000` — базовые клики
* `1002` — drag/motion
* `1006` — SGR-формат (рекомендуется всегда)

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

> **Рекомендация:** если включаешь мышь — **всегда отключай её в `finally`**.

---

# 15. Альтернативный экран

| Операция | API | ANSI-код |
|----------|-----|----------|
| Включить | `await api.enter_alt_screen()` | `\x1b[?1049h` |
| Выключить | `await api.exit_alt_screen()` | `\x1b[?1049l` |

Пример TUI-команды:

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

---

# 16. Работа с базой данных

## 16.1. Доступ к БД

```python
# API (lazy property)
db = api.db

# Прямое взаимодействие (устаревший способ)
from helpers.globals import GlobalStore
db = GlobalStore.get().require("db")
```

---

## 16.2. Shortcut-методы через `api`

| API | Прямое взаимодействие | Описание |
|-----|----------------------|----------|
| `await api.fetch_one(q, p)` | `await api.db.fetch_one(q, p)` | Одна строка (tuple) или None |
| `await api.fetch_all(q, p)` | `await api.db.fetch_all(q, p)` | Список строк |
| `await api.fetch_val(q, p)` | `await api.db.fetch_val(q, p)` | Первое поле первой строки |
| `await api.execute(q, p)` | `await api.db.execute(q, p)` | INSERT/UPDATE/DELETE |

---

## 16.3. Что возвращают `fetch_one()` и `fetch_all()`

⚠️ **Важно:** строки из БД — это **кортежи (tuple)**, не dict.

```python
# Правильно — распаковка
row = await api.fetch_one("SELECT a, b FROM t WHERE id = ?", (1,))
if not row:
    return "Not found.\n"
a, b = row

# Неправильно — dict-интерфейс не работает
row["username"]   # ошибка!
row.items()       # ошибка!
```

---

## 16.4. Практические примеры SQL

### SELECT одной строки

```python
# API
row = await api.fetch_one(
    "SELECT group_id, created_at FROM users WHERE username = ?",
    (api.username,)
)

# Прямое взаимодействие
cursor = await api.db.execute(
    "SELECT group_id, created_at FROM users WHERE username = ?",
    (api.username,)
)
row = await cursor.fetchone()
```

### SELECT нескольких строк

```python
# API
rows = await api.fetch_all("SELECT username, group_id FROM users ORDER BY username")
for username, group_id in rows:
    await api.writeln(f"{username}: group={group_id}")

# Прямое взаимодействие
cursor = await api.db.execute("SELECT username, group_id FROM users ORDER BY username")
rows = await cursor.fetchall()
```

### UPDATE / INSERT

```python
# API
await api.execute(
    "UPDATE users SET group_id = ? WHERE username = ?",
    (2, "alice")
)
await api.db.commit()

# Прямое взаимодействие
cursor = await api.db.execute(
    "UPDATE users SET group_id = ? WHERE username = ?",
    (2, "alice")
)
await api.db.commit()
```

---

## 16.5. Транзакции и обработка ошибок

```python
# API — через async context manager
try:
    async with api.db.transaction():
        await api.execute("UPDATE users SET group_id = ? WHERE username = ?", (2, "alice"))
        await api.execute("UPDATE users SET group_id = ? WHERE username = ?", (2, "bob"))
    return "Updated.\n"
except Exception as e:
    api.logger.exception("Failed to update groups")
    return f"Database error: {e}\n"

# Прямое взаимодействие
try:
    async with api.db.transaction():
        cursor = await api.db.execute("UPDATE users ...")
        cursor = await api.db.execute("UPDATE users ...")
    await api.db.commit()
except Exception as e:
    api.logger.exception("Failed")
    return f"Error: {e}\n"
```

### Практические правила

* одна запись → `execute()` + `commit()`
* несколько связанных записей → `async with db.transaction():`
* любые ошибки → логировать через `api.logger`
* не делать предположений о типе row без проверки

---

# 17. Работа с JSON-полями в таблице `users`

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

Несколько полей хранятся как JSON в `TEXT`.

---

## 17.1. `ssh_keys`

```python
# API
row = await api.fetch_one("SELECT ssh_keys FROM users WHERE username = ?", (api.username,))
(ssh_keys_raw,) = row
ssh_keys = json.loads(ssh_keys_raw or "[]")

# Добавление ключа
ssh_keys.append("ssh-ed25519 AAAA... newkey")
await api.execute(
    "UPDATE users SET ssh_keys = ? WHERE username = ?",
    (json.dumps(ssh_keys, ensure_ascii=False), api.username)
)
await api.db.commit()

# Прямое взаимодействие
cursor = await api.db.execute("SELECT ssh_keys FROM users WHERE username = ?", (api.username,))
row = await cursor.fetchone()
ssh_keys = json.loads(row[0] or "[]")
```

---

## 17.2. `saved_env`

```python
# API
row = await api.fetch_one("SELECT saved_env FROM users WHERE username = ?", (api.username,))
(saved_env_raw,) = row
saved_env = json.loads(saved_env_raw or "{}")
saved_env["EDITOR"] = "nano"

await api.execute(
    "UPDATE users SET saved_env = ? WHERE username = ?",
    (json.dumps(saved_env, ensure_ascii=False), api.username)
)
await api.db.commit()

# Одновременно обновить сессионное окружение
api.env_set("EDITOR", "nano")
```

---

## 17.3. `history`

```python
# API — через api.history
history = api.history
for i, entry in enumerate(history.all()):
    await api.write(f"  {i+1:2}  {entry}\r\n")

# Ручная работа с JSON-полем
row = await api.fetch_one("SELECT history FROM users WHERE username = ?", (api.username,))
(history_raw,) = row
history = json.loads(history_raw or "[]")

# Добавление записи
history.append("userinfo --all")
await api.execute(
    "UPDATE users SET history = ? WHERE username = ?",
    (json.dumps(history, ensure_ascii=False), api.username)
)
await api.db.commit()
```

---

# 18. `api.user` и `UserContext`

```python
# API — ленивое создание
user = api.user

# Доступные методы (UserContext)
user.get_field(field, default)      # получить сырое значение поля
user.set_field(field, value)        # установить значение поля
user.get_json(field, default)       # получить JSON-данные
user.set_json(field, data)          # сохранить JSON

# Шорткаты
user.get_ssh_keys()
user.set_ssh_keys(keys)
user.get_history()
user.set_history(history)
```

> **Примечание:** `UserContext` находится в разработке. Некоторые методы ещё не полностью реализованы. В текущей версии рекомендуется использовать прямые SQL-запросы через `api.fetch_one` / `api.execute`.

---

# 19. Криптография

```python
# API
encrypted = api.encrypt("secret")       # шифрование AES-GCM
decrypted = api.decrypt(encrypted)      # расшифровка

# Алиасы для явного контекста БД
api.db_encrypt(value)
api.db_decrypt(value)

# Прямое взаимодействие
from helpers.crypto import encrypt, decrypt
encrypted = encrypt("secret")
decrypted = decrypt(encrypted)
```

### Пример использования в БД

```python
# API
encrypted_secret = api.encrypt(api_secret)
await api.execute(
    "UPDATE users SET api_secret = ? WHERE username = ?",
    (encrypted_secret, api.username)
)
await api.db.commit()

# При чтении
row = await api.fetch_one("SELECT api_secret FROM users WHERE username = ?", (api.username,))
if row:
    secret = api.decrypt(row[0])
```

---

# 20. Глобальные сервисы и `GlobalStore`

`CommandAPI` использует `GlobalStore` внутри себя. Через `api` уже доступны:

* `api.db`
* `api.user`
* `api.terminal`
* `api.env`
* `api.permissions`
* `api.config`
* `api.history`

В случае крайней необходимости:

```python
# API
store = api.global_store()
pve = store.require("pve_client")

# Прямое взаимодействие (устаревший способ)
from helpers.globals import GlobalStore
store = GlobalStore.get()
pve = store.require("pve_client")
```

> **Команды не должны напрямую использовать `GlobalStore`, если нужный сервис уже доступен через `api`.**

---

# 21. Исключения команд

| Исключение | Когда использовать |
|------------|-------------------|
| `CommandError` | Базовый класс для всех ошибок команд |
| `CommandPermissionError` | Недостаточно прав (`api.require_permission`) |
| `CommandArgumentError` | Ошибка разбора аргументов (парсер) |
| `CommandAbort` | Операция отменена пользователем (`confirm` отказ) |
| `CommandNotFoundError` | Команда не найдена (внутреннее) |
| `CommandRuntimeError` | Ошибка выполнения (PTY, DB, сеть) |

```python
from sshserver.commandapi import (
    CommandAPI,
    CommandError,
    CommandPermissionError,
    CommandArgumentError,
    CommandAbort,
)

# Проверка прав
api.require_permission("db_admin")  # CommandPermissionError если нет

# Ошибка аргументов
raise CommandArgumentError("Unknown argument: --foo")

# Отмена пользователем
if not await api.confirm("Continue? [y/N]: "):
    raise CommandAbort("Cancelled by user")
```

---

# 22. Логирование

```python
# API — готовый логгер
api.logger.info("User opened shell")
api.logger.warning("Unknown option passed")
api.logger.exception("Database update failed")

# Прямое создание
import logging
logger = logging.getLogger(f"cmd.{api.username}")
```

### Что логировать

* изменение прав/групп
* обновление SSH-ключей
* интерактивные shell/PTY-сессии
* ошибки SQL
* административные действия

---

# 23. Размеры терминала

| Свойство | Описание |
|----------|----------|
| `api.rows` | Высота в строках |
| `api.cols` | Ширина в символах |
| `api.pixheight` | Высота в пикселях |
| `api.pixwidth` | Ширина в пикселях |

```python
# API
await api.pty.resize(api.rows, api.cols, api.pixwidth, api.pixheight)

# Прямое взаимодействие
term_size = api.session.term_size  # (cols, rows, pixwidth, pixheight)
await api.pty.resize(api.session.term_height, api.session.term_width,
                     api.session.term_pixwidth, api.session.term_pixheight)
```

Размеры обновляются автоматически при изменении окна SSH-клиента.

---

# 24. Система ввода: Line Editor

## 24.1. Input scroll (прокрутка ввода)

Реализована прокрутка ввода при длинных многострочных строках:

* `_scroll_offset` — смещение viewport (0 = layout row 0 прижат к верху)
* Автоматическая прокрутка при перемещении курсора за пределы экрана
* Корректная отрисовка при scroll > 0
* Поддержка многострочного ввода с переносом

---

## 24.2. Управление курсором

Система отслеживает позицию курсора:

* `_cursor_abs` — абсолютная позиция (row, col), 1-based
* `_anchor_row` — строка терминала где начинается layout row=0
* `_layout_anchor_row` — отслеживание позиции layout row=0

Режимы рендеринга:

* **absolute diff mode** — когда `_cursor_abs` заполнен
* **relative mode** — когда позиция неизвестна (как readline)

Оптимизации:

* diff-рендеринг (перерисовка только изменённых участков)
* anchor_row не выводится из cursor_pos (исправлен баг)
* Корректная обработка многострочного wrap

---

# 25. Keybind layer (слой горячих клавиш)

Инициализирован слой обработки горячих клавиш:

* Базовая инфраструктура для keybind-обработчиков
* Подготовка к расширяемым сочетаниям клавиш
* Интеграция с line editor

> **Статус:** базовый слой инициализирован, конкретные биндинги в разработке.

---

# 26. Тестирование и локальная отладка

### 1. Запусти сервер

```bash
python main.py
# или с uvloop
python main.py  # uvloop подключается автоматически
```

### 2. Подключись по SSH

```bash
ssh user@host -p <port>
```

### 3. Вызови команду

Проверь:

* корректный вывод
* help (`-h` / `--help`)
* ошибки парсера
* права
* интерактивный ввод
* автодополнение (Tab)
* подсветку синтаксиса

### 4. Смотри логи сервера

Особенно полезно:

* stack trace ошибок
* SQL-ошибки
* ошибки PTY
* ошибки парсинга
* LSP-логи

### 5. Отладка команд

```python
# Временное логирование
api.logger.debug(f"Args: {api.args}")
api.logger.debug(f"Parsed: {parsed_args}")

# Тестовые команды
async def execute(api: CommandAPI) -> str | None:
    api.logger.info(f"User: {api.username}, Perms: {api.permissions}")
    return f"Debug: {api.args}\n"
```

---

# 27. Лучшие практики

1. **Новые команды пишите через `CommandAPI` с `build_parser`.**
   Не используйте старый стиль. `build_parser` нужен для LSP.

2. **Не тяните `get_current_session()` и `GlobalStore` напрямую.**
   Всё основное уже есть в `api`.

3. **Не используйте обычный `argparse`.**
   Встроенный `ArgumentParser` интегрирован с LSP.

4. **Не полагайтесь на `dict`-строки из БД.**
   Считайте, что SQL-строка — это `tuple`.

5. **Все JSON-поля явно сериализуйте/десериализуйте.**
   `json.loads(raw or "[]")` / `json.dumps(data, ensure_ascii=False)`.

6. **Интерактивные режимы всегда оборачивайте в `try/finally`.**
   Особенно: альтернативный экран, мышь, PTY.

7. **Для проверки прав используйте `api.require_permission()`.**

8. **Для простых команд возвращайте строку.**
   Для потокового вывода — `await api.write(...)`.

9. **Изменения `api.env` не постоянны сами по себе.**
   Для персистентности обновляйте `saved_env` в БД.

10. **Логируйте административные действия.**
    Особенно всё, что меняет состояние системы или пользователей.

11. **Всегда включайте `build_parser` в `command`.**
    Это нужно для автодополнения и подсветки.

12. **Используйте `api.run_interactive()` вместо ручного PTY.**
    Если нужен полный контроль — используйте `api.pty`.

---

# 28. Полные примеры команд

## 28.1. Простая команда

```python
from sshserver.commandapi import CommandAPI

def build_parser(parser):
    parser.description = command["help"]

async def execute(api: CommandAPI) -> str | None:
    return f"Hello, {api.username}!\n"

command = {
    "name": "hello",
    "help": "Say hello",
    "func": execute,
    "build_parser": build_parser,
}
```

---

## 28.2. Команда с `build_parser` и подкомандами

```python
import json
from sshserver.commandapi import CommandAPI, CommandPermissionError

def build_parser(parser):
    parser.description = command["help"]

    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    p_list = subparsers.add_parser("list", help="List SSH keys")
    p_list.add_argument("--user", help="Target username")

    p_add = subparsers.add_parser("add", help="Add SSH key")
    p_add.add_argument("key", help="SSH public key")

async def execute(api: CommandAPI) -> str | None:
    parser = api.parser("sshkey", description=command["help"])
    parsed_args = parser.parse_args(api.args)

    target_user = parsed_args.user or api.username

    if target_user != api.username and not api.has_permission("db_admin"):
        raise CommandPermissionError("db_admin required")

    row = await api.fetch_one(
        "SELECT ssh_keys FROM users WHERE username = ?",
        (target_user,)
    )
    ssh_keys = json.loads(row[0] or "[]") if row else []

    if parsed_args.subcommand == "list":
        if not ssh_keys:
            return f"No SSH keys for {target_user}.\n"
        lines = [f"SSH keys for {target_user}:"]
        for i, key in enumerate(ssh_keys):
            short = key[:80] + "..." if len(key) > 80 else key
            lines.append(f"{i}: {short}")
        return "\n".join(lines) + "\n"

    elif parsed_args.subcommand == "add":
        ssh_keys.append(parsed_args.key)
        await api.execute(
            "UPDATE users SET ssh_keys = ? WHERE username = ?",
            (json.dumps(ssh_keys, ensure_ascii=False), target_user)
        )
        await api.db.commit()
        return f"SSH key added for {target_user}.\n"

command = {
    "name": "sshkey",
    "help": "Manage SSH keys",
    "func": execute,
    "build_parser": build_parser,
}
```

---

## 28.3. Команда с правами и БД

```python
import json
from sshserver.commandapi import CommandAPI

def build_parser(parser):
    parser.description = command["help"]
    parser.add_argument("-a", "--all", action="store_true", help="Show all fields")

async def execute(api: CommandAPI) -> str | None:
    api.require_permission("db_viewer")

    parser = api.parser("userinfo", description=command["help"])
    parsed_args = parser.parse_args(api.args)

    row = await api.fetch_one(
        "SELECT username, group_id, created_at, ssh_keys, saved_env, history "
        "FROM users WHERE username = ?",
        (api.username,)
    )

    if not row:
        return f"User {api.username} not found.\n"

    db_username, group_id, created_at, ssh_keys_raw, saved_env_raw, history_raw = row

    if parsed_args.all:
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

    return f"Username: {db_username}\nGroup ID: {group_id}\nCreated at: {created_at}\n"

command = {
    "name": "userinfo",
    "help": "Show information about current user",
    "func": execute,
    "permissions": ["db_viewer"],
    "build_parser": build_parser,
}
```

---

## 28.4. Интерактивная команда подтверждения

```python
from sshserver.commandapi import CommandAPI, CommandAbort

def build_parser(parser):
    parser.description = command["help"]

async def execute(api: CommandAPI) -> str | None:
    try:
        await api.confirm("Delete temp data? [y/N]: ")
        await api.write_success("Deleted.")
    except CommandAbort:
        return "Cancelled by user.\n"
    return None

command = {
    "name": "confirmtest",
    "help": "Test confirmation flow",
    "func": execute,
    "build_parser": build_parser,
}
```

---

## 28.5. Интерактивный shell через `run_interactive()`

```python
from sshserver.commandapi import CommandAPI

def build_parser(parser):
    parser.description = command["help"]

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
    "help": "Open interactive shell (auto PTY)",
    "func": execute,
    "permissions": ["system_permission", "admin_permission"],
    "build_parser": build_parser,
}
```

---

## 28.6. Интерактивный shell через низкоуровневый PTY

```python
import asyncio
import os
import fcntl
import termios
from sshserver.commandapi import CommandAPI

def _setup_pty(slave_fd: int):
    """Make slave fd the controlling terminal in the child."""
    os.setsid()
    fcntl.ioctl(slave_fd, termios.TIOCSCTTY, 0)

def build_parser(parser):
    parser.description = command["help"]

async def execute(api: CommandAPI) -> None:
    env = api.env
    terminal = api.terminal
    pty = terminal.pty

    await pty.ensure()
    slave_fd = pty.get_slave_fd()

    # Собираем окружение
    process_env = os.environ.copy()
    process_env.setdefault("TERM", env.get("TERM", "xterm-256color"))

    # Получаем размеры окна
    cols, rows, pixwidth, pixheight = (
        api.cols, api.rows, api.pixwidth, api.pixheight
    )

    # Синхронизируем размер
    await pty.resize(rows, cols, pixwidth, pixheight)
    await api.write("\r\n")

    # Подключаем потоки
    await pty.attach_streams()

    # Запускаем процесс
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
    "help": "Start bash with manual PTY setup",
    "func": execute,
    "permissions": ["system_permission"],
    "build_parser": build_parser,
}
```
