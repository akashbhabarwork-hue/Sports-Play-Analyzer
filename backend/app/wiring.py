from dataclasses import dataclass

from .adapters.db import PostgresHealthCheck
from .config import Settings
from .core.ports import HealthCheck


@dataclass(frozen=True, slots=True)
class Container:
    settings: Settings
    health_check: HealthCheck


def build_container(settings: Settings) -> Container:
    health_check = PostgresHealthCheck(settings.database_url)
    return Container(settings=settings, health_check=health_check)
