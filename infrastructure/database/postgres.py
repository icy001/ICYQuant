from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker


Base = declarative_base()


class Database:
    def __init__(self, url: str) -> None:
        self.engine = create_engine(url)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def get_session(self):
        db = self.SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def init_tables(self) -> None:
        Base.metadata.create_all(bind=self.engine)
