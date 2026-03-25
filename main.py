#!/usr/bin/env python3
import asyncio
import sys
import logging

from helpers.path import Paths
from helpers.config import Config
from helpers.globals import GlobalStore
from sshserver.server import SSHServerRunner


############ Setup Logging Configuration ############
def setup_logging(level: str = "DEBUG") -> None:
    """Configure root logger with specified log level and format."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.DEBUG),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


############ Main Async Function ############
async def main() -> int:
    """
    ########## Main Asynchronous Entry Point ##########
    
    Primary async function that initializes global objects,
    loads configuration, and starts the SSH server.
    """
    # ########## Initialize Paths and SSH Host Key ##########
    Paths.init()
    Paths.ensure_ssh_host_key()

    # ########## Load Configuration ##########
    config = Config()
    setup_logging(config.get("logger.level", "DEBUG"))

    # ########## Initialize Global Store ##########
    g = GlobalStore()
    g.set("config", config)

    # ########## Start SSH Server ##########
    runner = SSHServerRunner()
    try:
        await runner.start()
    except KeyboardInterrupt:
        logging.info("Shutting down...")
    except Exception as e:
        logging.exception("Server error")
        return 1
    return 0


############ Main Execution Block ############
if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
