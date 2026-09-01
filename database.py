from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# SQLite database file stored locally in the project root directory
SQLALCHEMY_DATABASE_URL = "sqlite:///./office_comms.db"

# connect_args={"check_same_thread": False} is required specifically for SQLite in FastAPI
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for our ORM [Object-Relational Mapping, a technique to map Python code classes to database tables]
Base = declarative_base()

def get_db():
    """Dependency that creates a new database session per request and closes it afterward."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()