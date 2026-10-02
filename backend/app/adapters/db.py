import logging

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


def create_db_engine(database_url: str) -> Engine:
    # One pool per process, shared by every repository and the health check.
    return create_engine(database_url, pool_pre_ping=True)


class PostgresHealthCheck:
    def __init__(self, engine: Engine):
        self.engine = engine

    def check_db(self) -> bool:
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except SQLAlchemyError as e:
            logger.error(f"DB health check failed: {e}")
            return False
