"""SQLAlchemy engine, session factory, and FastAPI dependency."""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _migrate_add_columns()


def _migrate_add_columns() -> None:
    """Add columns introduced after a DB was first created (SQLite only).

    create_all() never ALTERs existing tables, so for a persisted volume we
    add any missing optional columns here. Safe & idempotent.
    """
    from sqlalchemy import inspect, text

    wanted = {
        "sessions": [
            ("video_fps", "FLOAT"),
            ("frame_width", "INTEGER"),
            ("frame_height", "INTEGER"),
            ("grid_cell_px", "INTEGER"),
            ("grid_occ_fraction", "FLOAT"),
            ("refine_edges", "INTEGER"),
        ],
        "measurements": [
            ("tracks_json", "TEXT"),
            ("coverage_pct", "FLOAT"),
        ],
    }
    insp = inspect(engine)
    existing_tables = set(insp.get_table_names())
    with engine.begin() as conn:
        for table, cols in wanted.items():
            if table not in existing_tables:
                continue
            have = {c["name"] for c in insp.get_columns(table)}
            for name, sqltype in cols:
                if name not in have:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {sqltype}"))
