from alembic import context
from app.config import settings
from app.db import Base, make_engine
from app import models  # noqa: F401

config = context.config
target_metadata = Base.metadata

if context.is_offline_mode():
    context.configure(url=settings().database_url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    connectable = make_engine(settings().database_url)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()
