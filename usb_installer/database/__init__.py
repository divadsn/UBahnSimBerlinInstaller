from typing import Optional

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import sessionmaker

engine: Optional[Engine] = None
SessionLocal: Optional[sessionmaker] = None


def init_db(database_url: str):
    """
    Initialize the database engine and session factory with the given database URL.
    """
    global engine, SessionLocal
    engine = create_engine(database_url, echo=False)
    SessionLocal = sessionmaker(bind=engine)
