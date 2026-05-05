package com.example.mbtichatfriend.data.local

import androidx.room.Entity
import androidx.room.ColumnInfo
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
    @ColumnInfo(defaultValue = "''") val personaRaw: String = "",
    @ColumnInfo(defaultValue = "''") val personaSummary: String = "",
    @ColumnInfo(defaultValue = "''") val dialoguePrompt: String = "",
    @ColumnInfo(defaultValue = "''") val visualPrompt: String = "",
    val createdAt: Long = System.currentTimeMillis()
) {
    val affinityLevel: Int
        get() = when {
            affinityScore >= 80 -> 5
            affinityScore >= 60 -> 4
            affinityScore >= 40 -> 3
            affinityScore >= 20 -> 2
            else -> 1
        }
}
