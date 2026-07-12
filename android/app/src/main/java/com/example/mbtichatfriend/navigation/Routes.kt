package com.example.mbtichatfriend.navigation

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ChatBubble
import androidx.compose.material.icons.filled.Explore
import androidx.compose.material.icons.filled.Forum
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.outlined.ChatBubbleOutline
import androidx.compose.material.icons.outlined.Explore
import androidx.compose.material.icons.outlined.Forum
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
    data object StarterSelection : Route("onboarding/starter")
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
    data object Community : Route("community")
    data object WritePost : Route("community/write")
    data object PostDetail : Route("community/{postId}") {
        fun createRoute(postId: Long) = "community/$postId"
    }
    data object Compatibility : Route("compatibility/{myMbti}/{characterMbti}") {
        fun createRoute(myMbti: String, characterMbti: String) = "compatibility/$myMbti/$characterMbti"
    }
    data object Notifications : Route("notifications")
    data object YearReport : Route("year_report")
    // 32차 스프린트: 사용자 직접 입력 다이어리
    data object DiaryEntry : Route("diary_entry/{characterId}") {
        fun createRoute(characterId: Long) = "diary_entry/$characterId"
    }
    // 32차 스프린트: 주간 감정 리포트
    data object DiaryWeeklyReport : Route("diary_weekly_report")
    // 36차 스프린트: 프리미엄 구독
    data object Premium : Route("premium")
    // 36차 스프린트: 언어 설정
    data object LanguageSetting : Route("language_setting")
}

enum class BottomNavItem(
    val route: String,
    val label: String,
    val selectedIcon: ImageVector,
    val unselectedIcon: ImageVector
) {
    HOME(Route.Home.route, "홈", Icons.Filled.ChatBubble, Icons.Outlined.ChatBubbleOutline),
    GALLERY(Route.Gallery.route, "갤러리", Icons.Filled.Explore, Icons.Outlined.Explore),
    COMMUNITY(Route.Community.route, "커뮤니티", Icons.Filled.Forum, Icons.Outlined.Forum),
    SETTINGS(Route.Settings.route, "설정", Icons.Filled.Settings, Icons.Outlined.Settings)
}
