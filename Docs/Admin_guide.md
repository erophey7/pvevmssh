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

- дополнительно можно установить `liboqs` из исходников, нужно это что бы работал `Post quantum kex algorithm` (в общем для повышения безопасности в процессе обмена ключами)

## сборка liboqs из исходников
### зависимости
ubuntu: `sudo apt install build-essential astyle cmake gcc ninja-build libssl-dev unzip xsltproc doxygen graphviz valgrind`

arch: `sudo pacman -Syu base-devel astyle cmake ninja openssl unzip libxslt doxygen graphviz valgrind`

venv: `pip install pytest pytest-xdist pyyaml`

### установка
- что бы не засорять систему, лучше проводить все действия в .data и использовать отдельный venv для сборки

- в качестве бранча нужно использовать тег последнего релиза, на 09.04.2026 это `0.15.0`
```bash
# из корневой директории установки
mkdir -p .data/build_liboqs
cd .data/build_liboqs
# тут нужно установить зависимости в соответствии со cвоей системой
python -m venv build_venv
source build_venv/bin/activate
pip install pytest pytest-xdist pyyaml
git clone https://github.com/open-quantum-safe/liboqs -b 0.15.0
cd liboqs
mkdir build && cd build
cmake -GNinja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX=../../../liboqs \
  -DBUILD_SHARED_LIBS=ON \
  ..
ninja -j $(nproc --all)
# можно протестить либу с помощью ninja run_tests, падение по tests/test_code_conventions.py::test_style на работу не повлияет
mkdir ../../../liboqs
ninja install
cd ../../..
rm -rf build_liboqs
```
- так же на будующее, можно сразу приписать директорию `.data/liboqs/lib` в `LD_LIBRARY_PATH`, но это не обязательно

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
* `liboqs_custom_prefix`    - включение `liboqs_prefix` (если вы устанавливали liboqs по предоставленной инструкции, то это нужно включить)
* `liboqs_prefix`           - префикс установки liboqs (если он не в системных путях)

### logger
* `level`                   - уровень логирования, может быть установлен `DEBUG` `INFO` `WARNING` `ERROR`
* `log_files`               - включение/отключение логирования в файлы
* `log_dir`                 - папка для логов

### db
* `type`                    - тип бд (sqlite, mariadb, mysql(алиас на mariadb))
* `masterkey_file`          - мастер ключ шифрующий api_scret
* `limits`                  - лимиты для полей

sqlite only
* `file`                    - файл sqlite бд

mariadb only
* `host`                    - ip сервера
* `user`                    - пользователь бд
* `password`                - пароль
* `databse`                 - название бд
* `port`                    - порт сервера

#### limits
на текущий момент имеет
* `env`                     - ограничение для saved_env в колличестве записей
* `history`                 - ограничение для history в колличестве записей

### auth
* `ssh_key_enabled`         - включена ли аутентификация по ключу
* `password_enable`         - включена ли аутентификация по токену
* `default_group`           - дефолтная группа для новых пользователей
* `force_group`             - список пользователей перезаписываемой группой в формате `{"username": groupid}`
* `limited_inheritance`     - ограниечение наследования прав пользователей, без этого группа может получать вложенные права вложенных групп 

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