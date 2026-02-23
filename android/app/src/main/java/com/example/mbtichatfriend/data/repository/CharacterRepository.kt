package com.example.mbtichatfriend.data.repository

import com.example.mbtichatfriend.data.local.CharacterDao
import com.example.mbtichatfriend.data.local.CharacterEntity
import com.example.mbtichatfriend.data.local.MessageDao
import com.example.mbtichatfriend.model.PRESET_CHARACTERS
import com.example.mbtichatfriend.model.PresetCharacter
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class CharacterRepository @Inject constructor(
    private val dao: CharacterDao,
    private val messageDao: MessageDao
) {
    fun observeAll(): Flow<List<CharacterEntity>> = dao.observeAll()

    fun observeById(id: Long): Flow<CharacterEntity?> = dao.observeById(id)

    suspend fun getById(id: Long): CharacterEntity? = dao.getById(id)

    suspend fun create(
        name: String,
        mbti: String,
        speechStyle: String,
        relationship: String,
        avatarId: String
    ): Long {
        return dao.insert(
            CharacterEntity(
                name = name,
                mbti = mbti,
                speechStyle = speechStyle,
                relationship = relationship,
                avatarId = avatarId
            )
        )
    }

    suspend fun updateAffinity(id: Long, delta: Int) {
        val character = dao.getById(id) ?: return
        val newScore = (character.affinityScore + delta).coerceIn(0, 100)
        dao.updateAffinity(id, newScore)
    }

    suspend fun delete(id: Long) {
        messageDao.deleteByCharacter(id)
        dao.deleteById(id)
    }

    suspend fun addFromPreset(preset: PresetCharacter): Long {
        return dao.insert(
            CharacterEntity(
                name = preset.name,
                mbti = preset.mbti,
                speechStyle = preset.speechStyle,
                relationship = preset.relationship,
                avatarId = preset.avatarId
            )
        )
    }

    /**
     * 캐릭터가 없으면 그룹별 대표 캐릭터 4명 자동 생성
     */
    suspend fun seedPresetsIfEmpty() {
        val existing = observeAll().first()
        if (existing.isNotEmpty()) return

        PRESET_CHARACTERS
            .filter { it.mbti in listOf("ENFP", "INTJ", "ISFJ", "ESTP") }
            .forEach { addFromPreset(it) }
    }
}
