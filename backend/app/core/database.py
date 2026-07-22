from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


engine = create_engine(settings.database_url, echo=settings.app_debug)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_db_tables() -> None:
    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    additions = {
        "appointments": ("client_id", "INTEGER REFERENCES clients(id)"),
        "conversation_states": ("client_id", "INTEGER REFERENCES clients(id)"),
    }
    with engine.begin() as connection:
        for table, (column, definition) in additions.items():
            if table in inspector.get_table_names() and column not in {
                item["name"] for item in inspector.get_columns(table)
            }:
                connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))
        for table in additions:
            index_name = f"ix_{table}_client_id"
            if table in inspector.get_table_names() and index_name not in {
                item["name"] for item in inspector.get_indexes(table)
            }:
                connection.execute(text(f"CREATE INDEX {index_name} ON {table} (client_id)"))
