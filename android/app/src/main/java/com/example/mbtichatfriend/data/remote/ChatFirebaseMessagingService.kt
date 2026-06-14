package com.example.mbtichatfriend.data.remote

import android.app.PendingIntent
import android.content.Intent
import android.net.Uri
import android.util.Log
import com.example.mbtichatfriend.MainActivity
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
        Log.d(TAG, "New FCM token received")
        serviceScope.launch {
            prefs.updateFcmToken(token)
        }
    }

    override fun onMessageReceived(message: RemoteMessage) {
        super.onMessageReceived(message)
        Log.d(TAG, "FCM message received: ${message.data}")

        val notificationType = message.data["notification_type"]

        // D-2 레퍼럴 만료 알림 처리 (17차 스프린트)
        if (notificationType == "d2_expiry_receiver" || notificationType == "d2_expiry_sender") {
            handleD2ExpiryNotification(message.data)
            return
        }

        // 커뮤니티 알림 딥링크 처리 (22차 스프린트)
        if (notificationType == "community_comment" || notificationType == "community_empathy") {
            handleCommunityNotification(message.data, notificationType)
            return
        }

        // 레퍼럴 D-2 딥링크 처리 (22차 스프린트)
        if (notificationType == "referral_d2") {
            handleReferralD2DeepLink(message.data)
            return
        }

        // D+7 알림 딥링크 처리 (27차 스프린트)
        if (notificationType == "d3_personalized" || notificationType == "d5_character") {
            handleCharacterDeepLinkNotification(message.data, notificationType)
            return
        }
        if (notificationType == "weekly_summary") {
            handleWeeklySummaryNotification(message.data)
            return
        }
        if (notificationType == "referral_reward") {
            handleReferralRewardNotification(message.data)
            return
        }

        val characterName = message.data["character_name"] ?: "알 수 없음"
        val text = message.data["message"] ?: message.notification?.body ?: return
        val characterId = message.data["character_id"]?.toLongOrNull() ?: 0L

        // deep_link가 있으면 딥링크 PendingIntent, 없으면 기존 MainActivity 진입
        val deepLink = message.data["deep_link"]
        val pendingIntent = if (!deepLink.isNullOrEmpty()) {
            buildDeepLinkPendingIntent(deepLink, characterId.toInt())
        } else {
            null
        }

        notificationHelper.showChatNotification(
            characterName = characterName,
            message = text,
            characterId = characterId,
            pendingIntent = pendingIntent
        )
    }

    // ── 커뮤니티 알림 (22차 스프린트) ────────────────────────────────────────
    private fun handleCommunityNotification(data: Map<String, String>, notificationType: String) {
        val postId = data["post_id"] ?: return
        val title = data["title"] ?: when (notificationType) {
            "community_comment" -> "새 댓글이 달렸어요"
            "community_empathy" -> "공감을 받았어요"
            else -> "커뮤니티 알림"
        }
        val body = data["message"] ?: title
        val deepLink = data["deep_link"] ?: "mbtichat://community/$postId"
        val pendingIntent = buildDeepLinkPendingIntent(deepLink, postId.hashCode())
        notificationHelper.showDeepLinkNotification(
            title = title,
            body = body,
            pendingIntent = pendingIntent,
            notificationId = postId.hashCode()
        )
    }

    // ── 레퍼럴 D-2 딥링크 처리 (22차 스프린트) ───────────────────────────────
    private fun handleReferralD2DeepLink(data: Map<String, String>) {
        val title = data["title"] ?: "레퍼럴 알림"
        val body = data["message"] ?: title
        val deepLink = data["deep_link"] ?: "mbtichat://settings/referral"
        val pendingIntent = buildDeepLinkPendingIntent(deepLink, NOTIFICATION_ID_REFERRAL_DL)
        notificationHelper.showDeepLinkNotification(
            title = title,
            body = body,
            pendingIntent = pendingIntent,
            notificationId = NOTIFICATION_ID_REFERRAL_DL,
            channelId = NotificationHelper.CHANNEL_ID_REFERRAL
        )
    }

    // ── D-2 레퍼럴 만료 알림 처리 (17차 스프린트) ─────────────────────────────
    private fun handleD2ExpiryNotification(data: Map<String, String>) {
        val code = data["code"] ?: return
        val notificationType = data["notification_type"] ?: return
        notificationHelper.showReferralD2Notification(code = code, notificationType = notificationType)
    }

    // ── D+7 캐릭터 딥링크 알림 처리 (27차 스프린트) ───────────────────────────
    private fun handleCharacterDeepLinkNotification(
        data: Map<String, String>,
        notificationType: String
    ) {
        val characterId = data["character_id"] ?: return
        val title = data["title"] ?: when (notificationType) {
            "d3_personalized" -> "맞춤 메시지가 도착했어요"
            "d5_character" -> "친구가 기다리고 있어요"
            else -> "새 알림"
        }
        val body = data["message"] ?: title
        val deepLink = data["deep_link"] ?: "mbtichat://chat/$characterId"
        val pendingIntent = buildDeepLinkPendingIntent(deepLink, deepLink.hashCode())
        notificationHelper.showDeepLinkNotification(
            title = title,
            body = body,
            pendingIntent = pendingIntent,
            notificationId = deepLink.hashCode()
        )
    }

    // ── 주간 요약 알림 처리 (27차 스프린트) ───────────────────────────────────
    private fun handleWeeklySummaryNotification(data: Map<String, String>) {
        val title = data["title"] ?: "이번 주 대화 요약"
        val body = data["message"] ?: title
        val deepLink = data["deep_link"] ?: "mbtichat://home"
        val pendingIntent = buildDeepLinkPendingIntent(deepLink, NOTIFICATION_ID_WEEKLY_SUMMARY)
        notificationHelper.showDeepLinkNotification(
            title = title,
            body = body,
            pendingIntent = pendingIntent,
            notificationId = NOTIFICATION_ID_WEEKLY_SUMMARY
        )
    }

    // ── 레퍼럴 리워드 알림 처리 (27차 스프린트) ──────────────────────────────
    private fun handleReferralRewardNotification(data: Map<String, String>) {
        val title = data["title"] ?: "레퍼럴 리워드 지급!"
        val body = data["message"] ?: title
        val deepLink = data["deep_link"] ?: "mbtichat://settings/referral"
        val pendingIntent = buildDeepLinkPendingIntent(deepLink, NOTIFICATION_ID_REFERRAL_REWARD)
        notificationHelper.showDeepLinkNotification(
            title = title,
            body = body,
            pendingIntent = pendingIntent,
            notificationId = NOTIFICATION_ID_REFERRAL_REWARD,
            channelId = NotificationHelper.CHANNEL_ID_REFERRAL
        )
    }

    // ── 딥링크 PendingIntent 빌더 (22차 스프린트) ─────────────────────────────
    private fun buildDeepLinkPendingIntent(deepLink: String, requestCode: Int): PendingIntent {
        val intent = Intent(Intent.ACTION_VIEW, Uri.parse(deepLink), applicationContext, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }
        return PendingIntent.getActivity(
            applicationContext,
            requestCode,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
    }

    companion object {
        private const val TAG = "FCMService"
        private const val NOTIFICATION_ID_REFERRAL_DL = 2002
        private const val NOTIFICATION_ID_WEEKLY_SUMMARY = 2003
        private const val NOTIFICATION_ID_REFERRAL_REWARD = 2004
    }
}
