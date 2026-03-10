package com.example.mbtichatfriend.data.local

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "messages")
data class MessageEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val characterId: Long = 0,
    val text: String,
    val isFromUser: Boolean,
    val emotion: String? = null,
    val createdAt: Long = System.currentTimeMillis(),
    val sendStatus: String = "SENT",
    val retryCount: Int = 0
)
