#!/usr/bin/env python3
import asyncio
import sys
import logging
from pathlib import Path
from datetime import datetime

from helpers.path import Paths
from helpers.config import Config
from helpers.globals import GlobalStore
from helpers.liboqs import ensure_liboqs
from database.client import Database
from sshserver.server import SSHServerRunner


def setup_logging(
        level: str = "DEBUG",
        log_files: bool = False,
        log_dir: str = str(Paths.LOG_DIR),
    ):
        handlers = [logging.StreamHandler()]

        if log_files:
            log_path = Path(log_dir) / f"{datetime.now():%Y-%m-%d_%H-%M-%S}.log"
            handlers.append(logging.FileHandler(log_path, encoding="utf-8"))

        logging.basicConfig(
            level=getattr(logging, level.upper(), logging.DEBUG),
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            handlers=handlers,
            force=True,
        )

async def main() -> int:
    try:
        # Paths
        Paths.init()
        Paths.ensure_ssh_host_key()

        # Config
        config = Config()
        setup_logging(level=config.get("logger.level", "DEBUG"), 
                      log_files=config.get("logger.log_files", False), 
                      log_dir=config.get("logger.log_dir", str(Paths.LOG_DIR))
        )

        # liboqs
        ensure_liboqs(config)

        # DB
        db_config = config.get("db", {})
        db_type = db_config.get("type", "sqlite").lower()

        if db_type == "sqlite":
            db = Database(
                db_type="sqlite",
                database=db_config.get("file", str(Paths.SQLITE_FILE))
            )
        elif db_type in ("mariadb", "mysql"):
            db = Database(
                db_type="mariadb",
                host=db_config.get("host", "localhost"),
                user=db_config.get("user"),
                password=db_config.get("password"),
                database=db_config.get("database"),
                port=db_config.get("port", 3306)
            )
        else:
            raise ValueError(f"Unsupported database type: {db_type}")

        await db.connect()
        await _init_users_table(db, config.get("auth.default_group"))
        logging.info(f"Connected to {db_type.upper()} database")

        # GlobalStore
        g = GlobalStore()
        g.set("config", config)
        g.set("db", db)

        logging.info("PVE SSH Server initialized successfully")

        runner = SSHServerRunner()
        await runner.start()

        return 0

    except KeyboardInterrupt:
        logging.info("Server shutdown by user")
        return 0
    except Exception as e:
        logging.exception("Fatal error during startup")
        return 1
    finally:
        # Graceful shutdown
        try:
            db = GlobalStore.get().require("db")
            await db.close()
            logging.info("Database connection closed")
        except Exception:
            pass


async def _init_users_table(db, default_group):
    """Создаёт таблицу users, если её нет."""
    default_group = int(default_group or 0)
    await db.execute(f"""
        CREATE TABLE IF NOT EXISTS users (
            username    TEXT PRIMARY KEY,
            api_key     TEXT,
            api_secret  TEXT,
            ssh_keys    TEXT DEFAULT '[]',
            group_id    INTEGER DEFAULT {default_group},
            saved_env   TEXT DEFAULT '{{}}',
            history     TEXT DEFAULT '[]',
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    await db.commit()
    logging.info("Database table 'users' initialized")


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))