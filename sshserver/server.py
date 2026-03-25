"""
Запуск SSH-сервера: аутентификация и создание сессий.
"""

import asyncssh
import logging
from typing import Optional

from helpers.globals import GlobalStore
from helpers.path import Paths
from sshserver.handlers import handle_client

logger = logging.getLogger(__name__)


class PVESSHServer(asyncssh.SSHServer):
    """
    Класс-обработчик аутентификации и запросов на создание сессий.
    """

    def __init__(self) -> None:
        self._conn: Optional[asyncssh.SSHServerConnection] = None

    def connection_made(self, conn: asyncssh.SSHServerConnection) -> None:
        """Вызывается при установке SSH-соединения."""
        self._conn = conn
        logger.debug("Connection made")

    def connection_lost(self, exc: Optional[Exception]) -> None:
        """Вызывается при разрыве соединения."""
        logger.debug("Connection lost: %s", exc)

    def begin_auth(self, username: str) -> bool:
        """Начало аутентификации: возвращаем True, чтобы разрешить продолжение."""
        logger.debug("begin_auth called for %s", username)
        return True

    def password_auth_supported(self) -> bool:
        """Сообщаем, что поддерживаем аутентификацию по паролю."""
        return True

    def validate_password(self, username: str, password: str) -> bool:
        """
        Синхронная проверка пароля.
        Временно разрешаем все пароли.
        В будущем: проверка через API Proxmox.
        """
        logger.debug("validate_password called for %s", username)
        return True  # TODO: реальная аутентификация


class SSHServerRunner:
    """Запускает SSH-сервер и ожидает подключения."""

    def __init__(self) -> None:
        # Получаем конфигурацию из глобального хранилища
        config = GlobalStore.get().require("config")
        self.bind = config.get("ssh.bind", "0.0.0.0:22222")
        self.host_key = config.get("ssh.host_key", str(Paths.SSH_HOST_KEY))

    async def start(self) -> None:
        """Запускает сервер и ждёт его завершения."""
        host, port = self.bind.split(":")
        port = int(port)

        server = await asyncssh.create_server(
            PVESSHServer,
            host,
            port,
            server_host_keys=[self.host_key],
            process_factory=handle_client,
        )

        logger.info("SSH server listening on %s", self.bind)
        await server.wait_closed()