package com.example.mbtichatfriend.domain

import com.example.mbtichatfriend.data.local.CharacterEntity
import com.example.mbtichatfriend.data.local.UserPreferences
import com.example.mbtichatfriend.data.remote.MemoryItem
import com.example.mbtichatfriend.data.remote.SseEvent
import com.example.mbtichatfriend.data.repository.ChatRepository
import com.example.mbtichatfriend.data.repository.ChatResult
import com.example.mbtichatfriend.model.ChatMessage
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.emitAll
import kotlinx.coroutines.flow.flow
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
    private val userPreferences: UserPreferences,
) {

    /**
     * M2: 캐릭터별로 저장된 "내 역할"/"지금 상황"을 DataStore에서 읽어온다.
     * 모든 전송 경로(SSE/REST/재전송/오프라인 큐/선톡)가 이 UseCase를 거치므로
     * 여기서 한 번만 읽으면 ChatViewModel의 각 호출부를 개별 수정할 필요가 없다.
     * 조회 실패는 대화 전송 자체를 막지 않도록 조용히 빈 문자열로 대체한다.
     */
    private suspend fun loadRoleAndSituation(characterId: Long): Pair<String, String> {
        val role = runCatching { userPreferences.getUserRole(characterId) }.getOrDefault("")
        val situation = runCatching { userPreferences.getSituation(characterId) }.getOrDefault("")
        return role to situation
    }

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
    ): Flow<SseEvent> = flow {
        val (role, situation) = loadRoleAndSituation(character.id)
        emitAll(
            chatRepo.streamMessage(
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
                userRole = role,
                situation = situation,
            )
        )
    }

    /**
     * R1: 선톡(캐릭터 선발화) 전용 SSE 스트리밍 — /chat/proactive.
     * message 대신 hook만 전달한다(유도 문구 합성은 서버 책임). userRole/situation은
     * streamMessage와 동일하게 DataStore의 중앙 저장값을 재사용한다.
     *
     * @param hook 다음 대화 흐름 힌트(서버 story state의 next_hook). 빈 값이면
     *   서버가 기본 안부 흐름으로 폴백한다.
     */
    fun streamProactive(
        hook: String,
        character: CharacterEntity,
        nickname: String,
        userMbti: String?,
        conversationHistory: List<Map<String, String>>,
        memories: List<MemoryItem>,
    ): Flow<SseEvent> = flow {
        val (role, situation) = loadRoleAndSituation(character.id)
        emitAll(
            chatRepo.streamProactive(
                hook = hook,
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
                userRole = role,
                situation = situation,
            )
        )
    }

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
    ): ChatResult {
        val (role, situation) = loadRoleAndSituation(character.id)
        return chatRepo.sendMessage(
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
            userRole = role,
            situation = situation,
        )
    }

    /**
     * 메시지 DB 저장.
     */
    // R3: 반환된 rowId를 ViewModel이 읽음 워터마크 기준으로 사용한다.
    suspend fun saveUserMessage(characterId: Long, text: String): Long =
        chatRepo.saveMessage(
            characterId = characterId,
            text = text,
            isFromUser = true,
        )

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
