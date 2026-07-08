package com.example.mbtichatfriend

import android.app.Application
import com.example.mbtichatfriend.data.remote.FcmTokenManager
import com.example.mbtichatfriend.data.remote.RemoteConfigManager
import com.example.mbtichatfriend.data.repository.AnalyticsRepository
import com.example.mbtichatfriend.data.repository.AnalyticsEvent
import dagger.hilt.android.HiltAndroidApp
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltAndroidApp
class MBTIChatFriendApp : Application() {

    @Inject lateinit var fcmTokenManager: FcmTokenManager
    @Inject lateinit var remoteConfigManager: RemoteConfigManager
    @Inject lateinit var analyticsRepository: AnalyticsRepository

    val appScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    override fun onCreate() {
        super.onCreate()
        appScope.launch {
            remoteConfigManager.init()
            fcmTokenManager.ensureTokenRegistered()
        }
        // app_open 이벤트 — 앱 콜드 스타트마다 기록 (PM 로드맵 A1)
        analyticsRepository.track(
            scope = appScope,
            eventType = AnalyticsEvent.APP_OPEN,
        )
    }
}
