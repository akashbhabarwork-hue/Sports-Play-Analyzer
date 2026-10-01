from typing import Protocol


class HealthCheck(Protocol):
    def check_db(self) -> bool: ...
