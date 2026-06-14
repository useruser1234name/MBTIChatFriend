package com.example.mbtichatfriend.ui.chat

import com.example.mbtichatfriend.data.local.CharacterEntity
import com.example.mbtichatfriend.model.CharacterEmotion
import com.example.mbtichatfriend.model.ChatMessage

/**
 * MVI 아키텍처 2단계 — ChatViewModel 단일 UiState.
 * 스프린트 2 (A-4): isTyping/currentEmotion/errorMessage/levelUpEvent/levelDownEvent
 * 기존 mutableStateOf 병렬 상태를 Success 필드로 흡수.
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
        // A-4: 흡수된 mutableStateOf 필드
        val currentEmotion: CharacterEmotion = CharacterEmotion.NEUTRAL,
        val levelUpEvent: Int? = null,
        val levelDownEvent: Int? = null,
    ) : ChatUiState()

    /** 치명적 오류 상태 */
    data class Error(val message: String) : ChatUiState()
}
