"""Queue backend abstraction — Redis (optional) and local multiprocessing fallback."""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from typing import Any


class QueueBackend(ABC):
    """Abstract interface for task/result message passing."""

    @abstractmethod
    def put_task(self, task_id: str, task_data: dict[str, Any], ttl: int = 60) -> None:
        """Store a task for a worker to pick up."""

    @abstractmethod
    def get_task(self, task_id: str) -> dict[str, Any] | None:
        """Retrieve a task by ID. Returns None if not found/expired."""

    @abstractmethod
    def put_result(self, task_id: str, result: dict[str, Any] | str, ttl: int = 60) -> None:
        """Store a worker result."""

    @abstractmethod
    def get_result(self, task_id: str, timeout: float = 30.0) -> dict[str, Any] | str | None:
        """Wait for and retrieve a result. Returns None on timeout."""

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the backend is operational."""

    @abstractmethod
    def health_check(self) -> dict[str, Any]:
        """Return backend health status dict."""


# ── Local Backend (multiprocessing, always available) ──────────────────

class LocalBackend(QueueBackend):
    """In-memory queue backend using dicts. Zero external dependencies.

    Suitable for single-machine swarm execution.
    """

    def __init__(self):
        self._tasks: dict[str, tuple[dict, float]] = {}   # task_id -> (data, expires_at)
        self._results: dict[str, tuple[Any, float]] = {}   # task_id -> (data, expires_at)

    def put_task(self, task_id: str, task_data: dict[str, Any], ttl: int = 60) -> None:
        self._tasks[task_id] = (task_data, time.monotonic() + ttl)

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        entry = self._tasks.get(task_id)
        if entry is None:
            return None
        data, expires = entry
        if time.monotonic() > expires:
            del self._tasks[task_id]
            return None
        return data

    def put_result(self, task_id: str, result: dict[str, Any] | str, ttl: int = 60) -> None:
        self._results[task_id] = (result, time.monotonic() + ttl)

    def get_result(self, task_id: str, timeout: float = 30.0) -> dict[str, Any] | str | None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            entry = self._results.get(task_id)
            if entry is not None:
                data, expires = entry
                if time.monotonic() <= expires:
                    del self._results[task_id]
                    return data
                del self._results[task_id]
                return None
            time.sleep(0.05)
        return None

    def is_available(self) -> bool:
        return True

    def health_check(self) -> dict[str, Any]:
        return {
            "backend": "local",
            "available": True,
            "pending_tasks": len(self._tasks),
            "pending_results": len(self._results),
        }


# ── Redis Backend (optional) ──────────────────────────────────────────

class RedisBackend(QueueBackend):
    """Redis-backed queue for distributed swarm execution.

    Requires ``pip install redis``. Falls back gracefully if Redis
    is unavailable.
    """

    def __init__(self, host: str = "localhost", port: int = 6379, db: int = 0):
        self._host = host
        self._port = port
        self._db = db
        self._redis = None
        self._connect()

    def _connect(self) -> None:
        try:
            import redis as redis_lib
            self._redis = redis_lib.Redis(
                host=self._host, port=self._port, db=self._db,
                decode_responses=True, socket_connect_timeout=2,
            )
            self._redis.ping()
        except Exception:
            self._redis = None

    def put_task(self, task_id: str, task_data: dict[str, Any], ttl: int = 60) -> None:
        if not self._redis:
            raise ConnectionError("Redis not available")
        self._redis.setex(f"jagabot:task:{task_id}", ttl, json.dumps(task_data))

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        if not self._redis:
            return None
        raw = self._redis.get(f"jagabot:task:{task_id}")
        if raw is None:
            return None
        return json.loads(raw)

    def put_result(self, task_id: str, result: dict[str, Any] | str, ttl: int = 60) -> None:
        if not self._redis:
            raise ConnectionError("Redis not available")
        payload = json.dumps(result) if isinstance(result, dict) else result
        key = f"jagabot:result:{task_id}"
        self._redis.setex(key, ttl, payload)
        self._redis.publish(f"jagabot:done:{task_id}", "1")

    def get_result(self, task_id: str, timeout: float = 30.0) -> dict[str, Any] | str | None:
        if not self._redis:
            return None
        key = f"jagabot:result:{task_id}"
        # Fast path: result already available
        raw = self._redis.get(key)
        if raw is not None:
            self._redis.delete(key)
            try:
                return json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                return raw
        # Slow path: poll
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            raw = self._redis.get(key)
            if raw is not None:
                self._redis.delete(key)
                try:
                    return json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    return raw
            time.sleep(0.1)
        return None

    def is_available(self) -> bool:
        if not self._redis:
            return False
        try:
            return self._redis.ping()
        except Exception:
            return False

    def health_check(self) -> dict[str, Any]:
        available = self.is_available()
        info: dict[str, Any] = {
            "backend": "redis",
            "available": available,
            "host": self._host,
            "port": self._port,
        }
        if available and self._redis:
            try:
                server_info = self._redis.info("server")
                info["redis_version"] = server_info.get("redis_version", "unknown")
                info["uptime_seconds"] = server_info.get("uptime_in_seconds", 0)
            except Exception:
                pass
        return info


# ── Factory ───────────────────────────────────────────────────────────

def get_backend(
    prefer_redis: bool = True,
    redis_host: str = "localhost",
    redis_port: int = 6379,
) -> QueueBackend:
    """Get the best available queue backend.

    Tries Redis first (if ``prefer_redis=True``), falls back to LocalBackend.
    """
    if prefer_redis:
        try:
            backend = RedisBackend(host=redis_host, port=redis_port)
            if backend.is_available():
                return backend
        except Exception:
            pass
    return LocalBackend()
