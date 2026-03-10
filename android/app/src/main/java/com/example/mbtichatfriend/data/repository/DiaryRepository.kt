package com.example.mbtichatfriend.data.repository

import com.example.mbtichatfriend.data.local.DiaryDao
import com.example.mbtichatfriend.data.local.DiaryEntity
import com.example.mbtichatfriend.data.remote.ChatApi
import com.example.mbtichatfriend.data.remote.DiaryRequest
import kotlinx.coroutines.flow.Flow
import java.time.LocalDate
import javax.inject.Inject
import javax.inject.Singleton

data class DiaryResult(val diary: String, val emotion: String)

@Singleton
class DiaryRepository @Inject constructor(
    private val dao: DiaryDao,
    private val api: ChatApi
) {
    fun observeDiaries(characterId: Long): Flow<List<DiaryEntity>> =
        dao.observeByCharacter(characterId)

    suspend fun getTodayDiary(characterId: Long): DiaryEntity? =
        dao.getByDate(characterId, LocalDate.now().toString())

    suspend fun generateDiary(
        characterId: Long,
        characterName: String,
        mbti: String,
        speechStyle: String,
        nickname: String,
        affinityLevel: Int,
        conversationHistory: List<Map<String, String>>
    ): DiaryResult {
        return try {
            val response = api.generateDiary(
                DiaryRequest(
                    characterName = characterName,
                    mbti = mbti,
                    speechStyle = speechStyle,
                    nickname = nickname,
                    affinityLevel = affinityLevel,
                    conversationHistory = conversationHistory
                )
            )
            val today = LocalDate.now().toString()
            dao.insert(
                DiaryEntity(
                    characterId = characterId,
                    content = response.diary,
                    emotion = response.emotion,
                    date = today
                )
            )
            DiaryResult(diary = response.diary, emotion = response.emotion)
        } catch (e: Exception) {
            DiaryResult(
                diary = "오늘은 왠지 말로 표현하기 어려운 하루였어... 나중에 다시 써야겠다.",
                emotion = "NEUTRAL"
            )
        }
    }

    suspend fun clearDiaries(characterId: Long) {
        dao.deleteByCharacter(characterId)
    }
}
