package com.example.mbtichatfriend.data.repository

import android.util.Log
import com.example.mbtichatfriend.data.remote.ChatApi
import com.example.mbtichatfriend.data.remote.ClientEventDto
import com.example.mbtichatfriend.data.remote.EventBatchRequest
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.launch
import javax.inject.Inject
import javax.inject.Singleton

/**
 * 분석 이벤트 배치 전송 repository (PM 로드맵 A1 — 최소 계측).
 *
 * 설계 원칙:
 * - 인메모리 단일 이벤트 즉시 전송 (영구 큐 불필요 수준)
 * - 네트워크 실패가 앱 동작을 막지 않도록 try/catch + fire-and-forget
 * - user_id는 AuthInterceptor + 서버가 토큰에서 채우므로 클라이언트는 불필요
 *
 * 이벤트 허용 목록(server/app/analytics_events.py ALLOWED_CLIENT_EVENTS):
 *   app_open, app_background, onboarding_step, onboarding_complete,
 *   chat_message_sent, affinity_level_up, diary_opened,
 *   paywall_shown, premium_screen_open, purchase_initiated,
 *   purchase_complete, community_post_viewed
 */
@Singleton
class AnalyticsRepository @Inject constructor(
    private val api: ChatApi,
) {

    /**
     * 단일 이벤트를 배치(1건) 로 즉시 전송한다.
     * 호출부에서 scope를 제공(viewModelScope 또는 applicationScope).
     * 실패는 로그만 남기고 무시한다.
     */
    fun track(
        scope: CoroutineScope,
        eventType: String,
        roomId: String = "",
        characterId: String = "",
        payload: Map<String, Any?> = emptyMap(),
    ) {
        scope.launch {
            try {
                val batch = EventBatchRequest(
                    events = listOf(
                        ClientEventDto(
                            eventType = eventType,
                            roomId = roomId,
                            characterId = characterId,
                            payload = payload,
                        )
                    )
                )
                api.logEvents(batch)
            } catch (e: Exception) {
                Log.w(TAG, "analytics track failed: $eventType", e)
            }
        }
    }

    /**
     * 여러 이벤트를 단일 배치로 전송한다 (최대 100건, 서버 제한).
     */
    fun trackBatch(
        scope: CoroutineScope,
        events: List<ClientEventDto>,
    ) {
        if (events.isEmpty()) return
        scope.launch {
            try {
                api.logEvents(EventBatchRequest(events = events))
            } catch (e: Exception) {
                Log.w(TAG, "analytics trackBatch failed (${events.size} events)", e)
            }
        }
    }

    private companion object {
        const val TAG = "AnalyticsRepository"

        // 서버 analytics_events.py 상수 — 이벤트명 오타 방지
        const val APP_OPEN = "app_open"
        const val ONBOARDING_STEP = "onboarding_step"
        const val ONBOARDING_COMPLETE = "onboarding_complete"
    }
}

// ── 편의 확장 상수 (호출부에서 import해서 사용) ────────────────────────────────
object AnalyticsEvent {
    const val APP_OPEN = "app_open"
    const val APP_BACKGROUND = "app_background"
    const val ONBOARDING_STEP = "onboarding_step"
    const val ONBOARDING_COMPLETE = "onboarding_complete"
    const val CHAT_MESSAGE_SENT = "chat_message_sent"
    const val AFFINITY_LEVEL_UP = "affinity_level_up"
    const val DIARY_OPENED = "diary_opened"
    const val PAYWALL_SHOWN = "paywall_shown"
    const val PREMIUM_SCREEN_OPEN = "premium_screen_open"
    const val PURCHASE_INITIATED = "purchase_initiated"
    const val PURCHASE_COMPLETE = "purchase_complete"
    const val COMMUNITY_POST_VIEWED = "community_post_viewed"
}
