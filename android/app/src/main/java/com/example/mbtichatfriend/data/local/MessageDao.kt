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
}
