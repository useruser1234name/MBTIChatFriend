package com.example.mbtichatfriend.ui.chat

import com.example.mbtichatfriend.data.local.CharacterEntity
import com.example.mbtichatfriend.model.ChatMessage

/**
 * MVI 아키텍처 1단계 — ChatViewModel 단일 UiState.
 * 9차 스프린트 (ARCH-B 황인호 + ARCH-C 오세진).
 *
 * 기존 복수 StateFlow → 단일 ChatUiState.Success로 통합.
 * ChatScreen에서 when(uiState) 분기로 렌더링.
 *
 * 실제 타입 기준:
 * - messages: List<ChatMessage> (MessageEntity 아님, ChatRepository에서 매핑된 모델)
 * - character: CharacterEntity? (com.example.mbtichatfriend.data.local)
 * - sessionWarning: String? (SessionLimitResult 타입 없음 — ChatViewModel.sessionWarnMessage 동일)
 */
sealed class ChatUiState {
    /** 초기 로딩 상태 */
    object Loading : ChatUiState()

    /** 정상 동작 상태 — 모든 UI 데이터 포함 */
    data class Success(
        val messages: List<ChatMessage> = emptyList(),
        val character: CharacterEntity? = null,
        val isStreaming: Boolean = false,
        val isLottieAnimating: Boolean = false,
        val sessionWarning: String? = null,
        val affinityLevel: Int = 1,
        val error: String? = null,
        val isOnline: Boolean = true,
    ) : ChatUiState()

    /** 치명적 오류 상태 */
    data class Error(val message: String) : ChatUiState()
}
