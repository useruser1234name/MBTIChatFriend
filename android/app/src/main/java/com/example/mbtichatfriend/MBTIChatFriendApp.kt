package com.example.mbtichatfriend

import android.app.Application
import com.example.mbtichatfriend.data.remote.FcmTokenManager
import com.example.mbtichatfriend.data.remote.RemoteConfigManager
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

    private val appScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    override fun onCreate() {
        super.onCreate()
        appScope.launch {
            remoteConfigManager.init()
            fcmTokenManager.ensureTokenRegistered()
        }
    }
}
