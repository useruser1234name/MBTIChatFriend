package com.example.mbtichatfriend.navigation

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ChatBubble
import androidx.compose.material.icons.filled.Explore
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.outlined.ChatBubbleOutline
import androidx.compose.material.icons.outlined.Explore
import androidx.compose.material.icons.outlined.Settings
import androidx.compose.ui.graphics.vector.ImageVector

sealed class Route(val route: String) {
    data object Splash : Route("splash")
    data object Login : Route("login")
    data object Nickname : Route("onboarding/nickname")
    data object Gender : Route("onboarding/gender")
    data object Age : Route("onboarding/age")
    data object MbtiSelect : Route("onboarding/mbti")
    data object StyleSelect : Route("onboarding/style")
    data object Home : Route("home")
    data object Chat : Route("chat/{characterId}") {
        fun createRoute(characterId: Long) = "chat/$characterId"
    }
    data object CharacterProfile : Route("character/{characterId}") {
        fun createRoute(characterId: Long) = "character/$characterId"
    }
    data object Settings : Route("settings")
    data object VoiceCall : Route("voicecall/{characterId}") {
        fun createRoute(characterId: Long) = "voicecall/$characterId"
    }
    data object Diary : Route("diary/{characterId}") {
        fun createRoute(characterId: Long) = "diary/$characterId"
    }
    data object Gallery : Route("gallery")
}

enum class BottomNavItem(
    val route: String,
    val label: String,
    val selectedIcon: ImageVector,
    val unselectedIcon: ImageVector
) {
    HOME(Route.Home.route, "채팅", Icons.Filled.ChatBubble, Icons.Outlined.ChatBubbleOutline),
    GALLERY(Route.Gallery.route, "갤러리", Icons.Filled.Explore, Icons.Outlined.Explore),
    SETTINGS(Route.Settings.route, "설정", Icons.Filled.Settings, Icons.Outlined.Settings)
}
