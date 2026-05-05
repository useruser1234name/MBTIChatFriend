package com.example.mbtichatfriend.data.remote

import android.util.Log
import com.example.mbtichatfriend.BuildConfig
import com.example.mbtichatfriend.data.MessageConstraints
import com.example.mbtichatfriend.data.local.NotificationHelper
import com.example.mbtichatfriend.data.local.UserPreferences
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import dagger.hilt.android.AndroidEntryPoint
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import javax.inject.Inject

@AndroidEntryPoint
class ChatFirebaseMessagingService : FirebaseMessagingService() {

    @Inject lateinit var notificationHelper: NotificationHelper
    @Inject lateinit var prefs: UserPreferences

    private val serviceScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    override fun onNewToken(token: String) {
        super.onNewToken(token)
        if (BuildConfig.DEBUG) { Log.d(TAG, "New FCM token: ...${token.takeLast(6)}") }
        serviceScope.launch {
            prefs.updateFcmToken(token)
        }
    }

    override fun onMessageReceived(message: RemoteMessage) {
        super.onMessageReceived(message)
        Log.d(TAG, "FCM message received from: ${message.from}")

        // 데이터 검증: 필수 필드 확인
        val rawText = message.data["message"] ?: message.notification?.body
        if (rawText.isNullOrBlank()) {
            Log.w(TAG, "FCM message ignored: empty or missing message field")
            return
        }

        // 길이 검증: 서버 최대 2000자 + 여유분 허용
        if (rawText.length > MessageConstraints.MAX_FCM_MESSAGE_LENGTH) {
            Log.w(TAG, "FCM message ignored: message length ${rawText.length} exceeds limit")
            return
        }

        val characterName = message.data["character_name"]
            ?.take(50)  // 캐릭터 이름 최대 50자
            ?.ifBlank { "알 수 없음" }
            ?: "알 수 없음"

        val characterId = message.data["character_id"]?.toLongOrNull()
        if (characterId == null || characterId <= 0L) {
            Log.w(TAG, "FCM message ignored: invalid character_id")
            return
        }

        val text = rawText.take(MessageConstraints.MAX_NOTIFICATION_PREVIEW_LENGTH) // 알림 표시용으로 500자 이내로 자름

        notificationHelper.showChatNotification(
            characterName = characterName,
            message = text,
            characterId = characterId
        )
    }

    companion object {
        private const val TAG = "FCMService"
    }
}
