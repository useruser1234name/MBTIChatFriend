package com.example.mbtichatfriend.data.repository

import com.example.mbtichatfriend.data.remote.ChatApi
import javax.inject.Inject
import javax.inject.Singleton

data class LetterResponse(
    val has_letter: Boolean,
    val content: String,
    val generated_date: String,
)

@Singleton
class LetterRepository @Inject constructor(
    private val api: ChatApi,
) {
    suspend fun getLatestLetter(
        roomId: String,
        characterId: String,
    ): Result<LetterResponse> = runCatching {
        api.getLatestLetter(roomId, characterId)
    }
}
