import inspect

import pytest

from app.core import ports

# Repos that hold per-user data: every read must be scoped by user_id (acceptance A3).
USER_DATA_REPOS = (ports.VideoRepo, ports.JobRepo, ports.ResultRepo)


def public_methods(protocol: type) -> list[tuple[str, inspect.Signature]]:
    return [
        (name, inspect.signature(fn))
        for name, fn in vars(protocol).items()
        if inspect.isfunction(fn) and not name.startswith("_")
    ]


@pytest.mark.parametrize("protocol", USER_DATA_REPOS, ids=lambda p: p.__name__)
def test_user_data_methods_take_user_id_or_are_worker_only(protocol):
    methods = public_methods(protocol)
    assert methods, f"{protocol.__name__} has no methods"
    for name, sig in methods:
        assert "user_id" in sig.parameters or name.endswith("_for_worker"), (
            f"{protocol.__name__}.{name} reads user data without user_id; "
            "add user_id or name it *_for_worker"
        )
