package com.example.mbtichatfriend.data.local

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import kotlinx.coroutines.flow.Flow

@Dao
interface MessageDao {
    // F17: createdAt만으로는 같은 밀리초에 저장된 메시지의 순서가 비결정적이라
    // id ASC를 2차 정렬 키로 추가해 그룹핑/타임스탬프 규칙이 흔들리지 않게 한다.
    @Query("SELECT * FROM messages WHERE characterId = :characterId ORDER BY createdAt ASC, id ASC")
    fun observeByCharacter(characterId: Long): Flow<List<MessageEntity>>

    // R3: 반환값(rowId)이 필요 — 방금 저장한 유저 메시지의 id를 읽음 워터마크에 사용한다.
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(message: MessageEntity): Long

    @Query("DELETE FROM messages WHERE characterId = :characterId")
    suspend fun deleteByCharacter(characterId: Long)

    @Query("SELECT * FROM messages WHERE characterId = :characterId ORDER BY createdAt DESC LIMIT 1")
    suspend fun getLastMessage(characterId: Long): MessageEntity?

    // F17: 동일 패턴 — id ASC 2차 정렬로 동일 밀리초 저장 시 순서 비결정성 제거
    @Query("SELECT * FROM messages WHERE characterId = :characterId ORDER BY createdAt ASC, id ASC")
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

    // F17: 동일 패턴 — id ASC 2차 정렬로 동일 밀리초 저장 시 FIFO 전송 순서 비결정성 제거
    @Query("SELECT * FROM messages WHERE sendStatus = 'PENDING' ORDER BY createdAt ASC, id ASC")
    suspend fun getPendingMessages(): List<MessageEntity>

    @Query("UPDATE messages SET sendStatus = :status WHERE id = :id")
    suspend fun updateSendStatus(id: Long, status: String)

    @Query("UPDATE messages SET retryCount = retryCount + 1 WHERE id = :id")
    suspend fun incrementRetryCount(id: Long)
}
