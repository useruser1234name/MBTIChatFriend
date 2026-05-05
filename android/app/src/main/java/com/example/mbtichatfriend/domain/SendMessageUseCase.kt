package com.example.mbtichatfriend.domain

import com.example.mbtichatfriend.data.local.CharacterEntity
import com.example.mbtichatfriend.data.remote.MemoryItem
import com.example.mbtichatfriend.data.remote.SseEvent
import com.example.mbtichatfriend.data.repository.ChatRepository
import com.example.mbtichatfriend.model.ChatMessage
import kotlinx.coroutines.flow.Flow
import javax.inject.Inject
import javax.inject.Singleton

/**
 * SendMessageUseCase — 메시지 전송 전담 UseCase.
 *
 * ChatViewModel에서 분리된 단일 책임 클래스 (W1-3 스트랭글러 패턴 1단계).
 * ARCH-A 조성현 설계 / ARCH-B 황인호 검증 (2차 회의 합의).
 *
 * 책임:
 * - SSE 스트리밍 메시지 전송
 * - REST 폴백 메시지 전송
 * - 메시지 DB 저장
 *
 * 책임 외 (ViewModel 또는 다른 UseCase에서 처리):
 * - 호감도 업데이트 → AffinityManager (다음 스프린트)
 * - 감정/표정 업데이트 → ExpressionManager (다음 스프린트)
 * - 오프라인 큐 관리 → OfflineMessageQueue (기존 유지)
 */
@Singleton
class SendMessageUseCase @Inject constructor(
    private val chatRepo: ChatRepository,
) {

    /**
     * SSE 스트리밍으로 메시지를 전송하고 이벤트 Flow를 반환.
     *
     * @param text 전송할 메시지 텍스트
     * @param character 대상 캐릭터 엔티티
     * @param nickname 사용자 닉네임
     * @param userMbti 사용자 MBTI (nullable)
     * @param conversationHistory 최근 대화 히스토리
     * @param memories 장기 기억 목록
     * @return SseEvent Flow — Message / Done / Error 이벤트 스트림
     */
    fun streamMessage(
        text: String,
        character: CharacterEntity,
        nickname: String,
        userMbti: String?,
        conversationHistory: List<Map<String, String>>,
        memories: List<MemoryItem>,
    ): Flow<SseEvent> = chatRepo.streamMessage(
        message = text,
        mbti = character.mbti,
        speechStyle = character.speechStyle,
        relationship = character.relationship,
        nickname = nickname,
        affinityLevel = character.affinityLevel,
        conversationHistory = conversationHistory,
        userMbti = userMbti,
        characterName = character.name,
        characterId = character.id.toString(),
        memories = memories,
    )

    /**
     * REST 폴백 — SSE 실패 시 사용.
     */
    suspend fun sendMessageRest(
        text: String,
        character: CharacterEntity,
        nickname: String,
        userMbti: String?,
        conversationHistory: List<Map<String, String>>,
        memories: List<MemoryItem>,
    ) = chatRepo.sendMessage(
        message = text,
        mbti = character.mbti,
        speechStyle = character.speechStyle,
        relationship = character.relationship,
        nickname = nickname,
        affinityLevel = character.affinityLevel,
        conversationHistory = conversationHistory,
        userMbti = userMbti,
        characterName = character.name,
        characterId = character.id.toString(),
        memories = memories,
    )

    /**
     * 메시지 DB 저장.
     */
    suspend fun saveUserMessage(characterId: Long, text: String) {
        chatRepo.saveMessage(
            characterId = characterId,
            text = text,
            isFromUser = true,
        )
    }

    suspend fun savePendingMessage(characterId: Long, text: String) {
        chatRepo.saveMessage(
            characterId = characterId,
            text = text,
            isFromUser = true,
            sendStatus = "PENDING",
        )
    }

    suspend fun saveReplyMessage(
        characterId: Long,
        text: String,
        emotion: String?,
    ) {
        chatRepo.saveMessage(
            characterId = characterId,
            text = text,
            isFromUser = false,
            emotion = emotion,
        )
    }
}
