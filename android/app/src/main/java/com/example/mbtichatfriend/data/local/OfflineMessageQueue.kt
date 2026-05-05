package com.example.mbtichatfriend.data.local

import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class OfflineMessageQueue @Inject constructor(
    private val messageDao: MessageDao
) {
    enum class FlushResult {
        SENT,
        RETRY,
        FAILED
    }

    companion object {
        private const val MAX_RETRY = 3
    }

    private val flushMutex = Mutex()

    suspend fun flushPendingMessages(sendAction: suspend (MessageEntity) -> FlushResult) {
        flushMutex.withLock {
            val pendingMessages = messageDao.getPendingMessages()
            for (message in pendingMessages) {
                val result = try {
                    sendAction(message)
                } catch (_: Exception) {
                    FlushResult.RETRY
                }
                when (result) {
                    FlushResult.SENT -> {
                        messageDao.updateSendStatus(message.id, "SENT")
                    }
                    FlushResult.FAILED -> {
                        messageDao.updateSendStatus(message.id, "FAILED")
                    }
                    FlushResult.RETRY -> {
                        messageDao.incrementRetryCount(message.id)
                        val updated = message.retryCount + 1
                        if (updated >= MAX_RETRY) {
                            messageDao.updateSendStatus(message.id, "FAILED")
                        }
                    }
                }
            }
        }
    }
}
