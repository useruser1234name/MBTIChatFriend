package com.example.mbtichatfriend.data.local

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import kotlinx.coroutines.flow.Flow

@Dao
interface DiaryDao {

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(diary: DiaryEntity)

    @Query("SELECT * FROM diaries WHERE characterId = :characterId ORDER BY createdAt DESC")
    fun observeByCharacter(characterId: Long): Flow<List<DiaryEntity>>

    @Query("SELECT * FROM diaries WHERE characterId = :characterId AND date = :date LIMIT 1")
    suspend fun getByDate(characterId: Long, date: String): DiaryEntity?

    @Query("DELETE FROM diaries WHERE characterId = :characterId")
    suspend fun deleteByCharacter(characterId: Long)
}
