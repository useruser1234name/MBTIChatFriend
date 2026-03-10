package com.example.mbtichatfriend.data.local

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "feedback")
data class FeedbackEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val messageId: Long,
    val characterId: Long,
    val feedbackType: String,  // "thumbs_up" | "thumbs_down"
    val synced: Boolean = false,
    val createdAt: Long = System.currentTimeMillis()
)
