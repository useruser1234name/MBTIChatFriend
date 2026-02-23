package com.example.mbtichatfriend

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.navigation.compose.rememberNavController
import com.example.mbtichatfriend.data.local.UserPreferences
import com.example.mbtichatfriend.navigation.AppNavHost
import com.example.mbtichatfriend.navigation.Route
import com.example.mbtichatfriend.ui.theme.MBTIChatFriendTheme
import dagger.hilt.android.AndroidEntryPoint
import javax.inject.Inject

@AndroidEntryPoint
class MainActivity : ComponentActivity() {

    @Inject
    lateinit var userPreferences: UserPreferences

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            val darkModePreference by userPreferences.darkMode.collectAsState(initial = "system")
            val isDark = when (darkModePreference) {
                "dark" -> true
                "light" -> false
                else -> isSystemInDarkTheme()
            }

            MBTIChatFriendTheme(darkTheme = isDark, dynamicColor = false) {
                val navController = rememberNavController()
                AppNavHost(navController = navController)

                // 알림 탭으로부터의 딥링크 처리
                LaunchedEffect(Unit) {
                    handleDeepLink(intent)?.let { characterId ->
                        navController.navigate(Route.Chat.createRoute(characterId)) {
                            launchSingleTop = true
                        }
                    }
                }
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
    }

    private fun handleDeepLink(intent: Intent?): Long? {
        val characterId = intent?.getLongExtra("characterId", -1L) ?: -1L
        return if (characterId > 0) characterId else null
    }
}
