import asyncio
import os
from logging.config import fileConfig

from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context
from core.config import get_settings
from db import models  # noqa: F401  (registers the tables)
from db.base import Base

if context.config.config_file_name:
    fileConfig(context.config.config_file_name)

URL = os.environ.get("ALEMBIC_DATABASE_URL") or get_settings().database_url


def run(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()


async def main() -> None:
    engine = create_async_engine(URL)
    async with engine.connect() as connection:
        await connection.run_sync(run)
    await engine.dispose()


asyncio.run(main())
