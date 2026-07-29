"""
Resilient outbound transport for the demo checkout service (ADR-0001).

Policy order (load-bearing):
  1. Idempotency — short-circuit if the key already succeeded
  2. Retry — bounded attempts with exponential backoff + full jitter (transient only)
  3. Circuit breaker — per dependency base URL, inside the retry loop

sleep and rng are injectable for deterministic tests.
"""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from typing import Any, TypeVar

T = TypeVar("T")

TRANSIENT_STATUS_CODES = frozenset({500, 502, 503, 504})


class TransientError(Exception):
    """Simulated transient dependency failure (retryable)."""

    def __init__(self, message: str = "transient failure", status_code: int = 503):
        super().__init__(message)
        self.status_code = status_code


class CircuitOpenError(Exception):
    """Raised when the circuit breaker is open for a dependency."""


def is_transient(exc: BaseException) -> bool:
    if isinstance(exc, TransientError):
        return True
    status_code = getattr(exc, "status_code", None)
    return status_code in TRANSIENT_STATUS_CODES


class IdempotencyStore:
    def __init__(self) -> None:
        self._results: dict[str, Any] = {}

    def get(self, key: str) -> Any | None:
        return self._results.get(key)

    def put(self, key: str, result: Any) -> None:
        self._results[key] = result

    def clear(self) -> None:
        self._results.clear()


class CircuitBreaker:
    def __init__(
        self,
        *,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._clock = clock or time.monotonic
        self._state: dict[str, dict[str, Any]] = {}

    def _entry(self, dependency: str) -> dict[str, Any]:
        if dependency not in self._state:
            self._state[dependency] = {"failures": 0, "opened_at": None, "open": False}
        return self._state[dependency]

    def before_call(self, dependency: str) -> None:
        entry = self._entry(dependency)
        if not entry["open"]:
            return
        opened_at = entry["opened_at"]
        if opened_at is not None and self._clock() - opened_at >= self.recovery_timeout:
            entry["open"] = False
            entry["failures"] = 0
            entry["opened_at"] = None
            return
        raise CircuitOpenError(f"Circuit open for {dependency}")

    def record_success(self, dependency: str) -> None:
        entry = self._entry(dependency)
        entry["failures"] = 0
        entry["open"] = False
        entry["opened_at"] = None

    def record_failure(self, dependency: str) -> None:
        entry = self._entry(dependency)
        entry["failures"] += 1
        if entry["failures"] >= self.failure_threshold:
            entry["open"] = True
            entry["opened_at"] = self._clock()


class ResilientTransport:
    def __init__(
        self,
        *,
        max_retries: int = 3,
        base_delay_ms: float = 100.0,
        idempotency_store: IdempotencyStore | None = None,
        circuit_breaker: CircuitBreaker | None = None,
        sleep: Callable[[float], None] | None = None,
        rng: Callable[[], float] | None = None,
    ) -> None:
        self.max_retries = max_retries
        self.base_delay_ms = base_delay_ms
        self.idempotency_store = idempotency_store or IdempotencyStore()
        self.circuit_breaker = circuit_breaker or CircuitBreaker()
        self._sleep = sleep or time.sleep
        self._rng = rng or random.random

    def _backoff_seconds(self, attempt: int) -> float:
        cap_ms = self.base_delay_ms * (2**attempt)
        return self._rng() * (cap_ms / 1000.0)

    def execute(
        self,
        *,
        dependency: str,
        idempotency_key: str,
        operation: Callable[[], T],
    ) -> T:
        cached = self.idempotency_store.get(idempotency_key)
        if cached is not None:
            return cached

        last_exc: BaseException | None = None
        for attempt in range(self.max_retries + 1):
            try:
                self.circuit_breaker.before_call(dependency)
                result = operation()
                self.circuit_breaker.record_success(dependency)
                self.idempotency_store.put(idempotency_key, result)
                return result
            except CircuitOpenError:
                raise
            except BaseException as exc:
                if not is_transient(exc):
                    raise
                last_exc = exc
                self.circuit_breaker.record_failure(dependency)
                if attempt >= self.max_retries:
                    break
                self._sleep(self._backoff_seconds(attempt))

        assert last_exc is not None
        raise last_exc


_default_transport: ResilientTransport | None = None


def get_transport() -> ResilientTransport:
    global _default_transport
    if _default_transport is None:
        _default_transport = ResilientTransport()
    return _default_transport


def resilient_call(
    *,
    dependency: str,
    idempotency_key: str,
    operation: Callable[[], T],
    transport: ResilientTransport | None = None,
) -> T:
    active = transport or get_transport()
    return active.execute(
        dependency=dependency,
        idempotency_key=idempotency_key,
        operation=operation,
    )
