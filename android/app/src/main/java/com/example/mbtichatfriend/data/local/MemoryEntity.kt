package com.example.mbtichatfriend.data.local

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "memories")
data class MemoryEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val characterId: Long,
    val key: String,
    val value: String,
    val createdAt: Long = System.currentTimeMillis()
)
