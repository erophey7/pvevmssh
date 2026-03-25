#!/usr/bin/env python3
"""
Точка входа в SSH-сервер для управления VM через Proxmox.
"""

import asyncio
import sys
import logging

from helpers.path import Paths
from helpers.config import Config
from helpers.globals import GlobalStore
from sshserver.server import SSHServerRunner


def setup_logging(level: str = "DEBUG") -> None:
    """Настройка корневого логгера."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.DEBUG),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


async def main() -> int:
    """
    Основная асинхронная функция.
    Инициализирует глобальные объекты, загружает конфиг и запускает сервер.
    """
    # Создание необходимых директорий и host-ключа
    Paths.init()
    Paths.ensure_ssh_host_key()

    # Загрузка конфигурации
    config = Config()
    setup_logging(config.get("logger.level", "DEBUG"))

    # Инициализация глобального хранилища
    g = GlobalStore()
    g.set("config", config)

    # Запуск сервера
    runner = SSHServerRunner()
    try:
        await runner.start()
    except KeyboardInterrupt:
        logging.info("Shutting down...")
    except Exception as e:
        logging.exception("Server error")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))