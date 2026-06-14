package com.example.mbtichatfriend.data.local

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query

@Dao
interface FeedbackDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(feedback: FeedbackEntity)

    @Query("SELECT * FROM feedback WHERE messageId = :messageId LIMIT 1")
    suspend fun getByMessageId(messageId: Long): FeedbackEntity?

    @Query("SELECT * FROM feedback WHERE synced = 0 ORDER BY createdAt ASC")
    suspend fun getUnsynced(): List<FeedbackEntity>

    @Query("UPDATE feedback SET synced = 1 WHERE id = :id")
    suspend fun markSynced(id: Long)

    @Query("DELETE FROM feedback")
    suspend fun deleteAll()
}
