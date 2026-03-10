package com.example.mbtichatfriend.data.local

import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class OfflineMessageQueue @Inject constructor(
    private val messageDao: MessageDao
) {
    companion object {
        private const val MAX_RETRY = 3
    }

    suspend fun flushPendingMessages(sendAction: suspend (MessageEntity) -> Boolean) {
        val pendingMessages = messageDao.getPendingMessages()
        for (message in pendingMessages) {
            val success = try {
                sendAction(message)
            } catch (_: Exception) {
                false
            }
            if (success) {
                messageDao.updateSendStatus(message.id, "SENT")
            } else {
                messageDao.incrementRetryCount(message.id)
                val updated = message.retryCount + 1
                if (updated >= MAX_RETRY) {
                    messageDao.updateSendStatus(message.id, "FAILED")
                }
            }
        }
    }
}
