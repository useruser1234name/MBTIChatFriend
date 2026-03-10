package com.example.mbtichatfriend.model

data class ChatMessage(
    val id: Long,
    val text: String,
    val isFromUser: Boolean,
    val emotion: CharacterEmotion? = null,
    val createdAt: Long = System.currentTimeMillis(),
    val sendStatus: String = "SENT"
)
