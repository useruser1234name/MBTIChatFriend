package com.example.mbtichatfriend.data.remote

import android.util.Log
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
        Log.d(TAG, "New FCM token: $token")
        serviceScope.launch {
            prefs.updateFcmToken(token)
        }
    }

    override fun onMessageReceived(message: RemoteMessage) {
        super.onMessageReceived(message)
        Log.d(TAG, "FCM message received: ${message.data}")

        val characterName = message.data["character_name"] ?: "알 수 없음"
        val text = message.data["message"] ?: message.notification?.body ?: return
        val characterId = message.data["character_id"]?.toLongOrNull() ?: 0L

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
