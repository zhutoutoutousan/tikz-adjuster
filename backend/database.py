"""
Database configuration and session management
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

# Database URL - defaults to SQLite for development
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./tikz_editor.db"
)

# For PostgreSQL in production:
# DATABASE_URL = "postgresql://user:password@localhost/tikz_editor"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

