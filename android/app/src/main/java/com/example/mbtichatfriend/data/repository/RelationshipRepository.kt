package com.example.mbtichatfriend.data.repository

import com.example.mbtichatfriend.data.remote.ChatApi
import com.example.mbtichatfriend.data.remote.MemoryAlbumResponse
import com.example.mbtichatfriend.data.remote.MemoryMomentItem
import com.example.mbtichatfriend.data.remote.MemoryMomentRequest
import com.example.mbtichatfriend.data.remote.RelationshipSummaryResponse
import javax.inject.Inject
import javax.inject.Singleton

/**
 * 관계 히스토리 & 기억 앨범 Repository.
 *
 * UX-B 안현우 + UI-C 정수아 설계 (5차 회의 합의).
 * 캐릭터 투자감 강화 → 이탈률 감소 핵심 기능.
 *
 * ChatApi 호출을 위임하는 단순 Repository 패턴.
 * 오프라인 캐싱은 Phase 2에서 Room DB 연동 예정.
 */
@Singleton
class RelationshipRepository @Inject constructor(
    private val api: ChatApi
) {

    /**
     * 관계 히스토리 요약 조회.
     *
     * @param roomId 채팅방 ID
     * @param characterId 캐릭터 ID (빈 문자열이면 전체 캐릭터 합산)
     * @return 총 메시지 수, 세션 수, 함께한 일수, 호감도 변화 이력, 관심 토픽, 첫 대화 날짜
     */
    suspend fun getRelationshipSummary(
        roomId: String,
        characterId: String = ""
    ): Result<RelationshipSummaryResponse> = runCatching {
        api.getRelationshipSummary(roomId = roomId, characterId = characterId)
    }

    /**
     * 특별한 순간을 기억 앨범에 저장.
     *
     * @param roomId 채팅방 ID
     * @param characterId 캐릭터 ID
     * @param messageText 저장할 메시지 텍스트
     * @param momentType "special" | "funny" | "touching"
     * @param userNote 사용자 메모 (선택)
     */
    suspend fun saveMemoryMoment(
        roomId: String,
        characterId: String,
        messageText: String,
        momentType: String = "special",
        userNote: String = ""
    ): Result<Unit> = runCatching {
        api.saveMemoryMoment(
            roomId = roomId,
            request = MemoryMomentRequest(
                characterId = characterId,
                messageText = messageText,
                momentType = momentType,
                userNote = userNote
            )
        )
        Unit
    }

    /**
     * 저장된 기억 앨범 조회.
     *
     * @param roomId 채팅방 ID
     * @param characterId 캐릭터 ID (빈 문자열이면 전체)
     * @return 기억 앨범 항목 목록 (최신순, 최대 200개)
     */
    suspend fun getMemoryAlbum(
        roomId: String,
        characterId: String = ""
    ): Result<List<MemoryMomentItem>> = runCatching {
        val response: MemoryAlbumResponse =
            api.getMemoryAlbum(roomId = roomId, characterId = characterId)
        response.album
    }
}
