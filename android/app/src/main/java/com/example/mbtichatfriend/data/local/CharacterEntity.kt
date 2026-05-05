package com.example.mbtichatfriend.data.local

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "characters")
data class CharacterEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val name: String,
    val mbti: String,
    val speechStyle: String,
    val relationship: String,
    val affinityScore: Int = 0,
    val totalMessages: Int = 0,
    val avatarId: String = "default",
    val expressionSet: String? = null,
    val expressionSetReady: Boolean = false,
    val createdAt: Long = System.currentTimeMillis()
) {
    val affinityLevel: Int
        get() = when {
            affinityScore >= 81 -> 5
            affinityScore >= 61 -> 4
            affinityScore >= 41 -> 3
            affinityScore >= 21 -> 2
            else -> 1
        }
}
