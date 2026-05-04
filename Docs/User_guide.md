# Гайд для пользователя

# Использование комманд
Данный проект реализует свою систему комманд

для просмотра списка комманд можно использовать `help`

для того что бы написать свою комманду, можно ознакомится с [new api doc](new_command_api.md) и [api doc](command_api.md)

## список стандартных комманд

на данный момент реализован следующий список комманд для пользователя

* `about`                   - информация о терминале, системе, проекте
* `echo`                    - вывод текста
* `env`                     - управление env
* `export`                  - установка env
* `history`                 - управление историей комманд
* `whoami`                  - просмотр имени пользователя
* `sshkey`                  - управление ключами

так же присутствует такой список комманд требующие повышыные привелегии

db_admin

* `chgroup`                 - смена группы пользователю

db_viewer

* `userinfo`                - просмотр информации о пользователе в бд
* `userlist`                - просиотр списка пользователей в бд

tester_permission

* `char`                    - вывод Unicode символов
* `color`                   - вывод разноцветного текста
* `mouse`                   - дебаг мышки
* `termecho`                - управление `Terminal echo`
* `sessioninfo`             - runtime значения в SessionInfo dataclass
* `termecho`                - управление echo терминала

system_permission or admin_permission

* `bash`                    - вход в bash оболочку

---

# подключение к серверу
по большей части подключение к данному серверу схоже с подключением к обычному ssh серверу, но есть небольшие различия

## Аутентификация
всего есть 2 режима аутентификации - это: 
* api based 
* key based

### api based
основывается на механизме **ssh password аутентификации**.

но вместо имени пользователя и пароля используется **token_id** и **token_secret**
#### пример входа
> **Windows**
> ```bash
> ssh user1@pve!pvevmssh@host -p 22222
> Password: token_secret
> ```

> **Linux**
> ```bash
> ssh 'user1@pve!pvevmssh'@host -p 22222
> Password: token_secret
> ```

### key based
Основывается на **ssh public key**
- для того что бы использовать этот тип аутентификации необходимо сначала добавить публичную часть ключевой пары путём выполнения комманды **sshkey**

---

# Enviromnent
Для работы с env есть следующие команды
* `env`                     - просмотр, отчистка, сохранение в бд
* `export`                  - export переменной
## комманды
### env

Имеет флаги
* `-h` `--help`             - help окно
* `-f` `--flush` [`all`,`db`,`runtime`] - Служит для отчистки переменных
* `-s` `--save`             - Служит для сохранения текущего состояния в бд

### export
минимальный linux аналог

## служебные переменные
### PS1
Служит для настройки промпта.
- По умолчанию устанавливается в `\e[1;92m>>> \e[0m`, Может быть переопределено

> Поддерживает как `\e` ansi так и `[\e`

> Имеет стандартные для PS1 сокращения
> * `\u`                    - `$USERNAME`
> * `\h`                    - `$HOSTNAME.partition(".")[0]`
> * `\H`                    - `$HOSTNAME`

### HOSTNAME
Служит для комманд и PS1
* устанавливается в конфиге и не предполагается что будет переопределение

### USER
Служит для комманд и PS1
* устанавливается в процессе инита сессии и не предполагается что будет переопределение

### TERM
Служит для определения типа терминала

### HELLOMSG
Устанавливает приветственное сообщение


---

#  Стили и оформление терминала

Терминал позволяет полностью настраивать внешний вид через переменные окружения (`env`).

---

##  Режим отображения цветов

Переменная:

```bash
STYLE_COLOR_MODE
```

Определяет, как терминал будет отображать цвета.

### Поддерживаемые значения:

* `truecolor` / `24bit` — полный 24-bit цвет (рекомендуется)
* `256` / `256color` — 256 цветов
* `16` / `basic` — базовая палитра (совместимость)
* `auto` — автоматический выбор

#### Пример:

```bash
export STYLE_COLOR_MODE=truecolor
```

---

## Переопределение стандартных стилей

Любой встроенный стиль можно изменить через `STYLE_...`.

### Формат:

```
STYLE_<NAME>=<VALUE>
```

---

### Примеры встроенных стилей:

```bash
STYLE_SYNTAX_COMMAND
STYLE_SYNTAX_OPTION
STYLE_SYNTAX_STRING
STYLE_SYNTAX_NUMBER
STYLE_SYNTAX_DEFAULT
STYLE_SYNTAX_WS

STYLE_COMPLETION
STYLE_COMPLETION_SELECTED
STYLE_INLINE_HINT
```

---

### Пример использования:

```bash
export STYLE_SYNTAX_COMMAND=BLUE
export STYLE_SYNTAX_STRING=#00FFAA
export STYLE_SYNTAX_NUMBER=YELLOW
```

---

## Пользовательские стили

Вы можете создавать собственные стили:

```bash
export STYLE_MY_COLOR=RED
export STYLE_ERROR=#FF0000
export STYLE_HIGHLIGHT=CYAN
```

---

###  Использование пользовательских стилей

Пользовательские стили можно:

* использовать в командах (если поддерживается командой)
* использовать в UI элементах
* переиспользовать через ссылку

#### Пример переиспользования:

```bash
export STYLE_PRIMARY=#1F4E77
export STYLE_COMMAND=PRIMARY
```

---

## Поддерживаемые форматы значений

### 1. Имена цветов

```
BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE
```

---

### 2. HEX цвета

```
#RRGGBB
#RGB
```

Пример:

```bash
export STYLE_ERROR=#FF0033
```

---

### 3. ANSI escape (для продвинутых)

```bash
export STYLE_WARNING=\x1b[1;33m
```

---

##  Обновление настроек

Изменения применяются:

* автоматически при старте новой сессии
* или через обновление окружения через export

---

## Важно

* пользовательские стили имеют приоритет над встроенными
* ссылки между стилями поддерживаются:

```bash
STYLE_A=RED
STYLE_B=A
STYLE_C=B
```

---

## Синтаксис подсветки (что можно кастомизировать)

Подсветка команд поддерживает следующие категории:

| Стиль                   | Описание               |
| ----------------------- | ---------------------- |
| STYLE_SYNTAX_COMMAND    | команды                |
| STYLE_SYNTAX_SUBCOMMAND | субкомманды            |
| STYLE_SYNTAX_OPTION     | флаги (`-h`, `--help`) |
| STYLE_SYNTAX_STRING     | строки                 |
| STYLE_SYNTAX_NUMBER     | числа                  |
| STYLE_SYNTAX_PATH       | пути                   |
| STYLE_SYNTAX_ENV        | `$VAR`                 |
| STYLE_SYNTAX_FLAG       | параметры              |
| STYLE_SYNTAX_KEY        | ключи `key=value`      |
| STYLE_SYNTAX_VALUE      | значение после `=`     |
| STYLE_SYNTAX_OPERATOR   | `=`, `>`, `<`          |
| STYLE_SYNTAX_COMMENT    | комментарии            |
| STYLE_SYNTAX_BOOL       | true / false           |
| STYLE_SYNTAX_NULL       | null / none            |


---

## Пример полной кастомизации

```bash
export STYLE_COLOR_MODE=truecolor

export STYLE_SYNTAX_COMMAND=#4E9F3D
export STYLE_SYNTAX_STRING=#00D1FF
export STYLE_SYNTAX_NUMBER=#FFD166
export STYLE_SYNTAX_OPTION=#FFB703

export STYLE_PRIMARY=#1F4E77
export STYLE_ERROR=PRIMARY
```

---


