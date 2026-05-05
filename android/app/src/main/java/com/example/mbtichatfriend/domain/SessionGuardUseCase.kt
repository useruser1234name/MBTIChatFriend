package com.example.mbtichatfriend.domain

import com.example.mbtichatfriend.data.remote.SessionCheckRequest
import com.example.mbtichatfriend.data.repository.ChatRepository
import javax.inject.Inject
import javax.inject.Singleton

data class SessionLimitResult(
    val shouldWarn: Boolean,
    val elapsedMinutes: Int,
    val limitMinutes: Int,
    val message: String,
)

data class ConsecutiveDaysResult(
    val consecutiveDays: Int,
    val shouldShowRealityNudge: Boolean,
    val nudgeMessage: String,
)

/**
 * ChatViewModel에서 session 관련 코드를 분리한 UseCase.
 * 7차 스프린트 — ARCH-C 오세진 + ARCH-B 황인호 (기술 부채 해소).
 *
 * ChatViewModel의 session_guard 호출 코드를 이 UseCase로 위임.
 */
@Singleton
class SessionGuardUseCase @Inject constructor(
    private val chatRepository: ChatRepository,
) {
    /**
     * 오늘 세션 사용 시간이 한도(90분/60분)를 초과했는지 확인.
     */
    suspend fun checkSessionLimit(
        roomId: String,
        birthYear: Int? = null,
    ): SessionLimitResult = runCatching {
        val response = chatRepository.checkSession(
            SessionCheckRequest(roomId = roomId, userBirthYear = birthYear)
        )
        SessionLimitResult(
            shouldWarn = response.shouldWarn,
            elapsedMinutes = response.elapsedMinutes,
            limitMinutes = response.limitMinutes,
            message = response.message ?: "",
        )
    }.getOrElse {
        SessionLimitResult(
            shouldWarn = false,
            elapsedMinutes = 0,
            limitMinutes = 90,
            message = "",
        )
    }

    /**
     * 7일 연속 접속 여부 확인 — 현실 관계 유도 메시지 표시 여부.
     */
    suspend fun checkConsecutiveDays(
        roomId: String,
    ): ConsecutiveDaysResult = runCatching {
        val response = chatRepository.checkSession(
            SessionCheckRequest(roomId = roomId)
        )
        ConsecutiveDaysResult(
            consecutiveDays = response.consecutiveDays,
            shouldShowRealityNudge = response.shouldShowRealityNudge,
            nudgeMessage = response.nudgeMessage,
        )
    }.getOrElse {
        ConsecutiveDaysResult(
            consecutiveDays = 0,
            shouldShowRealityNudge = false,
            nudgeMessage = "",
        )
    }
}
