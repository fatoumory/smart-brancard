# migrations/env.py
# Configuration d'Alembic : utilise la même base et les mêmes modèles que l'API

from logging.config import fileConfig

from alembic import context

import models  # noqa: F401  enregistre tous les modèles dans Base.metadata
from database import Base, engine

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Les migrations sont générées en comparant la base à ces modèles
target_metadata = Base.metadata


def include_object(obj, name, type_, reflected, compare_to):
    # Ignore les tables qui ne viennent pas de nos modèles
    # (ex : spatial_ref_sys, créée par l'extension PostGIS) : Alembic ne doit pas les supprimer
    if type_ == "table" and reflected and compare_to is None:
        return False
    return True


def run_migrations_offline() -> None:
    """Génère le SQL sans se connecter (alembic upgrade head --sql)"""
    context.configure(
        url=engine.url.render_as_string(hide_password=False),
        target_metadata=target_metadata,
        include_object=include_object,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Applique les migrations sur la base de DATABASE_URL"""
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
