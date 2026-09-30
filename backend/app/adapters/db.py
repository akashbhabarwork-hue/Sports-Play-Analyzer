import logging
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text
from ..core.ports import HealthCheck

logger = logging.getLogger(__name__)

class PostgresHealthCheck:
    def __init__(self, database_url: str):
        self.engine = create_engine(database_url)

    def check_db(self) -> bool:
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except SQLAlchemyError as e:
            logger.error(f"DB health check failed: {e}")
            return False
