package com.example.mbtichatfriend.data.repository

import com.example.mbtichatfriend.data.remote.ChatApi
import com.example.mbtichatfriend.data.remote.LetterResponse
import javax.inject.Inject
import javax.inject.Singleton

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
