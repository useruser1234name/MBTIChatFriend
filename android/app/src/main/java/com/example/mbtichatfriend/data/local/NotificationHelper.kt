package com.example.mbtichatfriend.data.local

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import com.example.mbtichatfriend.MainActivity
import com.example.mbtichatfriend.R
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class NotificationHelper @Inject constructor(
    @ApplicationContext private val context: Context
) {
    companion object {
        private const val CHANNEL_ID = "chat_messages"
        private const val CHANNEL_NAME = "채팅 메시지"
        private const val CHANNEL_DESC = "캐릭터로부터의 새 메시지 알림"

        // 레퍼럴 알림 채널 (17차 스프린트)
        const val CHANNEL_ID_REFERRAL = "referral_notifications"
        private const val CHANNEL_NAME_REFERRAL = "초대 알림"
        private const val CHANNEL_DESC_REFERRAL = "초대 코드 관련 알림"
        const val NOTIFICATION_ID_REFERRAL_D2 = 2001
    }

    private val notificationManager =
        context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager

    init {
        createChannel()
        createReferralChannel()
    }

    private fun createChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                CHANNEL_NAME,
                NotificationManager.IMPORTANCE_DEFAULT
            ).apply {
                description = CHANNEL_DESC
            }
            notificationManager.createNotificationChannel(channel)
        }
    }

    private fun createReferralChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID_REFERRAL,
                CHANNEL_NAME_REFERRAL,
                NotificationManager.IMPORTANCE_DEFAULT
            ).apply {
                description = CHANNEL_DESC_REFERRAL
            }
            notificationManager.createNotificationChannel(channel)
        }
    }

    fun showChatNotification(
        characterName: String,
        message: String,
        characterId: Long,
        pendingIntent: PendingIntent? = null
    ) {
        val resolvedIntent = pendingIntent ?: run {
            val intent = Intent(context, MainActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_SINGLE_TOP
                putExtra("characterId", characterId)
            }
            PendingIntent.getActivity(
                context, characterId.toInt(), intent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
            )
        }

        val notification = NotificationCompat.Builder(context, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_launcher_foreground)
            .setContentTitle(characterName)
            .setContentText(message)
            .setAutoCancel(true)
            .setContentIntent(resolvedIntent)
            .setPriority(NotificationCompat.PRIORITY_DEFAULT)
            .build()

        notificationManager.notify(characterId.toInt(), notification)
    }

    // ── 딥링크 범용 알림 (22차 스프린트) ──────────────────────────────────────
    fun showDeepLinkNotification(
        title: String,
        body: String,
        pendingIntent: PendingIntent,
        notificationId: Int,
        channelId: String = CHANNEL_ID
    ) {
        val notification = NotificationCompat.Builder(context, channelId)
            .setSmallIcon(R.drawable.ic_launcher_foreground)
            .setContentTitle(title)
            .setContentText(body)
            .setStyle(NotificationCompat.BigTextStyle().bigText(body))
            .setAutoCancel(true)
            .setContentIntent(pendingIntent)
            .setPriority(NotificationCompat.PRIORITY_DEFAULT)
            .build()

        NotificationManagerCompat.from(context).notify(notificationId, notification)
    }

    // ── D-2 레퍼럴 만료 알림 (17차 스프린트) ──────────────────────────────────
    fun showReferralD2Notification(code: String, notificationType: String) {
        val (title, body) = when (notificationType) {
            "d2_expiry_receiver" ->
                "초대 코드 만료 D-2" to "받은 초대 코드가 2일 후 만료됩니다. 지금 가입하면 프리미엄 3일이 무료예요!"
            "d2_expiry_sender" ->
                "친구가 아직 가입 안 했어요" to "보낸 초대 코드가 2일 후 만료됩니다. 친구에게 한 번 더 알려볼까요?"
            else -> return
        }

        val intent = Intent(context, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK
            putExtra("deep_link", "mbtichatfriend://referral?code=$code")
        }
        val pendingIntent = PendingIntent.getActivity(
            context, NOTIFICATION_ID_REFERRAL_D2, intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val notification = NotificationCompat.Builder(context, CHANNEL_ID_REFERRAL)
            .setSmallIcon(R.drawable.ic_launcher_foreground)
            .setContentTitle(title)
            .setContentText(body)
            .setStyle(NotificationCompat.BigTextStyle().bigText(body))
            .setAutoCancel(true)
            .setContentIntent(pendingIntent)
            .setPriority(NotificationCompat.PRIORITY_DEFAULT)
            .build()

        NotificationManagerCompat.from(context).notify(NOTIFICATION_ID_REFERRAL_D2, notification)
    }
}
