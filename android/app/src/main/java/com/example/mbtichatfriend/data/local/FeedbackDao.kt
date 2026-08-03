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

    // A3: 채팅방 진입 시 피드백맵을 한 번에 복원하기 위한 방 단위 일괄 조회.
    // (메시지 개수만큼 getByMessageId를 N회 호출하지 않도록 추가 — 스키마 변경 없음, 기존 컬럼만 사용)
    @Query("SELECT * FROM feedback WHERE characterId = :characterId")
    suspend fun getByCharacterId(characterId: Long): List<FeedbackEntity>

    @Query("SELECT * FROM feedback WHERE synced = 0 ORDER BY createdAt ASC")
    suspend fun getUnsynced(): List<FeedbackEntity>

    @Query("UPDATE feedback SET synced = 1 WHERE id = :id")
    suspend fun markSynced(id: Long)
}
