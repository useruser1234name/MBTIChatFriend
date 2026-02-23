package com.example.mbtichatfriend.data.local

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "diaries")
data class DiaryEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val characterId: Long,
    val content: String,
    val emotion: String = "NEUTRAL",
    val date: String,           // "yyyy-MM-dd" 형식
    val createdAt: Long = System.currentTimeMillis()
)
