# BogoInsight/database/base.py
from sqlalchemy import Column, String, DateTime, Integer
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime, timezone

Base = declarative_base()

class BaseModel(Base):
    __abstract__ = True
    created_by = Column(String(50), default='admin')
    updated_by = Column(String(50), default='admin')
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))