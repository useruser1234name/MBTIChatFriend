package com.example.mbtichatfriend.data.local

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import kotlinx.coroutines.flow.Flow

@Dao
interface MessageDao {
    @Query("SELECT * FROM messages WHERE characterId = :characterId ORDER BY createdAt ASC")
    fun observeByCharacter(characterId: Long): Flow<List<MessageEntity>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(message: MessageEntity)

    @Query("DELETE FROM messages WHERE characterId = :characterId")
    suspend fun deleteByCharacter(characterId: Long)

    @Query("SELECT * FROM messages WHERE characterId = :characterId ORDER BY createdAt DESC LIMIT 1")
    suspend fun getLastMessage(characterId: Long): MessageEntity?

    @Query("SELECT * FROM messages WHERE characterId = :characterId ORDER BY createdAt ASC")
    suspend fun getAllByCharacter(characterId: Long): List<MessageEntity>

    @Query("DELETE FROM messages")
    suspend fun deleteAll()

    @Query("""
        SELECT m.* FROM messages m
        INNER JOIN (
            SELECT characterId, MAX(createdAt) AS maxCreatedAt
            FROM messages
            GROUP BY characterId
        ) latest ON m.characterId = latest.characterId AND m.createdAt = latest.maxCreatedAt
    """)
    suspend fun getLastMessagePerCharacter(): List<MessageEntity>

    @Query("SELECT * FROM messages WHERE sendStatus = 'PENDING' ORDER BY createdAt ASC")
    suspend fun getPendingMessages(): List<MessageEntity>

    @Query("UPDATE messages SET sendStatus = :status WHERE id = :id")
    suspend fun updateSendStatus(id: Long, status: String)

    @Query("UPDATE messages SET retryCount = retryCount + 1 WHERE id = :id")
    suspend fun incrementRetryCount(id: Long)
}
