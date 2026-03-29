#!/usr/bin/env python3
import asyncio
import sys
import logging

from helpers.path import Paths
from helpers.config import Config
from helpers.globals import GlobalStore
from sshserver.server import SSHServerRunner


########## Logging Setup ##########
def setup_logging(level: str = "DEBUG") -> None:
    """Configure root logger with specified log level and format."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.DEBUG),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


########## Main Entry Point ##########
async def main() -> int:
    """
    Bootstrap the server: create directories, load config, start SSH.
    """
    Paths.init()
    Paths.ensure_ssh_host_key()

    config = Config()
    setup_logging(config.get("logger.level", "DEBUG"))

    g = GlobalStore()
    g.set("config", config)

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