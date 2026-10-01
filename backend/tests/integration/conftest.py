import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "")
ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


@pytest.fixture(scope="session")
def alembic_cfg() -> Config:
    if not TEST_DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL not set")
    cfg = Config(str(ALEMBIC_INI))
    cfg.attributes["database_url"] = TEST_DATABASE_URL
    return cfg


@pytest.fixture(scope="session")
def engine(alembic_cfg):
    """A freshly migrated database shared by the integration session."""
    eng = create_engine(TEST_DATABASE_URL)
    command.downgrade(alembic_cfg, "base")
    command.upgrade(alembic_cfg, "head")
    yield eng
    eng.dispose()
