package com.example.mbtichatfriend.data.remote

import android.util.Log
import com.example.mbtichatfriend.data.local.UserPreferences
import com.google.firebase.messaging.FirebaseMessaging
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.tasks.await
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class FcmTokenManager @Inject constructor(
    private val prefs: UserPreferences,
    private val chatApi: ChatApi
) {
    suspend fun ensureTokenRegistered() {
        try {
            val token = FirebaseMessaging.getInstance().token.await()
            Log.d(TAG, "FCM token: $token")

            val savedToken = prefs.fcmToken.first()
            if (savedToken != token) {
                prefs.updateFcmToken(token)
            }

            val synced = prefs.fcmTokenSynced.first()
            if (!synced) {
                registerTokenWithServer(token)
            }
        } catch (e: Exception) {
            Log.w(TAG, "FCM token registration failed (Firebase may not be configured)", e)
        }
    }

    private suspend fun registerTokenWithServer(token: String) {
        try {
            val uid = prefs.firebaseUid.first()
            chatApi.registerFcmToken(FcmTokenRequest(token = token, userId = uid))
            prefs.markFcmTokenSynced()
            Log.d(TAG, "FCM token registered with server")
        } catch (e: Exception) {
            Log.w(TAG, "Failed to register FCM token with server", e)
        }
    }

    companion object {
        private const val TAG = "FcmTokenManager"
    }
}
