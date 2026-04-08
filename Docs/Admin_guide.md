# ATTENTION
на данный момент проект не предполагает применение в проде.


# Установка
- В будующем планируется install/update скрипт

## Зависимости
- Python 3.14+

## рекомендуемые пути
- `/opt`

## Python
рекомендуется использование venv

## примерный путь установки
```bash
git clone https://github.com/erophey7/pvevmssh.git
cd pvevmssh
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

# запуск
```bash
cd pvevmssh
source venv/bin/activate
python main.py    # или ./main.py
```


# Config
конфиг представляет собой json файл по пути `.data/config.json`

конфиг по умолчанию создаётся при первом запуске

## настройка
конфиг разделён на разделы
* `ssh`                     - парамерты ssh сервера
* `logger`                  - настройка логгера
* `db`                      - настройки бд (хоть и mysql предусмотрен, но он не тестировался)
* `auth`                    - параметры аутентификации
* `pve`                     - конфиг pve api и нод (в будующем)
* `env`                     - некоторые предустанавливаеме переменные окружения
* `groups`                  - группы

далее по разделам
### ssh
* `bind`                    - listen
* `host_key`                - отпечаток сервера

### logger
* `level`                   - уровень логирования, может быть установлен `DEBUG` `INFO` `WARNING` `ERROR`
* `log_files`               - включение/отключение логирования в файлы
* `log_dir`                 - папка для логов

### db
* `type`                    - тип бд (sqlite, mariadb, mysql(алиас на mariadb))
* `masterkey_file`          - мастер ключ шифрующий api_scret
* `limits`                  - лимиты для полей

sqlite only
* `file`                    - файл бд

mariadb only
* `host`                    - ip сервера
* `user`                    - пользователь бд
* `password`                - пароль
* `databse`                 - название бд
* `port`                    - порт сервера

#### limits
на текущий момент имеет
* `env`                     - ограничение для saved_env
* `history`                 - ограничение для history

### auth
* `ssh_key_enabled`         - включена ли аутентификация по ключу
* `password_enable`         - включена ли аутентификация по токену
* `default_group`           - дефолтная группа для новых пользователей
* `force_group`             - список пользователей перезаписываемой группой в формате `{"username": groupid}`
* `limited_inheritance`     - ограниечение наследования прав пользователей

### pve
* `main_node_host`          - URL главной ноды кластера
* `ssl_verity`              - проверка SSL
* `timeout`                 - timeout запроса

### groups
содержит в себе список групп

#### **пример группы**
```json
"0": {
    "name": "Administrator",
    "permissions": ["admin_permission"],
    "permset": [1,2,3]
}
```
* `"0"`                     - id группы
* `name`                    - имя группы
* `permissions`             - список прав группы
* `permset`                 - вложенные права от других групп


# Permissions & Groups

## права

### Список прав
по умолчанию представлен список прав:
Административные права
* `admin_permission`        - дефолтное право администратора
* `db_admin`                - право администратора бд (доступ к изменению других пользователей, просмотру серктов)

Расширеные пользовательские права
* `poweruser_permission`    - дефолтное право пользователя с расширкнными прави
* `db_viewer`               - право инспектора бд (просмотр всех записей, кроме секретов)
* `system_permission`       - право на доступ к системным ресурсам

Права обычного пользователя
* `user_permission`         - дефолтное право пользователя

парва тестировщика
* `tester_permission`       - дефолтное право тестировщика