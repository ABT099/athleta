"""
Alembic environment for auto-regulation's OWN database.

This migrates only auto-reg-owned algo tables (those mapped on ``AutoregBase``),
against ``AUTOREG_DATABASE_URL``. The api database is owned by the api service
(its own drizzle-kit migrations) and is not managed here.
"""
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool, text

from app.database import AUTOREG_DATABASE_URL, AutoregBase

# Importing the models package registers every model on its declarative base.
# Auto-reg-owned models map onto AutoregBase, so its metadata is the autogenerate
# target; api-owned tables are intentionally absent.
import app.models  # noqa: F401  (side-effect import: registers models)

config = context.config
config.set_main_option("sqlalchemy.url", AUTOREG_DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = AutoregBase.metadata

# Algo tables live in the ai_analysis schema.
VERSION_TABLE_SCHEMA = None if AUTOREG_DATABASE_URL.startswith("sqlite") else "ai_analysis"


def run_migrations_offline() -> None:
    context.configure(
        url=AUTOREG_DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        version_table_schema=VERSION_TABLE_SCHEMA,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        # The version table lives in ai_analysis, which the first migration creates —
        # ensure the schema exists before Alembic touches its bookkeeping table.
        if VERSION_TABLE_SCHEMA:
            connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {VERSION_TABLE_SCHEMA}"))
            connection.commit()
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            version_table_schema=VERSION_TABLE_SCHEMA,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
