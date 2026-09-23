# BogoInsight/database/session.py
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError
import streamlit as st

from BogoBots.database.base import Base
from BogoBots.models import (  # noqa: F401 — register models on Base.metadata
    book,
    news_source,
    news_item,
    news_report,
    news_report_item,
    news_hub_config,
)


def _database_url():
    url = make_url(st.secrets["db_url"])
    if "charset" not in url.query:
        url = url.update_query_dict({"charset": "utf8mb4"})
    return url


engine = create_engine(
    _database_url(),
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=10,
    max_overflow=20,
)
Session = sessionmaker(bind=engine, expire_on_commit=False)

_tables_ready = False


def create_tables():
    """Create missing tables once per process. Does not alter existing tables."""
    global _tables_ready
    if _tables_ready:
        return
    try:
        Base.metadata.create_all(bind=engine)
        _tables_ready = True
    except OperationalError as e:
        print("Error occurred during Table creation!")
        print(e)


def get_session():
    """Return a Session. Caller must close() it (or use `with get_session()`)."""
    create_tables()
    return Session()


@contextmanager
def session_scope():
    session = get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def check_db_connection():
    try:
        create_tables()
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except OperationalError as e:
        print(e)
        print("Database connection could not be established.")
        return False
