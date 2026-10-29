from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar

_cancellation_check: ContextVar[Callable[[], None] | None] = ContextVar(
    "llm_cancellation_check",
    default=None,
)


@contextmanager
def cancellation_scope(
    check: Callable[[], None] | None,
) -> Iterator[None]:
    token = _cancellation_check.set(check)
    try:
        yield
    finally:
        _cancellation_check.reset(token)


def current_cancellation_check() -> Callable[[], None] | None:
    return _cancellation_check.get()
