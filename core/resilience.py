from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Iterable, Optional, TypeVar


class ServiceError(Exception):
    pass


class ServiceAuthError(ServiceError):
    pass


class ServiceRateLimitError(ServiceError):
    pass


class ServiceUnavailableError(ServiceError):
    pass


class ServiceRequestError(ServiceError):
    pass


T = TypeVar("T")


@dataclass
class CircuitBreaker:
    name: str
    failure_threshold: int = 3
    cooldown_seconds: float = 20.0

    def __post_init__(self):
        self.failures = 0
        self.opened_at = 0.0

    def allow(self) -> bool:
        if self.opened_at <= 0:
            return True
        if (time.time() - self.opened_at) >= self.cooldown_seconds:
            self.failures = 0
            self.opened_at = 0.0
            return True
        return False

    def record_success(self):
        self.failures = 0
        self.opened_at = 0.0

    def record_failure(self):
        self.failures += 1
        if self.failures >= self.failure_threshold:
            self.opened_at = time.time()


def validate_http_status(status_code: int, service: str = "service"):
    if 200 <= int(status_code) < 300:
        return
    if status_code in (401, 403):
        raise ServiceAuthError(f"{service} authentication failed ({status_code})")
    if status_code == 429:
        raise ServiceRateLimitError(f"{service} rate limited ({status_code})")
    if status_code >= 500:
        raise ServiceUnavailableError(f"{service} unavailable ({status_code})")
    raise ServiceError(f"{service} request failed ({status_code})")


def retry_with_backoff(
    operation: Callable[[], T],
    retries: int = 2,
    base_delay: float = 0.25,
    factor: float = 2.0,
    retry_on: Optional[Iterable[type[Exception]]] = None,
) -> T:
    retry_types = tuple(retry_on or (ServiceRateLimitError, ServiceUnavailableError, ServiceRequestError))
    attempt = 0
    while True:
        try:
            return operation()
        except Exception as exc:
            attempt += 1
            if not isinstance(exc, retry_types) or attempt > int(retries):
                raise
            delay = max(0.0, float(base_delay)) * (float(factor) ** (attempt - 1))
            time.sleep(delay)
