"""Circuit Breaker 패턴 구현 — 3차 스프린트 P0 운영 안정성 확보.

상태 머신:
    CLOSED  (정상)   → 연속 N회 실패 시            → OPEN (차단)
    OPEN    (차단)   → recovery_timeout 초 후       → HALF_OPEN (탐색)
    HALF_OPEN (탐색) → 성공 시 → CLOSED / 실패 시 → OPEN

CTO-C 이서연 설계.
"""

from __future__ import annotations

import asyncio
import logging
import time
from enum import Enum
from typing import Any, Awaitable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitOpenError(Exception):
    """Circuit Breaker가 OPEN 상태일 때 발생하는 예외."""

    def __init__(self, name: str) -> None:
        super().__init__(f"[CircuitBreaker:{name}] OPEN — 호출 차단됨")
        self.circuit_name = name


class CircuitBreaker:
    """단일 의존성(DB / API 등)을 보호하는 Circuit Breaker.

    Args:
        name: 식별용 이름 (로그/모니터링에 사용)
        failure_threshold: 연속 실패 횟수 임계값 → OPEN 전환
        recovery_timeout: OPEN 상태 유지 초 → HALF_OPEN 전환
        half_open_max_calls: HALF_OPEN 상태에서 허용하는 최대 탐색 호출 수
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max_calls: int = 3,
    ) -> None:
        self._name = name
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._half_open_max_calls = half_open_max_calls

        self._state = CircuitState.CLOSED
        self._failure_count: int = 0
        self._success_count: int = 0  # HALF_OPEN 탐색 성공 카운터
        self._half_open_calls: int = 0  # HALF_OPEN 중 진행 중인 호출 수
        self._opened_at: float = 0.0  # OPEN 전환 시각 (time.monotonic)

        self._lock = asyncio.Lock()

    # ── 상태 조회 ──────────────────────────────────────────────────────────

    @property
    def state(self) -> str:
        """현재 상태를 문자열로 반환: 'CLOSED' / 'OPEN' / 'HALF_OPEN'."""
        self._maybe_transition_to_half_open()
        return self._state.value

    def _maybe_transition_to_half_open(self) -> None:
        """OPEN 상태에서 recovery_timeout이 지났으면 HALF_OPEN으로 전환 (Lock 없이 조회 전용)."""
        if (
            self._state == CircuitState.OPEN
            and time.monotonic() - self._opened_at >= self._recovery_timeout
        ):
            self._state = CircuitState.HALF_OPEN
            self._half_open_calls = 0
            self._success_count = 0
            logger.info(
                f"[CB:{self._name}] OPEN → HALF_OPEN "
                f"(recovery_timeout={self._recovery_timeout}s 경과)"
            )

    # ── 핵심 호출 ──────────────────────────────────────────────────────────

    async def call(self, coro: Awaitable[T]) -> T:
        """Circuit Breaker를 통해 코루틴을 실행한다.

        - CLOSED: 그대로 실행
        - OPEN: 즉시 CircuitOpenError 발생 (recovery_timeout 확인 후 HALF_OPEN 전환 가능)
        - HALF_OPEN: 최대 half_open_max_calls 까지만 실행, 초과 시 차단
        """
        async with self._lock:
            self._maybe_transition_to_half_open()

            if self._state == CircuitState.OPEN:
                raise CircuitOpenError(self._name)

            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self._half_open_max_calls:
                    raise CircuitOpenError(self._name)
                self._half_open_calls += 1

        # Lock 밖에서 실제 IO 호출 (다른 코루틴 블로킹 방지)
        try:
            result = await coro
        except Exception as exc:
            async with self._lock:
                await self._on_failure()
            raise

        async with self._lock:
            await self._on_success()

        return result

    # ── 상태 전환 내부 메서드 (Lock 보유 상태에서 호출) ────────────────────

    async def _on_success(self) -> None:
        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            logger.info(
                f"[CB:{self._name}] HALF_OPEN 탐색 성공 "
                f"({self._success_count}/{self._half_open_max_calls})"
            )
            if self._success_count >= self._half_open_max_calls:
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                self._success_count = 0
                self._half_open_calls = 0
                logger.info(f"[CB:{self._name}] HALF_OPEN → CLOSED (복구 완료)")
        elif self._state == CircuitState.CLOSED:
            # 정상 성공: 연속 실패 카운터 초기화
            if self._failure_count > 0:
                self._failure_count = 0

    async def _on_failure(self) -> None:
        if self._state == CircuitState.HALF_OPEN:
            # 탐색 중 실패 → 즉시 OPEN으로 되돌림
            self._state = CircuitState.OPEN
            self._opened_at = time.monotonic()
            self._failure_count = self._failure_threshold  # 이미 임계값 도달 표시
            self._half_open_calls = 0
            self._success_count = 0
            logger.warning(
                f"[CB:{self._name}] HALF_OPEN 탐색 실패 → OPEN "
                f"(recovery_timeout 재시작)"
            )
        else:
            # CLOSED 상태: 연속 실패 카운터 증가
            self._failure_count += 1
            logger.warning(
                f"[CB:{self._name}] 실패 카운트={self._failure_count}/"
                f"{self._failure_threshold}"
            )
            if self._failure_count >= self._failure_threshold:
                self._state = CircuitState.OPEN
                self._opened_at = time.monotonic()
                logger.error(
                    f"[CB:{self._name}] CLOSED → OPEN "
                    f"(연속 {self._failure_count}회 실패)"
                )

    # ── 모니터링 ───────────────────────────────────────────────────────────

    def get_status(self) -> dict:
        """모니터링용 상태 딕셔너리 반환."""
        self._maybe_transition_to_half_open()
        now = time.monotonic()
        remaining = 0.0
        if self._state == CircuitState.OPEN:
            elapsed = now - self._opened_at
            remaining = max(0.0, self._recovery_timeout - elapsed)

        return {
            "name": self._name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "failure_threshold": self._failure_threshold,
            "recovery_timeout": self._recovery_timeout,
            "half_open_max_calls": self._half_open_max_calls,
            "half_open_calls": self._half_open_calls,
            "recovery_remaining_seconds": round(remaining, 1),
        }


# ── 전역 싱글톤 ────────────────────────────────────────────────────────────

_db_circuit = CircuitBreaker(
    name="postgres",
    failure_threshold=5,
    recovery_timeout=60,
    half_open_max_calls=3,
)

_openai_circuit = CircuitBreaker(
    name="openai",
    failure_threshold=3,
    recovery_timeout=30,
    half_open_max_calls=3,
)


def get_db_circuit() -> CircuitBreaker:
    """PostgreSQL DB 보호용 Circuit Breaker 싱글톤 반환."""
    return _db_circuit


def get_openai_circuit() -> CircuitBreaker:
    """OpenAI API 보호용 Circuit Breaker 싱글톤 반환."""
    return _openai_circuit
