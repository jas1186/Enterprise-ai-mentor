from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.core.config import DATABASE_URL
from app.models import Base

if "sqlite" in DATABASE_URL and ":memory:" in DATABASE_URL:
    engine = create_engine(
        DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
elif "sqlite" in DATABASE_URL:
    engine = create_engine(
        DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False},
    )
else:
    engine = create_engine(
        DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initialize the database tables."""
    Base.metadata.create_all(bind=engine)
    migrations = {
        "employees": {
            "password_hash": "VARCHAR(255) NOT NULL DEFAULT ''",
            "clearance_level": "INTEGER NOT NULL DEFAULT 1",
            "is_admin": "BOOLEAN NOT NULL DEFAULT FALSE",
        },
        "documents": {
            "required_clearance": "INTEGER NOT NULL DEFAULT 1",
            "category": "VARCHAR(100) NOT NULL DEFAULT 'general'",
            "department": "VARCHAR(255)",
        },
    }
    inspector = inspect(engine)
    with engine.begin() as connection:
        for table, columns in migrations.items():
            existing = {column["name"] for column in inspector.get_columns(table)}
            for name, definition in columns.items():
                if name not in existing:
                    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {definition}"))


def get_db() -> Session:
    """Dependency for FastAPI to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
