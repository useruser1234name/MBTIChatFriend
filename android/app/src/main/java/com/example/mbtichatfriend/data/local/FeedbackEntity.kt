package com.example.mbtichatfriend.data.local

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "feedback")
data class FeedbackEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val messageId: Long,
    val characterId: Long,
    val feedbackType: String,  // "thumbs_up" | "thumbs_down"
    val roomId: String = "",
    // synced=true는 "서버가 실제로 저장함" 뿐 아니라 "영구 거부(4xx)되어 재시도를 포기함"도 의미한다.
    // (재시도 큐(getUnsynced)에서 제외하는 용도로 재사용 — ChatRepository.syncPendingFeedback 참고)
    val synced: Boolean = false,
    val createdAt: Long = System.currentTimeMillis()
)
