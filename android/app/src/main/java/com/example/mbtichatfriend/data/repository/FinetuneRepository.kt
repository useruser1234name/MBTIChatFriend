package com.example.mbtichatfriend.data.repository

import com.example.mbtichatfriend.data.local.CharacterEntity
import com.example.mbtichatfriend.data.local.MessageDao
import com.example.mbtichatfriend.data.remote.ChatApi
import com.example.mbtichatfriend.data.remote.FinetuneActivateRequest
import com.example.mbtichatfriend.data.remote.FinetuneStartRequest
import com.example.mbtichatfriend.data.remote.FinetuneStartResponse
import com.example.mbtichatfriend.data.remote.FinetuneStatusResponse
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class FinetuneRepository @Inject constructor(
    private val api: ChatApi,
    private val messageDao: MessageDao
) {
    suspend fun startFinetune(
        character: CharacterEntity,
        nickname: String
    ): FinetuneStartResponse {
        val messages = messageDao.getAllByCharacter(character.id)
        val conversations = messages.map { msg ->
            mapOf(
                "role" to if (msg.isFromUser) "user" else "assistant",
                "content" to msg.text
            )
        }
        return api.startFinetune(
            FinetuneStartRequest(
                characterId = character.id.toString(),
                characterName = character.name,
                mbti = character.mbti,
                speechStyle = character.speechStyle,
                relationship = character.relationship,
                nickname = nickname,
                affinityLevel = character.affinityLevel,
                conversations = conversations
            )
        )
    }

    suspend fun checkStatus(jobId: String): FinetuneStatusResponse =
        api.getFinetuneStatus(jobId)

    suspend fun activateModel(characterId: String, modelId: String) {
        api.activateFinetune(FinetuneActivateRequest(characterId, modelId))
    }
}
