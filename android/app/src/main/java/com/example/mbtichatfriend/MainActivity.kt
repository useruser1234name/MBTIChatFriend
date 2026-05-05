package com.example.mbtichatfriend

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.derivedStateOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.lifecycleScope
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.example.mbtichatfriend.data.local.UserPreferences
import com.example.mbtichatfriend.data.remote.ChatApi
import com.example.mbtichatfriend.data.remote.RedeemRequest
import com.example.mbtichatfriend.navigation.AppNavHost
import com.example.mbtichatfriend.navigation.BottomNavItem
import com.example.mbtichatfriend.navigation.Route
import com.example.mbtichatfriend.ui.theme.MBTIChatFriendTheme
import dagger.hilt.android.AndroidEntryPoint
import kotlinx.coroutines.launch
import javax.inject.Inject

@AndroidEntryPoint
class MainActivity : ComponentActivity() {

    @Inject
    lateinit var userPreferences: UserPreferences

    @Inject
    lateinit var chatApi: ChatApi

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        // 레퍼럴 V3 딥링크 자동 처리 (29차 스프린트)
        handleReferralDeepLink(intent)

        setContent {
            val darkModePreference by userPreferences.darkMode.collectAsState(initial = "system")
            val isDark = when (darkModePreference) {
                "dark" -> true
                "light" -> false
                else -> isSystemInDarkTheme()
            }

            MBTIChatFriendTheme(darkTheme = isDark, dynamicColor = false) {
                val navController = rememberNavController()
                val navBackStackEntry by navController.currentBackStackEntryAsState()
                val currentRoute = navBackStackEntry?.destination?.route
                val snackbarHostState = remember { SnackbarHostState() }
                val scope = rememberCoroutineScope()

                // 바텀 네비가 보여야 하는 화면들
                val bottomNavRoutes = remember {
                    setOf(Route.Home.route, Route.Gallery.route, Route.Community.route, Route.Settings.route)
                }
                val showBottomBar by remember(currentRoute) {
                    derivedStateOf { currentRoute in bottomNavRoutes }
                }

                Scaffold(
                    snackbarHost = { SnackbarHost(snackbarHostState) },
                    bottomBar = {
                        AnimatedVisibility(
                            visible = showBottomBar,
                            enter = slideInVertically(initialOffsetY = { it }),
                            exit = slideOutVertically(targetOffsetY = { it })
                        ) {
                            NavigationBar(
                                containerColor = MaterialTheme.colorScheme.surface,
                                tonalElevation = 2.dp
                            ) {
                                BottomNavItem.entries.forEach { item ->
                                    val isSelected = currentRoute == item.route
                                    NavigationBarItem(
                                        selected = isSelected,
                                        onClick = {
                                            navController.navigate(item.route) {
                                                popUpTo(navController.graph.findStartDestination().id) {
                                                    saveState = true
                                                }
                                                launchSingleTop = true
                                                restoreState = true
                                            }
                                        },
                                        icon = {
                                            Icon(
                                                if (isSelected) item.selectedIcon else item.unselectedIcon,
                                                contentDescription = item.label
                                            )
                                        },
                                        label = { Text(item.label, style = MaterialTheme.typography.labelSmall) },
                                        colors = NavigationBarItemDefaults.colors(
                                            selectedIconColor = MaterialTheme.colorScheme.primary,
                                            selectedTextColor = MaterialTheme.colorScheme.primary,
                                            indicatorColor = MaterialTheme.colorScheme.primaryContainer
                                        )
                                    )
                                }
                            }
                        }
                    }
                ) { innerPadding ->
                    AppNavHost(
                        navController = navController,
                        modifier = Modifier.padding(innerPadding)
                    )
                }

                // 알림 탭으로부터의 딥링크 처리
                LaunchedEffect(Unit) {
                    handleDeepLink(intent)?.let { characterId ->
                        navController.navigate(Route.Chat.createRoute(characterId)) {
                            launchSingleTop = true
                        }
                    }
                }

                // 레퍼럴 V3 리딤 성공 Snackbar 수신
                LaunchedEffect(Unit) {
                    referralSuccessMessage?.let { message ->
                        scope.launch { snackbarHostState.showSnackbar(message) }
                        referralSuccessMessage = null
                    }
                }
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        // 앱이 이미 실행 중일 때 수신된 레퍼럴 딥링크 처리
        handleReferralDeepLink(intent)
    }

    private fun handleDeepLink(intent: Intent?): Long? {
        val characterId = intent?.getLongExtra("characterId", -1L) ?: -1L
        return if (characterId > 0) characterId else null
    }

    // 레퍼럴 V3 딥링크 처리 (29차 스프린트)
    // mbtichat.page.link/invite?code=XXXX 형태의 앱 링크를 파싱하여 자동 리딤
    private var referralSuccessMessage: String? = null

    private fun handleReferralDeepLink(intent: Intent?) {
        val uri = intent?.data ?: return
        if (uri.host != "mbtichat.page.link") return
        if (uri.path != "/invite") return
        val code = uri.getQueryParameter("code") ?: return

        lifecycleScope.launch {
            runCatching {
                val response = chatApi.redeemReferral(RedeemRequest(code))
                if (response.isSuccessful) {
                    referralSuccessMessage = "🎉 친구 초대 혜택 7일이 추가됐어요!"
                }
            }.onFailure { e ->
                android.util.Log.w("MainActivity", "레퍼럴 V3 리딤 실패", e)
            }
        }
    }
}
